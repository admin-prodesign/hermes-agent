"""Profile-home Apps Script registry for PD One.

The four built-in projects stay in code. Employees add their own container-bound
scripts in a JSON file under the profile folder, read on every call so a
registration does not reload MCP. The requester is the bound session user.
A tool argument cannot name that person.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pd_one_ops")

REGISTER_CONFIRMATION = "RUN LIVE APPS SCRIPT REGISTER"
REGISTRY_SCHEMA = "pd-one.apps-script-registry.v1"
SCRIPT_PROJECTS_SCOPE = "https://www.googleapis.com/auth/script.projects"
DRIVE_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive",
})
ENTRY_ACTIONS = (
    "get_content",
    "verify_readback",
    "unique_text_patch",
    "staged_file_replace",
)
BUILTIN_KEYS = frozenset({
    "worker_scheduling",
    "appsheet_helper",
    "appsheet_data_mirror",
    "finance_forex_notification",
})
_AUDIT_ACTIONS = {
    "register_project": "register",
    "unique_text_patch": "patch",
    "staged_file_replace": "patch",
    "worker_scheduling_apps_script_patch": "patch",
    "verify_readback": "readback",
}
_AUDIT_RESULTS = frozenset({"dry_run", "ok", "denied", "error", "registered"})
_DENIED_DETAILS = frozenset({
    "access_denied",
    "outside_company_domain",
    "requester_not_owner_or_writer",
    "pd_one_account_no_access",
    "requester_unbound",
})
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SECRET_KEYS = frozenset({
    "refresh_token",
    "access_token",
    "client_secret",
    "id_token",
    "token",
    "secret",
})
_SCOPE_REMEDIATION = (
    "The PD One gog token must include "
    "https://www.googleapis.com/auth/script.projects and a Drive read scope "
    "(https://www.googleapis.com/auth/drive.readonly, "
    "https://www.googleapis.com/auth/drive.metadata.readonly, or "
    "https://www.googleapis.com/auth/drive). "
    "gog stores the refresh token in the OS keyring and may store scope "
    "metadata under ~/.config/gogcli. This check reads those JSON files and "
    "does not print tokens. If a scope is missing, keep the services the "
    "account already has and re-consent: "
    "gog auth add <pd_one.emails.admin> "
    "--services <existing-services>,appscript,drive "
    "--drive-scope readonly "
    "--extra-scopes https://www.googleapis.com/auth/script.projects "
    "--force-consent. "
    "Enable the Apps Script API and Google Drive API on the OAuth client "
    "first. Inspect the recorded grant with `gog auth list --json`, then run "
    "apps_script_project_ops action check_gog_scopes."
)


class RegistryUnreadable(ValueError):
    """The profile registry exists but is not a usable JSON document."""


def registry_path() -> Path:
    """Profile data, not the release tree. Resolved when the call happens."""
    from tools.pd_one_ops.site_config import profile_root

    return Path(profile_root() / "pd-one" / "apps-script-registry.json")


def audit_path() -> Path:
    from tools.pd_one_ops.site_config import profile_root

    return Path(profile_root() / "pd-one" / "apps-script-audit.jsonl")


def gogcli_config_dir() -> Path:
    from tools.pd_one_ops.site_config import resolve_configured_path

    return Path(resolve_configured_path("~/.config/gogcli"))


def merge_profile_registry(builtins: dict[str, Any]) -> dict[str, Any]:
    """Built-in keys win. A corrupt registry leaves the built-ins usable."""
    merged = {
        key: dict(value)
        for key, value in builtins.items()
        if isinstance(value, dict)
    }
    try:
        extra = _registry_projects()
    except RegistryUnreadable:
        logger.exception("pd one apps script registry unreadable")
        return merged
    for key, project in extra.items():
        if key in merged or not isinstance(project, dict):
            continue
        if not project.get("registered_by") or not project.get("script_id"):
            continue
        merged[key] = dict(project)
    return merged


def project_is_visible(project: dict[str, Any]) -> bool:
    """Built-ins stay shared. A self-registered row is the registrar or an admin."""
    owner = str(project.get("registered_by") or "").strip()
    if not owner:
        return True
    requester = bound_requester()
    if not requester["user_id"]:
        return False
    if requester["user_id"] == owner:
        return True
    return bool(requester["is_admin"])


def assert_project_visible(project: dict[str, Any]) -> None:
    if not project_is_visible(project):
        raise ValueError("access_denied")


def visible_project_keys(projects: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key, project in projects.items()
        if isinstance(project, dict) and project_is_visible(project)
    )


def register_apps_script_project(
    *,
    project_key: str,
    script_id: str,
    parent_file_id: str,
    dry_run: bool,
    confirm_live_register: str | None,
) -> dict[str, Any]:
    """Dry-run unless confirm_live_register is the register phrase.

    Identity, domain, and Drive writer checks all run before a dry-run plan
    is returned. Nothing is written until the live phrase matches.
    """
    requester = _require_session_user()
    emails = company_principal_emails(requester)
    key = _validate_key(project_key)
    _reject_builtin_key(key)
    script = _validate_optional_id(script_id, "invalid_script_id")
    parent = _validate_optional_id(parent_file_id, "invalid_parent_file_id")
    if not script and not parent:
        raise ValueError("script_id or parent_file_id is required")
    binding = resolve_apps_script_binding(
        script_id=script,
        parent_file_id=parent,
        account=_admin_account(),
    )
    if not binding.get("pd_one_account_access"):
        raise ValueError("pd_one_account_no_access")
    if not requester_is_owner_or_writer(emails, binding.get("permissions") or []):
        raise ValueError("requester_not_owner_or_writer")
    _reject_key_taken(key, requester["user_id"])
    plan = _registration_plan(key, binding, requester["user_id"], dry_run=True)
    if dry_run:
        return plan
    if confirm_live_register != REGISTER_CONFIRMATION:
        raise ValueError(
            "live Apps Script registration requires "
            f"confirm_live_register={REGISTER_CONFIRMATION!r}"
        )
    _store_registration(key, binding, requester["user_id"])
    plan["dry_run"] = False
    plan["written"] = True
    return plan


def resolve_apps_script_binding(
    *,
    script_id: str,
    parent_file_id: str,
    account: str,
) -> dict[str, Any]:
    """Resolve script id and container, then read the container as the PD One account."""
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import (
        _google_access_token,
        _google_api_json,
    )

    token = _google_access_token(account)
    script_id, parent_file_id, title = _resolve_ids(
        script_id, parent_file_id, token, _google_api_json,
    )
    _require_drive_file(parent_file_id, token, _google_api_json)
    permissions = _list_permissions(parent_file_id, token, _google_api_json)
    return {
        "script_id": script_id,
        "parent_file_id": parent_file_id,
        "title": title,
        "permissions": permissions,
        "pd_one_account_access": True,
    }


def requester_is_owner_or_writer(emails: set[str], permissions: list[Any]) -> bool:
    from tools.pd_one_ops.drive_acl_common import (
        access_for_role,
        expanded_members,
        normalize_email,
    )

    groups = _group_cache()
    for perm in permissions:
        if not isinstance(perm, dict):
            continue
        if access_for_role(perm.get("role")) != "write":
            continue
        principal = normalize_email(perm.get("emailAddress") or perm.get("email"))
        if not principal:
            continue
        kind = str(perm.get("type") or "user").lower()
        if kind == "user" and principal in emails:
            return True
        if kind == "group" and groups is not None and emails & expanded_members(groups, principal):
            return True
    return False


def bound_requester() -> dict[str, Any]:
    """Session user id plus policy-cache emails and admin role.

    ``HERMES_SESSION_*`` environment values are ignored. They are writable
    from a terminal inside the turn.
    """
    from gateway.session_context import bound_session_value

    user_id = str(bound_session_value("HERMES_SESSION_USER_ID") or "").strip()
    policy = _load_policy(user_id) if user_id else None
    return {
        "user_id": user_id,
        "emails": _policy_emails(policy),
        "is_admin": _policy_is_admin(policy),
    }


def company_domain() -> str:
    from tools.pd_one_ops.drive_acl_common import normalize_email
    from tools.pd_one_ops.site_config import site_text

    admin = normalize_email(site_text("PDONE_EMAIL_ADMIN"))
    if "@" not in admin:
        return ""
    return admin.rsplit("@", 1)[1]


def company_principal_emails(requester: dict[str, Any]) -> set[str]:
    domain = company_domain()
    if not domain:
        raise ValueError("company_domain_unconfigured")
    matched = {
        email for email in requester["emails"]
        if str(email).rsplit("@", 1)[-1] == domain
    }
    if not matched:
        raise ValueError("outside_company_domain")
    return matched


def gog_token_scope_report(config_dir: Path | None = None) -> dict[str, Any]:
    """Report whether local gogcli JSON records the required scopes.

    The refresh token itself usually lives in the OS keyring. Scope metadata
    that gog wrote under the config directory is what this can see. Token
    material is not copied into the report.
    """
    root = Path(config_dir) if config_dir is not None else gogcli_config_dir()
    scopes = _collect_scopes(root)
    has_script = SCRIPT_PROJECTS_SCOPE in scopes
    has_drive = bool(scopes & DRIVE_READ_SCOPES)
    if has_script and has_drive:
        status = "ok"
    elif scopes:
        status = "missing_scopes"
    else:
        status = "scopes_not_found"
    return {
        "status": status,
        "config_dir": str(root),
        "has_script_projects": has_script,
        "has_drive_read": has_drive,
        "scope_count": len(scopes),
        "remediation": _SCOPE_REMEDIATION,
    }


def note_result(action_key: str, result: dict[str, Any]) -> None:
    audit_apps_script(
        action_key,
        script_id=_result_script_id(result),
        outcome=_result_outcome(action_key, result),
    )


def note_error(action_key: str, project_key: str, script_id: str, exc: BaseException) -> None:
    resolved = script_id or known_script_id(project_key)
    audit_apps_script(action_key, script_id=resolved, outcome=exception_outcome(exc))


def exception_outcome(exc: BaseException) -> str:
    if str(exc) in _DENIED_DETAILS:
        return "denied"
    return "error"


def known_script_id(project_key: str) -> str:
    if not project_key:
        return ""
    from tools.pd_one_ops.pd_one_safe_ops_mcp_part0 import APPS_SCRIPT_ALLOWED_PROJECTS

    project = APPS_SCRIPT_ALLOWED_PROJECTS().get(project_key) or {}
    if not isinstance(project, dict):
        return ""
    return _audit_text(project.get("script_id"))


def audit_apps_script(action_key: str, *, script_id: str, outcome: str) -> None:
    kind = _AUDIT_ACTIONS.get(action_key)
    if kind is None:
        return
    record = {
        "who": _audit_text(bound_requester()["user_id"]),
        "at": _utc_now(),
        "script_id": _audit_text(script_id),
        "action": kind,
        "result": outcome if outcome in _AUDIT_RESULTS else "error",
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    path = audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            _flock(handle)
            handle.write(line)
            handle.flush()
        os.chmod(path, 0o600)
    except OSError:
        logger.exception("pd one apps script audit write failed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _audit_text(value: Any) -> str:
    return str(value or "").replace("\n", "").replace("\r", "")[:128]


def _result_script_id(result: dict[str, Any]) -> str:
    for key in ("script_id",):
        if result.get(key):
            return str(result[key])
    project = result.get("project")
    if isinstance(project, dict) and project.get("script_id"):
        return str(project["script_id"])
    plan = result.get("plan")
    if isinstance(plan, dict) and plan.get("script_id"):
        return str(plan["script_id"])
    return ""


def _result_outcome(action_key: str, result: dict[str, Any]) -> str:
    if result.get("status") != "ok":
        return "error"
    if action_key == "register_project":
        return "dry_run" if result.get("dry_run") else "registered"
    if action_key in _AUDIT_ACTIONS and result.get("dry_run") and action_key != "verify_readback":
        return "dry_run"
    return "ok"


def _require_session_user() -> dict[str, Any]:
    requester = bound_requester()
    if not requester["user_id"]:
        raise ValueError("requester_unbound")
    return requester


def _admin_account() -> str:
    from tools.pd_one_ops.site_config import site_text

    account = site_text("PDONE_EMAIL_ADMIN").strip()
    if not account:
        raise ValueError("company_domain_unconfigured")
    return account


def _validate_key(project_key: str) -> str:
    key = str(project_key or "").strip()
    if not _KEY_RE.fullmatch(key):
        raise ValueError("invalid_project_key")
    return key


def _validate_optional_id(value: str, code: str) -> str:
    text = str(value or "").strip()
    if text and not _ID_RE.fullmatch(text):
        raise ValueError(code)
    return text


def _reject_builtin_key(key: str) -> None:
    if key in BUILTIN_KEYS:
        raise ValueError("project_key_reserved")


def _reject_key_taken(key: str, user_id: str) -> None:
    try:
        projects = _registry_projects()
    except RegistryUnreadable:
        raise
    existing = projects.get(key)
    if not isinstance(existing, dict):
        return
    owner = str(existing.get("registered_by") or "").strip()
    if owner and owner != user_id:
        raise ValueError("project_key_taken")


def _registration_plan(
    key: str,
    binding: dict[str, Any],
    user_id: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "action": "register_project",
        "dry_run": dry_run,
        "written": False,
        "project_key": key,
        "script_id": binding["script_id"],
        "parent_file_id": binding["parent_file_id"],
        "title": binding.get("title") or "",
        "registered_by": user_id,
        "pd_one_account_access": True,
        "requester_access": "owner_or_writer",
        "safety": {
            "requester_from_session": True,
            "model_requester_ignored": True,
            "company_domain_required": True,
            "live_confirmation_required": REGISTER_CONFIRMATION,
        },
    }


def _store_registration(key: str, binding: dict[str, Any], user_id: str) -> None:
    entry = {
        "script_id": binding["script_id"],
        "parent_file_id": binding["parent_file_id"],
        "spreadsheet_id": binding["parent_file_id"],
        "account": _admin_account(),
        "title": str(binding.get("title") or "")[:200],
        "system": "employee_registered",
        "allowed_actions": list(ENTRY_ACTIONS),
        "registered_by": user_id,
        "registered_at": _utc_now(),
    }

    def _mutate(document: dict[str, Any]) -> None:
        projects = document.setdefault("projects", {})
        if not isinstance(projects, dict):
            raise RegistryUnreadable("registry_unreadable")
        projects[key] = entry

    _locked_update(_mutate)


def _read_document() -> dict[str, Any]:
    path = registry_path()
    if not path.is_file():
        return {"schema": REGISTRY_SCHEMA, "projects": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryUnreadable("registry_unreadable") from exc
    if not isinstance(data, dict):
        raise RegistryUnreadable("registry_unreadable")
    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        raise RegistryUnreadable("registry_unreadable")
    data["projects"] = projects
    data.setdefault("schema", REGISTRY_SCHEMA)
    return data


def _registry_projects() -> dict[str, Any]:
    projects = _read_document()["projects"]
    return projects if isinstance(projects, dict) else {}


def _locked_update(mutator: Any) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a", encoding="utf-8") as lock:
        _flock(lock)
        document = _read_document()
        mutator(document)
        _atomic_json(path, document)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _flock(handle: Any) -> None:
    try:
        import fcntl
    except ImportError:
        return
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _load_policy(user_id: str) -> dict[str, Any] | None:
    from tools.pd_one_safe_ops import load_user_policy

    policy = load_user_policy(user_id)
    return policy if isinstance(policy, dict) else None


def _policy_emails(policy: dict[str, Any] | None) -> set[str]:
    from tools.pd_one_ops.drive_acl_common import normalize_email

    if not isinstance(policy, dict):
        return set()
    blobs = [policy]
    identity = policy.get("identity")
    if isinstance(identity, dict):
        blobs.append(identity)
    found: list[Any] = []
    for blob in blobs:
        for key in ("companyEmails", "googleAccountEmails", "companyEmail", "email"):
            value = blob.get(key)
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, list):
                found.extend(value)
    return {email for email in (normalize_email(item) for item in found) if email}


def _policy_is_admin(policy: dict[str, Any] | None) -> bool:
    if not isinstance(policy, dict):
        return False
    if policy.get("found") is False or policy.get("active") is False:
        return False
    tokens: set[str] = set()
    for key in ("roles", "safeScopes"):
        value = policy.get(key)
        if isinstance(value, str):
            parts = value.split(",")
        elif isinstance(value, (list, tuple)):
            parts = value
        else:
            continue
        tokens.update(str(part).strip().lower() for part in parts if str(part).strip())
    return "admin" in tokens


def _group_cache() -> dict[str, Any] | None:
    """Missing group cache still allows a direct owner/writer ACE."""
    try:
        from tools.pd_one_ops.drive_acl_common import load_group_v1_cache

        return load_group_v1_cache()
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _resolve_ids(script_id: str, parent_file_id: str, token: str, api: Any) -> tuple[str, str, str]:
    title = ""
    if script_id:
        meta = api(
            "https://script.googleapis.com/v1/projects/" + urllib.parse.quote(script_id),
            token=token,
        )
        if not isinstance(meta, dict):
            raise ValueError("pd_one_account_no_access")
        resolved_parent = str(meta.get("parentId") or "")
        title = str(meta.get("title") or "")
        parent_file_id = _same_parent(parent_file_id, resolved_parent)
    else:
        script_id, title = _script_child(parent_file_id, token, api)
    if not _ID_RE.fullmatch(script_id) or not _ID_RE.fullmatch(parent_file_id):
        raise ValueError("pd_one_account_no_access")
    return script_id, parent_file_id, title


def _same_parent(requested: str, resolved: str) -> str:
    if requested and resolved and requested != resolved:
        raise ValueError("script_parent_mismatch")
    parent = requested or resolved
    if not parent:
        raise ValueError("standalone_script_has_no_parent")
    return parent


def _script_child(parent_file_id: str, token: str, api: Any) -> tuple[str, str]:
    query = urllib.parse.urlencode({
        "q": (
            f"'{parent_file_id}' in parents and "
            "mimeType='application/vnd.google-apps.script' and trashed=false"
        ),
        "fields": "files(id,name)",
        "supportsAllDrives": "true",
        "pageSize": "10",
    })
    listed = api("https://www.googleapis.com/drive/v3/files?" + query, token=token)
    files = [
        item for item in (listed.get("files") or [])
        if isinstance(item, dict) and item.get("id")
    ]
    if len(files) != 1:
        raise ValueError("container_script_not_unique")
    return str(files[0]["id"]), str(files[0].get("name") or "")


def _require_drive_file(parent_file_id: str, token: str, api: Any) -> None:
    url = (
        "https://www.googleapis.com/drive/v3/files/"
        + urllib.parse.quote(parent_file_id)
        + "?supportsAllDrives=true&fields=id,name"
    )
    try:
        parent = api(url, token=token)
    except (OSError, RuntimeError) as exc:
        raise ValueError("pd_one_account_no_access") from exc
    if not isinstance(parent, dict) or not parent.get("id"):
        raise ValueError("pd_one_account_no_access")


def _list_permissions(parent_file_id: str, token: str, api: Any) -> list[dict[str, Any]]:
    perms: list[dict[str, Any]] = []
    page = ""
    for _ in range(5):
        params = {
            "supportsAllDrives": "true",
            "pageSize": "100",
            "fields": "nextPageToken,permissions(type,role,emailAddress)",
        }
        if page:
            params["pageToken"] = page
        url = (
            "https://www.googleapis.com/drive/v3/files/"
            + urllib.parse.quote(parent_file_id)
            + "/permissions?"
            + urllib.parse.urlencode(params)
        )
        try:
            payload = api(url, token=token)
        except (OSError, RuntimeError) as exc:
            raise ValueError("pd_one_account_no_access") from exc
        if not isinstance(payload, dict):
            raise ValueError("pd_one_account_no_access")
        perms.extend(
            row for row in (payload.get("permissions") or []) if isinstance(row, dict)
        )
        page = str(payload.get("nextPageToken") or "")
        if not page:
            break
    return perms


def _collect_scopes(root: Path) -> set[str]:
    found: set[str] = set()
    if not root.is_dir():
        return found
    seen = 0
    for path in root.rglob("*.json"):
        seen += 1
        if seen > 200:
            break
        if path.is_symlink() or not path.is_file():
            continue
        if "credential" in path.name.lower():
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        _collect_scope_values(data, found)
    return found


def _collect_scope_values(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"scope", "scopes"}:
                _add_scope_text(item, found)
            elif lowered not in _SECRET_KEYS:
                _collect_scope_values(item, found)
        return
    if isinstance(value, list):
        for item in value:
            _collect_scope_values(item, found)


def _add_scope_text(value: Any, found: set[str]) -> None:
    if isinstance(value, str):
        for piece in value.replace(",", " ").split():
            if piece.startswith("https://"):
                found.add(piece)
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.startswith("https://"):
                found.add(item)
