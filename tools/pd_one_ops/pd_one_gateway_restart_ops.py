#!/usr/bin/env python3
"""Andy-origin Mattermost post authorization for bounded Hermes gateway restarts."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any, Callable

ALLOWED_UNITS = frozenset({"hermes-gateway-pdone.service", "hermes-gateway.service"})
LIVE_CONFIRMATION = "RESTART PD ONE GATEWAY"
MATTERMOST_POST_ID_RE = re.compile(r"^[a-z0-9]{26}$")
RESTART_REQUEST_RE = re.compile(
    r"(?is)\b(?:restart|reboot|reload)\b.*\b(?:gateway|hermes-gateway)\b|\b(?:gateway|hermes-gateway)\b.*\b(?:restart|reboot|reload)\b"
)


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "error": message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)


def emit(payload: dict[str, Any]) -> None:
    from tools.pd_one_ops.hr_guard import guard_hr_payload

    print(json.dumps(guard_hr_payload(payload), ensure_ascii=False, indent=2, sort_keys=True))


def _andy_user_id() -> str:
    from tools.pd_one_ops.pd_one_safe_ops_part0 import DEFAULT_ANDY_USER_ID

    return DEFAULT_ANDY_USER_ID() or "5nak6m7nmf8kudbrwbtccazbgc"


def _validate_post_id(origin_post_id: str) -> str:
    post_id = str(origin_post_id or "").strip()
    if not MATTERMOST_POST_ID_RE.fullmatch(post_id):
        fail(f"invalid Mattermost origin_post_id: {origin_post_id!r}")
    return post_id


def post_requests_gateway_restart(message: str) -> bool:
    return bool(RESTART_REQUEST_RE.search(str(message or "")))


def authorize_andy_gateway_restart(
    *,
    requester_user_id: str,
    origin_post_id: str,
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    andy_id = _andy_user_id()
    requester = str(requester_user_id or "").strip()
    if requester != andy_id:
        fail("gateway restart origin authorization requires Andy requester_user_id")
    post_id = _validate_post_id(origin_post_id)
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
    if not post_requests_gateway_restart(message):
        fail("origin post message does not request a gateway restart")
    return {
        "authorization": "andy_origin_post",
        "origin_post_id": post_id,
        "requester_user_id": requester,
        "message_excerpt": message[:240],
    }


def restart_gateway(
    *,
    unit_name: str,
    dry_run: bool = True,
    requester_user_id: str = "",
    origin_post_id: str = "",
    confirm_live_write: str = "",
    post_fetcher: Callable[[str], dict[str, Any]] | None = None,
    busctl_runner: Callable[[list[str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    unit = str(unit_name or "").strip()
    if unit not in ALLOWED_UNITS:
        fail(f"unit_name must be one of: {', '.join(sorted(ALLOWED_UNITS))}")
    receipt: dict[str, Any] = {
        "status": "ok",
        "capability": "pd_one_gateway_restart",
        "mode": "dry-run" if dry_run else "live",
        "unit_name": unit,
        "plan": {
            "busctl_argv": [
                "busctl",
                "--user",
                "call",
                "org.freedesktop.systemd1",
                "/org/freedesktop/systemd1",
                "org.freedesktop.systemd1.Manager",
                "RestartUnit",
                "ss",
                unit,
                "replace",
            ],
            "would_restart": True,
        },
        "safety": {
            "andy_origin_post_required_for_live": True,
            "live_write_confirmation_required": LIVE_CONFIRMATION,
            "allowed_units": sorted(ALLOWED_UNITS),
            "shell_used": False,
            "systemctl_forbidden": True,
            "hermes_gateway_cli_forbidden": True,
            "approval_card_forbidden": True,
        },
    }
    if dry_run:
        receipt["writes"] = False
        return receipt
    if confirm_live_write != LIVE_CONFIRMATION:
        fail(f"live gateway restart requires confirm_live_write {LIVE_CONFIRMATION!r}")
    if not requester_user_id or not origin_post_id:
        fail("live gateway restart requires requester_user_id and origin_post_id")
    auth = authorize_andy_gateway_restart(
        requester_user_id=requester_user_id,
        origin_post_id=origin_post_id,
        post_fetcher=post_fetcher,
    )
    receipt["authorization"] = auth
    runner = busctl_runner or _default_busctl_runner
    result = runner(receipt["plan"]["busctl_argv"])
    receipt["writes"] = True
    receipt["execution"] = result
    return receipt


def _default_busctl_runner(argv: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"busctl RestartUnit failed: {exc}")
    if completed.returncode != 0:
        fail(
            "busctl RestartUnit returned non-zero exit "
            f"{completed.returncode}: {(completed.stderr or completed.stdout)[:500]}"
        )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[:500],
        "stderr": (completed.stderr or "")[:500],
    }


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", dest="dry_run", action="store_false")
    parser.add_argument("--requester-user-id", default="")
    parser.add_argument("--origin-post-id", default="")
    parser.add_argument("--confirm-live-write", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    emit(
        restart_gateway(
            unit_name=args.unit_name,
            dry_run=bool(args.dry_run),
            requester_user_id=args.requester_user_id,
            origin_post_id=args.origin_post_id,
            confirm_live_write=args.confirm_live_write,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())