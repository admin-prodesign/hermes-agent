#!/usr/bin/env python3
"""Bounded AppSheet user access: HR_EAS settings, notification groups, subscriber add."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from tools.pd_one_ops.pd_one_google_group_member_ops import ALLOWED_MM_CHANNEL_IDS

ANDY_USER_ID = "5nak6m7nmf8kudbrwbtccazbgc"
APPSHEET_MANAGE_APP_ID = "f2073120-8c2e-4930-b13c-105838c5e4c3"
APPSHEET_MANAGE_APP_NAME = "prodesign-group-1163872-25-01-09"
LIVE_CONFIRMATION = "RUN LIVE APPSHEET USER ACCESS"
KNOWN_NOTIFICATION_GROUPS = frozenset({"Team_SeniorStaff", "Team_Molding_Staff"})
NOTIFICATION_TOKEN_RE = re.compile(r"^Team_[A-Za-z0-9_]+$")
SETTINGS_TABLE = "HR_Employees_AppSheet_Settings"
HR_TABLE = "HR_Employees"
SETTINGS_WRITABLE_FIELDS = frozenset({
    "PersonID",
    "Name_ZH",
    "Company Email",
    "Appsheet Email",
    "Appsheet Notification Group",
})

_logger = logging.getLogger("pd_one_ops")


def _quote(person_id: str) -> str:
    return str(person_id or "").replace('"', '""')


def load_appsheet_manage_session(session_factory: Callable[[], Any] | None = None) -> Any:
    """Load an authenticated requests.Session for AppSheet manage APIs (mockable in tests)."""
    if session_factory is not None:
        return session_factory()
    from tools.pd_one_ops.pd_one_appsheet_definition_ops import editor_cookie_paths

    cookie_file, key_file = editor_cookie_paths()
    from tools.pd_one_ops.pd_one_appsheet_definition_ops import EditorClient

    client = EditorClient.from_cookie_files(
        cookie_file, key_file, app_id=APPSHEET_MANAGE_APP_ID, app_name=APPSHEET_MANAGE_APP_NAME,
    )
    return client._session


def _default_post_fetcher(post_id: str) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_part1 import _mattermost_lookup_get, mattermost_context

    base, headers, _me = mattermost_context()
    receipt, post = _mattermost_lookup_get(base, headers, f"/api/v4/posts/{post_id}")
    if receipt.get("status") != 200 or not post:
        raise ValueError(f"Mattermost post {post_id} could not be re-fetched for authorization")
    return post


def _authorization_message_text(
    post: dict[str, Any], post_fetcher: Callable[[str], dict[str, Any]],
) -> str:
    parts = [str(post.get("message") or "")]
    root_id = str(post.get("root_id") or "").strip()
    post_id = str(post.get("id") or "").strip()
    if root_id and root_id != post_id:
        root = post_fetcher(root_id)
        if not isinstance(root, dict):
            raise ValueError(f"thread root post {root_id} could not be re-fetched for authorization")
        parts.insert(0, str(root.get("message") or ""))
    return "\n".join(parts)


def authorize_andy_post(
    *,
    authorizing_post_id: str,
    name_zh: str,
    email: str,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    post_id = str(authorizing_post_id or "").strip()
    if not post_id:
        raise ValueError("authorizing_post_id is required")
    fetch = post_fetcher or _default_post_fetcher
    post = fetch(post_id)
    if str(post.get("user_id") or "") != ANDY_USER_ID:
        raise ValueError("Mattermost post sender is not Andy; caller-supplied sender ids are not trusted")
    if int(post.get("delete_at") or 0):
        raise ValueError(f"Mattermost post {post_id} is deleted")
    channel_id = str(post.get("channel_id") or "")
    if channel_id not in ALLOWED_MM_CHANNEL_IDS:
        raise ValueError(f"Mattermost post channel {channel_id} is not an allowed authorization room")
    bound_text = _authorization_message_text(post, fetch)
    name = str(name_zh or "").strip()
    addr = str(email or "").strip()
    if not name and not addr:
        raise ValueError("name_zh or email is required")
    if name and name not in bound_text and (not addr or addr.casefold() not in bound_text.casefold()):
        return None
    return {
        "authorization": "andy_mattermost_post",
        "authorizing_post_id": post_id,
        "channel_id": channel_id,
        "message_excerpt": bound_text[:240],
    }


def normalize_notification_groups(groups: list[str]) -> list[str]:
    if not isinstance(groups, list) or not groups:
        raise ValueError("notification_groups must be a non-empty list")
    if len(groups) > len(KNOWN_NOTIFICATION_GROUPS):
        raise ValueError("notification_groups has too many entries")
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in groups:
        token = str(raw or "").strip()
        if not token:
            raise ValueError("notification_groups entries must be non-empty")
        if not NOTIFICATION_TOKEN_RE.fullmatch(token):
            raise ValueError(f"notification group {token!r} is not a LookupID token (reject English labels)")
        if token not in KNOWN_NOTIFICATION_GROUPS:
            raise ValueError(f"unsupported notification group token: {token!r}")
        if token in seen:
            raise ValueError(f"duplicate notification group token: {token!r}")
        seen.add(token)
        ordered.append(token)
    return ordered


def notification_group_field_value(tokens: list[str]) -> str:
    return ", ".join(tokens)


def parse_notification_group_field(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    return {part.strip() for part in text.split(",") if part.strip()}


def _hr_subset(row: dict[str, Any]) -> dict[str, Any]:
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part1 import _appsheet_hr_employee_subset

    return _appsheet_hr_employee_subset(row)


def _settings_subset(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in sorted(SETTINGS_WRITABLE_FIELDS) if key in row or key != "PersonID"}


def _compare_email(left: Any, right: Any) -> bool:
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def build_plan(
    client: Any,
    *,
    person_id: str,
    name_zh: str,
    email: str,
    notification_groups: list[str],
    authorization: dict[str, Any] | None,
) -> dict[str, Any]:
    groups = normalize_notification_groups(notification_groups)
    selector = f'FILTER("{HR_TABLE}", [PersonID] = "{_quote(person_id)}")'
    hr_rows = client.find(HR_TABLE, selector)
    if len(hr_rows) != 1:
        raise ValueError(f"expected exactly 1 HR_Employees row for PersonID={person_id}, got {len(hr_rows)}")
    hr = hr_rows[0]
    expected_name = str(name_zh or "").strip()
    expected_email = str(email or "").strip()
    if str(hr.get("Name_ZH") or "").strip() != expected_name:
        raise ValueError(f"Name_ZH mismatch for PersonID={person_id}")
    if not _compare_email(hr.get("Company Email"), expected_email):
        raise ValueError(f"Company Email mismatch for PersonID={person_id}")
    company_email = str(hr.get("Company Email") or "").strip()
    current_appsheet_email = str(hr.get("Appsheet Email") or "").strip()
    appsheet_email_action = "unchanged"
    planned_appsheet_email = current_appsheet_email
    if not current_appsheet_email:
        planned_appsheet_email = company_email
        appsheet_email_action = "set_blank_to_company_email"
    elif _compare_email(current_appsheet_email, company_email):
        planned_appsheet_email = company_email
        appsheet_email_action = "already_matches_company_email"
    else:
        if not _compare_email(current_appsheet_email, expected_email):
            raise ValueError("Appsheet Email differs from Company Email and would not be replaced")
        appsheet_email_action = "unchanged_existing_login"
    settings_selector = f'FILTER("{SETTINGS_TABLE}", [PersonID] = "{_quote(person_id)}")'
    settings_rows = client.find(SETTINGS_TABLE, settings_selector)
    settings_exists = len(settings_rows) == 1
    settings_row = settings_rows[0] if settings_exists else {}
    group_value = notification_group_field_value(groups)
    settings_upsert: dict[str, Any] = {
        "PersonID": person_id,
        "Name_ZH": expected_name,
        "Company Email": company_email,
        "Appsheet Email": planned_appsheet_email,
        "Appsheet Notification Group": group_value,
    }
    settings_action = "edit" if settings_exists else "add"
    return {
        "table_hr": HR_TABLE,
        "table_settings": SETTINGS_TABLE,
        "person_id": person_id,
        "authorization": authorization,
        "matched_hr_row": _hr_subset(hr),
        "settings_exists": settings_exists,
        "settings_action": settings_action,
        "current_settings_row": _settings_subset(settings_row) if settings_exists else None,
        "planned_settings_row": settings_upsert,
        "notification_groups": groups,
        "appsheet_email_action": appsheet_email_action,
        "subscriber_email": planned_appsheet_email,
    }


def _load_subscribers(session: Any) -> list[dict[str, Any]]:
    url = f"https://www.appsheet.com/api/loadUsers/{APPSHEET_MANAGE_APP_ID}"
    response = session.get(url, timeout=120)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("Subscribers", "subscribers", "users", "Users"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _subscriber_present(subscribers: list[dict[str, Any]], email: str) -> bool:
    target = email.casefold()
    for row in subscribers:
        if not isinstance(row, dict):
            continue
        for key in ("Email", "email", "UserEmail"):
            if str(row.get(key) or "").strip().casefold() == target:
                return True
    return False


def _add_subscriber(session: Any, email: str) -> dict[str, Any]:
    payload = {
        "permissionForNewSubscribers": 1,
        "roleForNewSubscribers": "User",
        "sendEmail": False,
        "appId": APPSHEET_MANAGE_APP_ID,
        "app name": APPSHEET_MANAGE_APP_NAME,
        "emails": [email],
    }
    response = session.post(
        "https://www.appsheet.com/manage/SubscribeEmailsWithPermissions",
        data=payload,
        timeout=120,
    )
    return {"status_code": response.status_code, "ok": response.ok, "text_len": len(response.text or "")}


def verify_settings_readback(client: Any, person_id: str, groups: list[str]) -> dict[str, Any]:
    selector = f'FILTER("{SETTINGS_TABLE}", [PersonID] = "{_quote(person_id)}")'
    rows = client.find(SETTINGS_TABLE, selector)
    if len(rows) != 1:
        raise RuntimeError(f"settings readback expected 1 row, got {len(rows)}")
    row = rows[0]
    present = parse_notification_group_field(row.get("Appsheet Notification Group"))
    missing = [token for token in groups if token not in present]
    return {
        "verified": not missing,
        "missing_notification_groups": missing,
        "readback_subset": _settings_subset(row),
    }


def execute_appsheet_user_access(
    *,
    person_id: str,
    name_zh: str,
    email: str,
    notification_groups: list[str],
    authorizing_post_id: str,
    dry_run: bool = True,
    confirm_live_write: str = "",
    appsheet_client: Any | None = None,
    manage_session: Any | None = None,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    person_id = str(person_id or "").strip()
    if not person_id:
        raise ValueError("person_id is required")
    authorization = authorize_andy_post(
        authorizing_post_id=authorizing_post_id,
        name_zh=name_zh,
        email=email,
        post_fetcher=post_fetcher,
    )
    if authorization is None:
        return {
            "status": "denied",
            "capability": "pd_one_appsheet_user_access",
            "reason": "authorizing_post_missing_name_or_email",
            "dry_run": bool(dry_run),
            "execution": None,
        }
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import APPSHEET_ENV_FILES, APPSHEET_SCHEMA_MAP
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part1 import _load_appsheet_record_ops_module

    module = _load_appsheet_record_ops_module()
    client = appsheet_client or module.AppSheetClient(
        str(APPSHEET_ENV_FILES()["deployed"]), str(APPSHEET_SCHEMA_MAP()),
    )
    plan = build_plan(
        client,
        person_id=person_id,
        name_zh=name_zh,
        email=email,
        notification_groups=notification_groups,
        authorization=authorization,
    )
    safety = {
        "live_write_confirmation_required": LIVE_CONFIRMATION,
        "requires_andy_mattermost_post": True,
        "no_saveapp": True,
        "no_appsheet_roles_write": True,
        "readback_verification_required": True,
        "shell_used": False,
    }
    if dry_run:
        return {
            "status": "ok",
            "capability": "pd_one_appsheet_user_access",
            "dry_run": True,
            "safety": safety,
            "plan": plan,
            "execution": None,
        }
    if confirm_live_write != LIVE_CONFIRMATION:
        raise ValueError(f"live writes require confirm_live_write={LIVE_CONFIRMATION!r}")
    execution: dict[str, Any] = {}
    row = dict(plan["planned_settings_row"])
    if plan["settings_action"] == "add":
        client.add(SETTINGS_TABLE, row)
        execution["settings_write"] = "add"
    else:
        client.edit(SETTINGS_TABLE, row)
        execution["settings_write"] = "edit"
    execution["settings_readback"] = verify_settings_readback(client, person_id, plan["notification_groups"])
    if not execution["settings_readback"]["verified"]:
        return {
            "status": "error",
            "error": "readback_verification_failed",
            "capability": "pd_one_appsheet_user_access",
            "dry_run": False,
            "safety": safety,
            "plan": plan,
            "execution": execution,
        }
    session = manage_session if manage_session is not None else load_appsheet_manage_session(session_factory)
    subscribers_before = _load_subscribers(session)
    execution["subscribers_before_count"] = len(subscribers_before)
    target_email = str(plan["subscriber_email"] or "").strip()
    if _subscriber_present(subscribers_before, target_email):
        execution["subscriber_add"] = {"status": "already_present", "email": target_email}
    else:
        execution["subscriber_add"] = _add_subscriber(session, target_email)
        subscribers_after = _load_subscribers(session)
        execution["subscribers_after_count"] = len(subscribers_after)
        if not _subscriber_present(subscribers_after, target_email):
            return {
                "status": "error",
                "error": "subscriber_readback_failed",
                "capability": "pd_one_appsheet_user_access",
                "dry_run": False,
                "safety": safety,
                "plan": plan,
                "execution": execution,
            }
    return {
        "status": "ok",
        "capability": "pd_one_appsheet_user_access",
        "dry_run": False,
        "safety": safety,
        "plan": plan,
        "execution": execution,
    }