#!/usr/bin/env python3
"""Ticket-gated AppSheet editor definition inspect/apply for PD One safe-ops."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any, Callable

from tools.pd_one_ops.site_config import profile_root, resolve_configured_path

DEFAULT_APP_ID = "f2073120-8c2e-4930-b13c-105838c5e4c3"
DEFAULT_APP_NAME = "prodesign-group-1163872-25-01-09"
TICKET_RE = re.compile(r"^PDAPP-\d{8}-[A-F0-9]{8}$")
MATTERMOST_POST_ID_RE = re.compile(r"^[a-z0-9]{26}$")
LIVE_CONFIRMATION = "RUN LIVE APPSHEET DEFINITION APPLY"
TICKET_CAPABILITY = "appsheet_definition_apply"
APPSHEET_VENV_PY = Path(
    resolve_configured_path(
        "~/.hermes/profiles/pdone/legacy-openclaw/workspace/ops/venvs/"
        "venv-appsheet-doc/bin/python"
    )
)


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "error": message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)


def emit(payload: dict[str, Any]) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload

    payload = guard_hr_payload(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _reexec_into_appsheet_venv() -> None:
    try:
        import browser_cookie3
        return
    except ImportError:
        pass
    if os.environ.get("PD_ONE_APPSHEET_REEXEC") == "1" or not APPSHEET_VENV_PY.is_file():
        return
    os.environ["PD_ONE_APPSHEET_REEXEC"] = "1"
    os.execv(str(APPSHEET_VENV_PY), [str(APPSHEET_VENV_PY), os.path.abspath(__file__), *sys.argv[1:]])


def _browser_cookie_files_readable(cookie_file: Path, key_file: Path) -> bool:
    try:
        return os.access(cookie_file, os.R_OK) and os.access(key_file, os.R_OK)
    except OSError:
        return False


def editor_cookie_paths() -> tuple[Path, Path]:
    desktop_cookie = Path(
        resolve_configured_path("~/.hermes/browser-profiles/pdone-desktop/Default/Cookies")
    )
    desktop_key = Path(
        resolve_configured_path("~/.hermes/browser-profiles/pdone-desktop/Local State")
    )
    legacy_cookie = Path(
        resolve_configured_path(
            "~/.hermes/profiles/pdone/legacy-openclaw/browser/openclaw/user-data/Default/Cookies"
        )
    )
    legacy_key = Path(
        resolve_configured_path(
            "~/.hermes/profiles/pdone/legacy-openclaw/browser/openclaw/user-data/Local State"
        )
    )
    if _browser_cookie_files_readable(desktop_cookie, desktop_key):
        return desktop_cookie, desktop_key
    return legacy_cookie, legacy_key


def definitions_root(app_id: str) -> Path:
    root = profile_root() / "legacy-openclaw/workspace/data/appsheet-definitions" / app_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def receipts_root() -> Path:
    root = profile_root() / "logs/appsheet-definition-ops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def allowed_staging_roots() -> list[Path]:
    base = Path(profile_root()).resolve()
    return [
        (base / "cache").resolve(),
        (base / "cache/scratch").resolve(),
        definitions_root(DEFAULT_APP_ID).resolve(),
        receipts_root().resolve(),
    ]


def resolve_allowed_path(raw: str, *, label: str) -> Path:
    text = str(raw or "").strip()
    if not text:
        fail(f"{label} is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    for root in allowed_staging_roots():
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    fail(f"{label} must live under PD One cache, scratch, definition snapshots, or ops receipts")


def parse_app(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("app") if "app" in payload else payload.get("App")
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    raise RuntimeError("loadApp response missing app JSON")


def wrapper_flags(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("Success", "ErrorDescription", "IsValid", "IsRunnable", "Warnings", "AppErrors"):
        if key in payload and key != "AppErrors":
            value = payload.get(key)
            if not isinstance(value, (dict, list)) or (isinstance(value, list) and len(value) < 20):
                out[key] = value
    errors = payload.get("AppErrors") or payload.get("appErrors") or {}
    if isinstance(errors, dict):
        items = errors.get("Errors") or []
        out["wrapper_error_count"] = len(items)
        out["wrapper_errors"] = [
            str(item.get("Message") or item.get("Error") or item)[:240]
            for item in items[:8]
            if isinstance(item, dict) or item
        ]
    return out


def validity(app: dict[str, Any]) -> dict[str, Any]:
    return {
        key: app.get(key)
        for key in (
            "Version",
            "StableVersion",
            "PercentOnLatestVersion",
            "IsValid",
            "IsRunnable",
            "IsDeployable",
            "LastModified",
        )
    }


def structure_counts(app: dict[str, Any]) -> dict[str, int]:
    app_data = app.get("AppData") if isinstance(app.get("AppData"), dict) else {}
    presentation = app.get("Presentation") if isinstance(app.get("Presentation"), dict) else {}
    schemas = app_data.get("DataSchemas") if isinstance(app_data.get("DataSchemas"), list) else []
    slices = app_data.get("TableSlices") if isinstance(app_data.get("TableSlices"), list) else []
    controls = presentation.get("Controls") if isinstance(presentation.get("Controls"), list) else []
    return {
        "data_schemas": len(schemas),
        "table_slices": len(slices),
        "presentation_controls": len(controls),
    }


def app_json_sha256(app: dict[str, Any]) -> str:
    blob = json.dumps(app, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class EditorClient:
    """AppSheet editor HTTP client using Chromium cookie session."""

    def __init__(self, session: Any, *, app_id: str, app_name: str) -> None:
        self._session = session
        self.app_id = app_id
        self.app_name = app_name

    @classmethod
    def from_cookie_files(cls, cookie_file: Path, key_file: Path, *, app_id: str, app_name: str) -> EditorClient:
        from tools.environments.dbus_session_env import ensure_user_dbus_session_in_environ

        ensure_user_dbus_session_in_environ()
        import browser_cookie3
        import requests

        jar = browser_cookie3.Chromium(
            cookie_file=str(cookie_file), key_file=str(key_file), domain_name="appsheet.com"
        ).load()
        if len(jar) == 0:
            raise RuntimeError(f"No AppSheet cookies in {cookie_file}")
        session = requests.Session()
        session.cookies.update(jar)
        return cls(session, app_id=app_id, app_name=app_name)

    def load_app(self, version: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
        url = (
            f"https://www.appsheet.com/api/loadApp/{self.app_name}"
            f"?version={version}&checkConsistency=true&useUpdatedWarningText=false"
        )
        response = self._session.get(url, timeout=600, headers={"Accept": "application/json"})
        if response.status_code == 401:
            raise RuntimeError(
                "AppSheet editor session is unauthorized (HTTP 401). "
                "Sign in to the AppSheet editor in the desktop Chrome profile "
                "(~/.hermes/browser-profiles/pdone-desktop) and retry."
            )
        response.raise_for_status()
        payload = response.json()
        return payload, parse_app(payload)

    def save_app(self, app: dict[str, Any]) -> dict[str, Any]:
        body = gzip.compress(
            json.dumps(
                {
                    "appId": self.app_id,
                    "appJson": json.dumps(app, ensure_ascii=False, separators=(",", ":")),
                    "validate": True,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Encoding": "gzip",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.appsheet.com",
            "Referer": f"https://www.appsheet.com/template/appdef?appId={self.app_id}",
        }
        response = self._session.post(
            "https://www.appsheet.com/api/saveapp", data=body, headers=headers, timeout=600
        )
        text = response.text
        try:
            parsed = response.json()
        except Exception:
            parsed = {"raw_text": text[:4000]}
        summary = {
            "status_code": response.status_code,
            "success": parsed.get("Success") if isinstance(parsed, dict) else None,
            "error": parsed.get("ErrorDescription") if isinstance(parsed, dict) else None,
            "text_len": len(text),
            "wrapper": wrapper_flags(parsed) if isinstance(parsed, dict) else {},
        }
        if response.status_code >= 400 or (
            isinstance(parsed, dict) and parsed.get("Success") is False
        ):
            raise RuntimeError(f"saveapp failed: {summary}")
        return summary

    def promote_stable(self, version: str) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.appsheet.com",
            "Referer": f"https://www.appsheet.com/template/appdef?appId={self.app_id}",
        }
        response = self._session.post(
            "https://www.appsheet.com/Manage/SetStableVersion",
            data={"appId": self.app_id, "version": version, "percentOnLatestVersion": "0"},
            headers=headers,
            timeout=240,
        )
        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text[:2000]}
        ok = response.status_code < 400 and not (
            isinstance(body, dict) and body.get("Success") is False
        )
        return {"ok": ok, "status_code": response.status_code, "response": body}


def load_patch_envelope(path: Path) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"patch envelope is not readable JSON: {exc}")
    if not isinstance(envelope, dict):
        fail("patch envelope must be a JSON object")
    patch_id = str(envelope.get("patch_id") or "").strip()
    app_id = str(envelope.get("app_id") or DEFAULT_APP_ID).strip()
    app_name = str(envelope.get("app_name") or DEFAULT_APP_NAME).strip()
    proposed_path = resolve_allowed_path(str(envelope.get("proposed_app_path") or ""), label="proposed_app_path")
    if not patch_id or len(patch_id) > 120 or not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$", patch_id):
        fail("patch_id must be a bounded identifier")
    return {
        "patch_id": patch_id,
        "app_id": app_id,
        "app_name": app_name,
        "proposed_app_path": proposed_path,
        "promote_stable": bool(envelope.get("promote_stable")),
        "change_summary": envelope.get("change_summary") if isinstance(envelope.get("change_summary"), list) else [],
        "proposed_app_sha256": str(envelope.get("proposed_app_sha256") or "").strip(),
    }


def load_proposed_app(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"proposed app JSON is not readable: {exc}")
    if not isinstance(data, dict):
        fail("proposed app JSON must be an object")
    return data


def andy_origin_user_id() -> str:
    from tools.pd_one_ops.pd_one_safe_ops_part0 import DEFAULT_ANDY_USER_ID

    configured = str(DEFAULT_ANDY_USER_ID() or "").strip()
    return configured or "5nak6m7nmf8kudbrwbtccazbgc"


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def post_asks_for_definition_changes(message: str, change_summary: list[Any]) -> bool:
    normalized_message = _normalize_match_text(message)
    if not normalized_message:
        return False
    items = [str(item or "").strip() for item in change_summary if str(item or "").strip()]
    if not items:
        return False
    return all(_normalize_match_text(item) in normalized_message for item in items)


def authorize_andy_origin_post(
    *,
    requester_user_id: str,
    origin_post_id: str,
    change_summary: list[Any],
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    andy_id = andy_origin_user_id()
    requester = str(requester_user_id or "").strip()
    if requester != andy_id:
        fail("live AppSheet definition apply origin authorization requires Andy requester_user_id")
    post_id = str(origin_post_id or "").strip()
    if not MATTERMOST_POST_ID_RE.fullmatch(post_id):
        fail(f"invalid Mattermost origin_post_id: {origin_post_id!r}")
    if post_fetcher is not None:
        post = post_fetcher(post_id)
        if not isinstance(post, dict):
            fail(f"origin post {post_id} could not be re-fetched for authorization")
    else:
        from tools.pd_one_ops.pd_one_safe_ops_part1 import _mattermost_lookup_get, mattermost_context

        base, headers, _me = mattermost_context()
        receipt, post = _mattermost_lookup_get(base, headers, f"/api/v4/posts/{post_id}")
        if receipt.get("status") != 200 or not post:
            fail(f"origin post {post_id} could not be re-fetched for authorization")
    if str(post.get("user_id") or "") != andy_id:
        fail("origin post sender does not match Andy requester_user_id")
    if int(post.get("delete_at") or 0):
        fail(f"origin post {post_id} is deleted")
    message = str(post.get("message") or "")
    if not post_asks_for_definition_changes(message, change_summary):
        fail("origin post message does not request the patch envelope change_summary")
    return {
        "authorization": "andy_origin_post",
        "origin_post_id": post_id,
        "requester_user_id": requester,
        "message_excerpt": message[:240],
    }


def authorize_live_apply(
    *,
    ticket_id: str,
    requester_user_id: str,
    origin_post_id: str,
    patch_id: str,
    app_id: str,
    change_summary: list[Any],
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ticket = str(ticket_id or "").strip()
    requester = str(requester_user_id or "").strip()
    post_id = str(origin_post_id or "").strip()
    if ticket:
        bound = authorize_ticket(ticket, patch_id=patch_id, app_id=app_id)
        return {"authorization": "pdapp_ticket", "ticket_id": bound.get("ticket_id") or ticket}
    if requester and post_id:
        origin = authorize_andy_origin_post(
            requester_user_id=requester,
            origin_post_id=post_id,
            change_summary=change_summary,
            post_fetcher=post_fetcher,
        )
        return origin
    if requester or post_id:
        fail("live AppSheet definition apply requires both requester_user_id and origin_post_id")
    fail("live AppSheet definition apply requires ticket_id or Andy origin_post authorization")


def authorize_ticket(ticket_id: str, *, patch_id: str, app_id: str) -> dict[str, Any]:
    if not TICKET_RE.fullmatch(ticket_id):
        fail("ticket_id must look like PDAPP-YYYYMMDD-XXXXXXXX")
    ledger_tools = profile_root() / "legacy-openclaw/workspace/tools"
    ledger_path = str(ledger_tools)
    if ledger_path not in sys.path:
        sys.path.append(ledger_path)
    from admin_approval_tickets import ApprovalLedger

    ticket = ApprovalLedger().get(ticket_id)
    grant = ticket.get("approval_grant") or {}
    caps = set(grant.get("allowed_capabilities") or [])
    if ticket.get("status") not in {"approved", "queued", "in_progress"}:
        fail(f"ticket {ticket_id} is not executable: {ticket.get('status')}")
    if grant.get("status") != "active" or TICKET_CAPABILITY not in caps:
        fail(f"ticket {ticket_id} grant does not include {TICKET_CAPABILITY}")
    bound = " ".join(
        [
            json.dumps(ticket.get("implementation_plan") or {}, ensure_ascii=False),
            str(ticket.get("requested_action") or ""),
            json.dumps(ticket.get("bound_resources") or [], ensure_ascii=False),
        ]
    ).lower()
    if patch_id.lower() not in bound or app_id.lower() not in bound:
        fail("ticket bound scope does not include the exact patch_id and app_id")
    return ticket


def write_snapshot(app_id: str, patch_id: str, label: str, app: dict[str, Any]) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = definitions_root(app_id) / f"{stamp}-{label}-{patch_id}.json"
    path.write_text(json.dumps(app, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return str(path)


def inspect_definition(
    *,
    app_id: str = DEFAULT_APP_ID,
    app_name: str = DEFAULT_APP_NAME,
    version: str = "",
    client_factory: Callable[..., EditorClient] | None = None,
) -> dict[str, Any]:
    app_id = str(app_id or DEFAULT_APP_ID).strip()
    app_name = str(app_name or DEFAULT_APP_NAME).strip()
    version = str(version or "").strip()
    cookie_file, key_file = editor_cookie_paths()
    factory = client_factory or (
        lambda: EditorClient.from_cookie_files(cookie_file, key_file, app_id=app_id, app_name=app_name)
    )
    client = factory()
    payload, app = client.load_app(version)
    stable_version = str(app.get("StableVersion") or "")
    stable_payload: dict[str, Any] | None = None
    stable_app: dict[str, Any] | None = None
    if stable_version and stable_version != str(app.get("Version") or ""):
        stable_payload, stable_app = client.load_app(stable_version)
    result: dict[str, Any] = {
        "status": "ok",
        "capability": "pd_one_appsheet_definition_inspect",
        "app_id": app_id,
        "app_name": app_name,
        "version_requested": version or "latest",
        "latest": validity(app),
        "latest_structure": structure_counts(app),
        "latest_wrapper": wrapper_flags(payload),
        "latest_app_sha256": app_json_sha256(app),
        "definitions_dir": str(definitions_root(app_id)),
        "safety": {"read_only": True, "editor_writes": False, "shell_used": False},
    }
    if stable_app is not None and stable_payload is not None:
        result["stable"] = validity(stable_app)
        result["stable_structure"] = structure_counts(stable_app)
        result["stable_wrapper"] = wrapper_flags(stable_payload)
        result["stable_app_sha256"] = app_json_sha256(stable_app)
    return result


def apply_definition(
    *,
    patch_envelope_path: str,
    dry_run: bool = True,
    ticket_id: str = "",
    requester_user_id: str = "",
    origin_post_id: str = "",
    confirm_live_write: str = "",
    client_factory: Callable[..., EditorClient] | None = None,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    envelope_path = resolve_allowed_path(patch_envelope_path, label="patch_envelope_path")
    envelope = load_patch_envelope(envelope_path)
    proposed = load_proposed_app(envelope["proposed_app_path"])
    proposed_sha = app_json_sha256(proposed)
    if envelope["proposed_app_sha256"] and envelope["proposed_app_sha256"] != proposed_sha:
        fail("proposed_app_sha256 does not match proposed_app_path contents")
    cookie_file, key_file = editor_cookie_paths()
    factory = client_factory or (
        lambda: EditorClient.from_cookie_files(
            cookie_file, key_file, app_id=envelope["app_id"], app_name=envelope["app_name"]
        )
    )
    client = factory()
    _before_payload, before_app = client.load_app("")
    before_sha = app_json_sha256(before_app)
    plan = {
        "patch_id": envelope["patch_id"],
        "app_id": envelope["app_id"],
        "app_name": envelope["app_name"],
        "before_version": before_app.get("Version"),
        "before_sha256": before_sha,
        "proposed_sha256": proposed_sha,
        "proposed_structure": structure_counts(proposed),
        "before_structure": structure_counts(before_app),
        "change_summary": envelope["change_summary"],
        "promote_stable": envelope["promote_stable"],
        "would_change": proposed_sha != before_sha,
    }
    receipt: dict[str, Any] = {
        "status": "ok",
        "capability": "pd_one_appsheet_definition_apply_approved",
        "mode": "dry-run" if dry_run else "live",
        "patch_envelope_path": str(envelope_path),
        "plan": plan,
        "readback_required": True,
        "safety": {
            "admin_ticket_or_andy_origin_post_required_for_live": True,
            "live_write_confirmation_required": LIVE_CONFIRMATION,
            "snapshot_before_save": True,
            "rollback_on_failure": True,
            "shell_used": False,
        },
    }
    if dry_run:
        receipt["writes"] = False
        return receipt
    if confirm_live_write != LIVE_CONFIRMATION:
        fail(f"live apply requires --confirm-live-write {LIVE_CONFIRMATION!r}")
    auth = authorize_live_apply(
        ticket_id=ticket_id,
        requester_user_id=requester_user_id,
        origin_post_id=origin_post_id,
        patch_id=envelope["patch_id"],
        app_id=envelope["app_id"],
        change_summary=envelope["change_summary"],
        post_fetcher=post_fetcher,
    )
    receipt["authorization"] = auth
    auth_ticket_id = auth.get("ticket_id")
    if auth_ticket_id:
        receipt["ticket_id"] = auth_ticket_id
    elif auth.get("origin_post_id"):
        receipt["origin_post_id"] = auth["origin_post_id"]
        receipt["requester_user_id"] = auth.get("requester_user_id")
    if not plan["would_change"]:
        receipt.update(
            {
                "writes": False,
                "execution": {
                    "status": "noop",
                    "verified": True,
                    "ticket_id": auth_ticket_id,
                    "origin_post_id": auth.get("origin_post_id"),
                },
            }
        )
        return receipt
    snapshot_path = write_snapshot(envelope["app_id"], envelope["patch_id"], "pre", before_app)
    receipt["snapshot_before_path"] = snapshot_path
    rollback_path: str | None = None
    try:
        save_summary = client.save_app(proposed)
        after_payload, after_app = client.load_app("")
        after_sha = app_json_sha256(after_app)
        verified = after_sha == proposed_sha
        execution: dict[str, Any] = {
            "save": save_summary,
            "after_version": after_app.get("Version"),
            "after_validity": validity(after_app),
            "after_wrapper": wrapper_flags(after_payload),
            "after_sha256": after_sha,
            "verified": verified,
            "ticket_id": auth_ticket_id,
            "origin_post_id": auth.get("origin_post_id"),
        }
        if not verified:
            rollback_path = write_snapshot(envelope["app_id"], envelope["patch_id"], "rollback-source", after_app)
            client.save_app(before_app)
            _rollback_payload, rollback_app = client.load_app("")
            execution["rollback"] = {
                "attempted": True,
                "restored_sha256": app_json_sha256(rollback_app),
                "restored_version": rollback_app.get("Version"),
                "rollback_snapshot_path": rollback_path,
            }
            receipt["status"] = "error"
            receipt["error"] = "readback_verification_failed"
            receipt["writes"] = True
            receipt["execution"] = execution
            return receipt
        if envelope["promote_stable"]:
            target = str(after_app.get("Version") or "")
            promo = client.promote_stable(target)
            execution["promote_stable"] = promo
            latest_payload, latest_app = client.load_app("")
            execution["stable_version_after_promote"] = latest_app.get("StableVersion")
            execution["stable_matches_saved"] = str(latest_app.get("StableVersion") or "") == target
            execution["latest_wrapper_after_promote"] = wrapper_flags(latest_payload)
        receipt["writes"] = True
        receipt["execution"] = execution
        ops_receipt = receipts_root() / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-apply-{envelope['patch_id']}.json"
        ops_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        receipt["receipt_path"] = str(ops_receipt)
        return receipt
    except Exception as exc:
        logging.getLogger("pd_one_ops").exception("appsheet definition apply failed")
        try:
            client.save_app(before_app)
            _rollback_payload, rollback_app = client.load_app("")
            receipt["rollback"] = {
                "attempted": True,
                "restored_sha256": app_json_sha256(rollback_app),
                "restored_version": rollback_app.get("Version"),
                "failure": str(exc)[:500],
            }
        except Exception as rollback_exc:
            receipt["rollback"] = {"attempted": True, "error": str(rollback_exc)[:500], "failure": str(exc)[:500]}
        receipt["status"] = "error"
        receipt["error"] = "apply_failed"
        receipt["detail"] = str(exc)[:500]
        receipt["writes"] = True
        return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--app-id", default=DEFAULT_APP_ID)
    inspect.add_argument("--app-name", default=DEFAULT_APP_NAME)
    inspect.add_argument("--version", default="", help="Optional AppSheet version id; empty loads latest")
    apply = sub.add_parser("apply")
    apply.add_argument("--patch-envelope-path", required=True)
    apply.add_argument("--dry-run", action="store_true", default=True)
    apply.add_argument("--live", dest="dry_run", action="store_false")
    apply.add_argument("--ticket-id", default="")
    apply.add_argument("--requester-user-id", default="")
    apply.add_argument("--origin-post-id", default="")
    apply.add_argument("--confirm-live-write", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    _reexec_into_appsheet_venv()
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        emit(inspect_definition(app_id=args.app_id, app_name=args.app_name, version=args.version))
        return 0
    payload = apply_definition(
        patch_envelope_path=args.patch_envelope_path,
        dry_run=bool(args.dry_run),
        ticket_id=args.ticket_id,
        requester_user_id=args.requester_user_id,
        origin_post_id=args.origin_post_id,
        confirm_live_write=args.confirm_live_write,
    )
    return 0 if payload.get("status") == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
