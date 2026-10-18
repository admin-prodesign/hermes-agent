"""Maintain one editable Mattermost status post for PD One health.

Silent on success by default so it can run as a Hermes no-agent cron job.
Set PD_ONE_STATUS_VERBOSE=1 for a one-line summary.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from tools.pd_one_ops.mattermost_status import config as cfg
from tools.pd_one_ops.mattermost_status import providers as prov


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def tpe_stamp(ts: dt.datetime | None = None) -> str:
    ts = ts or utc_now()
    return ts.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S TPE")


def _canary_model() -> str:
    return os.getenv("PD_ONE_STATUS_CANARY_MODEL", "").strip() or prov.resolve_canary_model()


def _hermes_canary_model() -> str:
    explicit = os.getenv("PD_ONE_STATUS_HERMES_CANARY_MODEL", "").strip()
    return explicit or _canary_model()


def runtime_check_line() -> str:
    runtime = prov.load_runtime_model()
    msg = f"runtime {runtime['label']}"
    if runtime.get("default"):
        msg += f" {runtime['default']}"
    if runtime.get("provider"):
        msg += f" ({runtime['provider']})"
    return msg


def _is_mm_unreachable_item(item: str) -> bool:
    if not item.startswith("Mattermost API failed"):
        return False
    low = item.lower()
    return ("http 0" in low) or ("unreachable" in low) or ("timeout" in low) or ("timed out" in low)


def _gateway_healthy(checks_ok: list[str]) -> bool:
    return "gateway service active" in checks_ok


def _mm_unreachable_only(checks_ok: list[str], checks_bad: list[str]) -> bool:
    if not _gateway_healthy(checks_ok) or not checks_bad:
        return False
    return all(_is_mm_unreachable_item(x) for x in checks_bad)


def build_availability(
    checks_ok: list[str],
    checks_bad: list[str],
    detail: dict[str, Any],
) -> dict[str, Any]:
    process_ok = _gateway_healthy(checks_ok)
    mm_code = detail.get("mattermost_users_me_code")
    if not isinstance(mm_code, int):
        mm_code = 0
    mm_ok = bool(detail.get("mattermost_bot_user_id")) and 200 <= mm_code < 300
    runtime = detail.get("runtime_model") if isinstance(detail.get("runtime_model"), dict) else prov.load_runtime_model()
    return {
        "process": {
            "ok": bool(process_ok),
            "unit": cfg.GATEWAY_UNIT,
            "state": str(detail.get("systemd") or ("active" if process_ok else "unknown")),
        },
        "mm_from_nemo": {
            "ok": bool(mm_ok),
            "http_code": int(mm_code),
        },
        "runtime": {
            "label": str(runtime.get("label") or "Model"),
            "default": str(runtime.get("default") or ""),
            "provider": str(runtime.get("provider") or ""),
        },
    }


def load_env_file(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.exists():
        return vals
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        vals[key.strip()] = val.strip().strip('"').strip("'")
    return vals


def load_state() -> dict[str, Any]:
    p = cfg.STATE_DIR / "state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    cfg.STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cfg.STATE_DIR / "state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(cfg.STATE_DIR / "state.json")


def log_event(event: dict[str, Any]) -> None:
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    event = {"ts_utc": utc_now().isoformat(), **event}
    path = cfg.LOG_DIR / f"runs-{utc_now().strftime('%Y%m')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def run_cmd(args: list[str], timeout: float = cfg.REQUEST_TIMEOUT) -> tuple[bool, str]:
    try:
        cp = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return cp.returncode == 0, cp.stdout.strip()
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def http_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[bool, int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=cfg.REQUEST_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = body[:500]
            return 200 <= resp.status < 300, resp.status, parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        return False, exc.code, body
    except Exception as exc:
        return False, 0, f"{type(exc).__name__}: {exc}"


def http_multipart_image(url: str, *, token: str, image_path: Path) -> tuple[bool, int, Any]:
    boundary = f"----pd-one-avatar-{uuid.uuid4().hex}"
    image_bytes = image_path.read_bytes()
    filename = image_path.name
    body = b"".join([
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode("utf-8"),
        b"Content-Type: image/png\r\n\r\n",
        image_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ])
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=cfg.REQUEST_TIMEOUT) as resp:
            body_text = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                parsed = body_text[:500]
            return 200 <= resp.status < 300, resp.status, parsed
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", "replace")[:500]
        return False, exc.code, body_text
    except Exception as exc:
        return False, 0, f"{type(exc).__name__}: {exc}"


def update_avatar_badge(mm_url: str, token: str, bot_user_id: str, status: str, state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if not cfg.AVATAR_BADGING_ENABLED:
        return True, {"skipped": "disabled"}
    avatar_path = cfg.AVATAR_PATHS.get(status)
    if avatar_path is None or not avatar_path.exists():
        return False, {"error": "missing_avatar_variant", "status": status, "path": str(avatar_path) if avatar_path else None}
    if state.get("avatar_status") == status and state.get("avatar_path") == str(avatar_path):
        return True, {"skipped": "already_current", "status": status, "path": str(avatar_path)}
    ok, code, data = http_multipart_image(mm_url.rstrip("/") + f"/api/v4/users/{bot_user_id}/image", token=token, image_path=avatar_path)
    detail = {"http_code": code, "status": status, "path": str(avatar_path), "response": data}
    if ok:
        state["avatar_status"] = status
        state["avatar_path"] = str(avatar_path)
        state["avatar_updated_tpe"] = tpe_stamp()
        state.pop("avatar_error", None)
    else:
        state["avatar_error"] = detail
    return ok, detail


def update_bot_description(mm_url: str, token: str, bot_user_id: str, status: str, state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if not cfg.BOT_DESCRIPTION_BADGING_ENABLED:
        return True, {"skipped": "disabled"}
    description = cfg.BOT_DESCRIPTIONS.get(status)
    if not description:
        return False, {"error": "missing_description_variant", "status": status}
    if state.get("bot_description_status") == status and state.get("bot_description") == description:
        return True, {"skipped": "already_current", "status": status, "description": description}
    ok, code, data = http_json(
        mm_url.rstrip("/") + f"/api/v4/bots/{bot_user_id}",
        method="PUT",
        token=token,
        payload={"description": description},
    )
    detail = {"http_code": code, "status": status, "description": description, "response": data}
    if ok:
        state["bot_description_status"] = status
        state["bot_description"] = description
        state["bot_description_updated_tpe"] = tpe_stamp()
        state.pop("bot_description_error", None)
    else:
        state["bot_description_error"] = detail
    return ok, detail


def _parse_iso_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def check_inference_canary(state: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    model = _canary_model()
    return prov.cached_canary_runner(
        state,
        state_key="codex_canary",
        enabled=cfg.CANARY_ENABLED,
        force_env="PD_ONE_STATUS_FORCE_CANARY",
        interval_seconds=cfg.CANARY_INTERVAL_SECONDS,
        failure_backoff_seconds=cfg.CANARY_FAILURE_BACKOFF_SECONDS,
        stale_grace_seconds=cfg.CANARY_STALE_GRACE_SECONDS,
        disabled_msg="Provider inference canary disabled",
        stale_msg="Provider inference canary stale",
        ok_prefix="Provider inference canary OK",
        fail_msg="Provider inference canary failed",
        runner=lambda: prov._run_inference_canary(model),
        parse_iso_ts=_parse_iso_ts,
        utc_now_iso=lambda: utc_now().isoformat(),
        tpe_stamp=tpe_stamp,
    )


def check_hermes_path_canary(state: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    model = _hermes_canary_model()
    prompt = cfg.HERMES_CANARY_PROMPT
    return prov.cached_canary_runner(
        state,
        state_key="hermes_path_canary",
        enabled=cfg.HERMES_CANARY_ENABLED,
        force_env="PD_ONE_STATUS_FORCE_HERMES_CANARY",
        interval_seconds=cfg.HERMES_CANARY_INTERVAL_SECONDS,
        failure_backoff_seconds=cfg.CANARY_FAILURE_BACKOFF_SECONDS,
        stale_grace_seconds=cfg.CANARY_STALE_GRACE_SECONDS,
        disabled_msg="Hermes-path canary disabled",
        stale_msg="Hermes-path canary stale",
        ok_prefix="Hermes-path canary OK",
        fail_msg="Hermes-path canary failed",
        runner=lambda: prov.run_hermes_path_canary(model, prompt),
        parse_iso_ts=_parse_iso_ts,
        utc_now_iso=lambda: utc_now().isoformat(),
        tpe_stamp=tpe_stamp,
    )


def check_health(mm_url: str, token: str, state: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    ok: list[str] = []
    bad: list[str] = []
    detail: dict[str, Any] = {}

    active, out = run_cmd(["systemctl", "--user", "is-active", cfg.GATEWAY_UNIT])
    detail["systemd"] = out
    (ok if active and out == "active" else bad).append(
        "gateway service active" if active and out == "active" else f"gateway service not active ({out or 'unknown'})"
    )

    h_ok = True
    code = 0
    body: Any = {"skipped": "no_health_url_configured"}
    if cfg.HEALTH_URL:
        h_ok, code, body = http_json(cfg.HEALTH_URL)
        detail["health_http_code"] = code
        detail["health_body"] = body if isinstance(body, dict) else str(body)[:180]
        if h_ok and isinstance(body, dict) and body.get("ok") is True:
            ok.append("local health endpoint OK")
        else:
            bad.append(f"local health endpoint failed (HTTP {code})")
    else:
        detail["health_http_code"] = None
        detail["health_body"] = body
        ok.append("local health endpoint not configured for Hermes gateway")

    me_ok, me_code, me = http_json(mm_url.rstrip("/") + "/api/v4/users/me", token=token)
    detail["mattermost_users_me_code"] = me_code
    if me_ok and isinstance(me, dict) and me.get("id"):
        ok.append(f"Mattermost API OK as @{me.get('username', 'bot')}")
        detail["mattermost_bot_user_id"] = me.get("id")
        detail["mattermost_bot_username"] = me.get("username")
    else:
        if me_code == 0:
            bad.append("Mattermost API failed (HTTP 0) — unreachable from bot host (NAT hairpin)")
        else:
            bad.append(f"Mattermost API failed (HTTP {me_code})")

    runtime_msg = runtime_check_line()
    detail["runtime_model"] = prov.load_runtime_model()
    ok.append(runtime_msg)

    provider_ok, provider_msg, provider_detail = prov.check_provider_metadata()
    detail["provider_metadata"] = provider_detail
    detail["provider_metadata_msg"] = provider_msg
    if provider_ok:
        ok.append(provider_msg)
    else:
        bad.append(provider_msg)

    canary_ok, canary_msg, canary_detail = check_inference_canary(state)
    detail["inference_canary"] = canary_detail
    detail["codex_canary"] = canary_detail
    detail["codex_canary_msg"] = canary_msg
    if canary_ok:
        ok.append(canary_msg)
    else:
        bad.append(canary_msg)

    hermes_ok, hermes_msg, hermes_detail = check_hermes_path_canary(state)
    detail["hermes_path_canary"] = hermes_detail
    detail["hermes_path_canary_msg"] = hermes_msg
    if hermes_ok:
        ok.append(hermes_msg)
    else:
        bad.append(hermes_msg)

    return ok, bad, detail


def _zh_check(item: str) -> str:
    mapping = (
        ("gateway service active", "閘道服務正常運作"),
        ("local health endpoint OK", "本機健康檢查端點正常"),
        ("local health endpoint not configured for Hermes gateway", "Hermes 閘道未設定本機健康檢查端點"),
    )
    for prefix, zh in mapping:
        if item == prefix:
            return zh
    if item.startswith("Mattermost API OK as"):
        return item.replace("Mattermost API OK as", "Mattermost API 正常，帳號")
    if item.startswith("gateway service not active"):
        return item.replace("gateway service not active", "閘道服務未正常運作")
    if item.startswith("local health endpoint failed"):
        return item.replace("local health endpoint failed", "本機健康檢查端點失敗")
    if item.startswith("Mattermost API failed (HTTP 0)"):
        return "Mattermost API 失敗（HTTP 0）— 機器人主機無法連線（NAT hairpin）"
    if item.startswith("Mattermost API failed"):
        return item.replace("Mattermost API failed", "Mattermost API 失敗")
    if item.startswith("runtime "):
        return item.replace("runtime ", "執行環境 ", 1)
    if item.startswith("Provider metadata check disabled"):
        return "Provider 元資料檢查已停用"
    if item.startswith("Provider OAuth/token unavailable"):
        return "Provider OAuth token 無法使用"
    if "model catalog OK" in item:
        return item.replace("OAuth/model catalog OK", "OAuth / 模型清單正常")
    if "model catalog failed" in item:
        return item.replace("model catalog failed", "模型清單失敗")
    if item.startswith("Provider inference canary OK"):
        return item.replace("Provider inference canary OK", "Provider 推理 canary 正常")
    if item.startswith("Provider inference canary disabled"):
        return "Provider 推理 canary 已停用"
    if item.startswith("Provider inference canary stale"):
        return "Provider 推理 canary 已過期"
    if item.startswith("Provider inference canary failed"):
        return "Provider 推理 canary 失敗"
    if item.startswith("Hermes-path canary OK"):
        return item.replace("Hermes-path canary OK", "Hermes 路徑 canary 正常")
    if item.startswith("Hermes-path canary disabled"):
        return "Hermes 路徑 canary 已停用"
    if item.startswith("Hermes-path canary stale"):
        return "Hermes 路徑 canary 已過期"
    if item.startswith("Hermes-path canary failed"):
        return "Hermes 路徑 canary 失敗"
    return item


def render_message(status: str, checks_ok: list[str], checks_bad: list[str], state: dict[str, Any]) -> str:
    avail = state.get("availability") if isinstance(state.get("availability"), dict) else {}
    process = avail.get("process") if isinstance(avail.get("process"), dict) else {}
    mm_nemo = avail.get("mm_from_nemo") if isinstance(avail.get("mm_from_nemo"), dict) else {}
    runtime = avail.get("runtime") if isinstance(avail.get("runtime"), dict) else prov.load_runtime_model()
    process_ok = bool(process.get("ok", _gateway_healthy(checks_ok)))
    process_state = str(process.get("state") or ("active" if process_ok else "unknown"))
    unit = str(process.get("unit") or cfg.GATEWAY_UNIT)
    mm_ok = bool(mm_nemo.get("ok"))
    mm_code = mm_nemo.get("http_code")
    if not isinstance(mm_code, int):
        mm_code = 0
    mm_only = _mm_unreachable_only(checks_ok, checks_bad) or (process_ok and not mm_ok)
    icon = {"online": "🟢", "degraded": "🟡", "offline": "🔴"}.get(status, "⚪")
    if status == "offline":
        title_en = "PD One offline"
        title_zh = "PD One 離線"
    elif status == "online":
        title_en = "PD One online"
        title_zh = "PD One 在線"
    elif mm_only:
        title_en = "PD One up, Mattermost unreachable from bot host"
        title_zh = "PD One 在線，但機器人主機連不到 Mattermost"
    else:
        title_en = "PD One degraded"
        title_zh = "PD One 狀態不穩定"
    last_success = state.get("last_success_tpe", "not recorded / 尚未記錄")
    consecutive = int(state.get("consecutive_mm_from_nemo_failures") or 0)
    if not consecutive:
        consecutive = int(state.get("consecutive_failures") or 0)
    checked = tpe_stamp()
    runtime_bit = str(runtime.get("label") or "Model")
    if runtime.get("default"):
        runtime_bit += f" (`{runtime['default']}`"
        if runtime.get("provider"):
            runtime_bit += f" / {runtime['provider']}"
        runtime_bit += ")"
    if process_ok:
        process_en = f"✅ PD One process: `{unit}` {process_state}"
        process_zh = f"✅ PD One 程序：`{unit}` {process_state}"
    else:
        process_en = f"❌ PD One process: `{unit}` {process_state}"
        process_zh = f"❌ PD One 程序：`{unit}` {process_state}"
    if mm_ok:
        mm_en = f"✅ PD One → Mattermost from bot host: HTTP {mm_code}"
        mm_zh = f"✅ PD One → Mattermost（從機器人主機）：HTTP {mm_code}"
    elif mm_code == 0:
        mm_en = (
            "⚠️ PD One → Mattermost from bot host: HTTP 0 (NAT hairpin) — "
            "people cannot talk to PD One on Mattermost"
        )
        mm_zh = (
            "⚠️ PD One → Mattermost（從機器人主機）：HTTP 0（NAT hairpin）— "
            "目前無法在 Mattermost 上聯繫 PD One"
        )
    else:
        mm_en = f"⚠️ PD One → Mattermost from bot host: HTTP {mm_code}"
        mm_zh = f"⚠️ PD One → Mattermost（從機器人主機）：HTTP {mm_code}"
    lines = [
        f"{icon} **{title_en} / {title_zh}**",
        "",
        "**English**",
        f"- Last checked: {checked}",
        f"- Last healthy check (process + Mattermost from bot host): {last_success}",
        f"- Consecutive Mattermost-from-bot-host failures: {consecutive}",
        f"- Runtime: {runtime_bit}",
        "- Availability:",
        f"  - {process_en}",
        f"  - {mm_en}",
        "- Checks:",
    ]
    for item in checks_ok:
        lines.append(f"  - ✅ {item}")
    for item in checks_bad:
        lines.append(f"  - ⚠️ {item}")
    lines.extend([
        "",
        "**繁體中文**",
        f"- 最後檢查時間：{checked}",
        f"- 最近一次健康檢查通過（程序 + 從機器人主機連 Mattermost）：{last_success}",
        f"- 機器人主機連續寫入 Mattermost 失敗次數：{consecutive}",
        f"- 執行環境：{runtime_bit}",
        "- 可用性：",
        f"  - {process_zh}",
        f"  - {mm_zh}",
        "- 檢查項目：",
    ])
    for item in checks_ok:
        lines.append(f"  - ✅ {_zh_check(item)}")
    for item in checks_bad:
        lines.append(f"  - ⚠️ {_zh_check(item)}")
    lines.extend([
        "",
        "This message is maintained automatically by the PD One status monitor; it edits this same post instead of spamming the channel.",
        "狀態由 PD One 監控自動更新；系統會編輯同一則訊息，不會重複洗版。",
    ])
    return "\n".join(lines)


def mm_post(mm_url: str, token: str, channel_id: str, message: str) -> tuple[bool, str, Any]:
    ok, code, data = http_json(
        mm_url.rstrip("/") + "/api/v4/posts",
        method="POST",
        token=token,
        payload={"channel_id": channel_id, "message": message},
    )
    post_id = data.get("id") if isinstance(data, dict) else None
    return ok and bool(post_id), str(post_id or f"HTTP {code}"), data


def mm_patch(mm_url: str, token: str, post_id: str, message: str) -> tuple[bool, Any]:
    ok, code, data = http_json(
        mm_url.rstrip("/") + f"/api/v4/posts/{post_id}/patch",
        method="PUT",
        token=token,
        payload={"message": message},
    )
    return ok, data if ok else {"code": code, "body": data}


def mm_pin(mm_url: str, token: str, post_id: str) -> tuple[bool, Any]:
    ok, code, data = http_json(mm_url.rstrip("/") + f"/api/v4/posts/{post_id}/pin", method="POST", token=token)
    return ok, data if ok else {"code": code, "body": data}


def main() -> int:
    verbose = os.getenv("PD_ONE_STATUS_VERBOSE", "").lower() in {"1", "true", "yes"}
    dry_run = "--dry-run" in sys.argv or os.getenv("PD_ONE_STATUS_DRY_RUN", "").lower() in {"1", "true", "yes"}
    env = {**load_env_file(cfg.ENV_FILE), **os.environ}
    mm_url = env.get("MATTERMOST_URL", "").rstrip("/")
    token = env.get("MATTERMOST_BOT_TOKEN") or env.get("MATTERMOST_TOKEN") or ""
    channel_id = cfg.CHANNEL_ID
    state = load_state()
    original_state = dict(state)

    if not channel_id:
        log_event({"level": "error", "event": "missing_mattermost_channel", "hint": "set PD_ONE_STATUS_MATTERMOST_CHANNEL"})
        if verbose:
            print("missing PD_ONE_STATUS_MATTERMOST_CHANNEL")
        return 2

    if not mm_url or not token:
        log_event({"level": "error", "event": "missing_mattermost_config", "env_file": str(cfg.ENV_FILE)})
        if verbose:
            print("missing Mattermost URL/token")
        return 2

    checks_ok, checks_bad, detail = check_health(mm_url, token, state)
    now_tpe = tpe_stamp()
    prev_status = state.get("status")
    availability = build_availability(checks_ok, checks_bad, detail)
    process_ok = bool(availability["process"]["ok"])
    mm_nemo_ok = bool(availability["mm_from_nemo"]["ok"])
    if not process_ok:
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        state["last_failure_tpe"] = now_tpe
        state["last_failure_summary"] = "; ".join(checks_bad)[:500]
        status = "offline" if state["consecutive_failures"] >= cfg.FAILURES_TO_OFFLINE else "degraded"
    elif not mm_nemo_ok:
        prev_mm = state.get("consecutive_mm_from_nemo_failures")
        if prev_mm is None:
            prev_mm = int(state.get("consecutive_failures", 0))
        state["consecutive_mm_from_nemo_failures"] = int(prev_mm) + 1
        state["consecutive_failures"] = 0
        state["last_failure_tpe"] = now_tpe
        state["last_failure_summary"] = "; ".join(checks_bad)[:500]
        status = "degraded"
    elif checks_bad:
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        state["last_failure_tpe"] = now_tpe
        state["last_failure_summary"] = "; ".join(checks_bad)[:500]
        status = "offline" if state["consecutive_failures"] >= cfg.FAILURES_TO_OFFLINE else "degraded"
    else:
        state["consecutive_failures"] = 0
        state["consecutive_mm_from_nemo_failures"] = 0
        status = "online"
        state["last_success_tpe"] = now_tpe
        state.pop("last_failure_summary", None)

    state["status"] = status
    state["last_checked_tpe"] = now_tpe
    state["availability"] = availability
    if state.get("channel_id") and state.get("channel_id") != channel_id:
        state["previous_post_id"] = state.get("post_id")
        state["previous_channel_id"] = state.get("channel_id")
        state.pop("post_id", None)
        state.pop("post_url_hint", None)
    state["channel_id"] = channel_id
    state["updated_by"] = "tools.pd_one_ops.mattermost_status"

    if dry_run:
        persisted = dict(original_state)
        if "codex_canary" in state:
            persisted["codex_canary"] = state["codex_canary"]
        if "hermes_path_canary" in state:
            persisted["hermes_path_canary"] = state["hermes_path_canary"]
        persisted["dry_run_status"] = status
        persisted["dry_run_last_checked_tpe"] = now_tpe
        persisted["dry_run_checks_bad"] = checks_bad
        persisted["availability"] = availability
        log_event({"level": "info", "event": "dry_run_status_checked", "status": status, "checks_ok": checks_ok, "checks_bad": checks_bad, "health": detail})
        save_state(persisted)
        print(f"dry_run status={status} failures={state.get('consecutive_failures', 0)} ok={len(checks_ok)} bad={len(checks_bad)}")
        return 0

    avatar_ok = True
    avatar_detail: dict[str, Any] = {"skipped": "no_bot_user_id"}
    bot_description_ok = True
    bot_description_detail: dict[str, Any] = {"skipped": "no_bot_user_id"}
    bot_user_id = detail.get("mattermost_bot_user_id")
    if bot_user_id:
        avatar_ok, avatar_detail = update_avatar_badge(mm_url, token, str(bot_user_id), status, state)
        if not avatar_ok:
            log_event({"level": "warning", "event": "avatar_badge_update_failed", "status": status, "detail": avatar_detail})
        bot_description_ok, bot_description_detail = update_bot_description(mm_url, token, str(bot_user_id), status, state)
        if not bot_description_ok:
            log_event({"level": "warning", "event": "bot_description_update_failed", "status": status, "detail": bot_description_detail})

    message = render_message(status, checks_ok, checks_bad, state)
    post_id = state.get("post_id")
    posted = False
    delivery_detail: Any = None
    if post_id:
        patched, delivery_detail = mm_patch(mm_url, token, post_id, message)
        if not patched:
            patch_code = delivery_detail.get("code") if isinstance(delivery_detail, dict) else None
            if patch_code not in {403, 404}:
                log_event({"level": "error", "event": "mattermost_patch_failed_no_repost", "status": status, "post_id": post_id, "detail": delivery_detail, "health": detail})
                save_state(state)
                if verbose:
                    print(f"status={status} patch_failed_no_repost post_id={post_id} detail={delivery_detail}")
                if _mm_unreachable_only(checks_ok, checks_bad) or patch_code in {0, None}:
                    return 0
                return 3
            created, new_post_id, delivery_detail = mm_post(mm_url, token, channel_id, message)
            if not created:
                log_event({"level": "error", "event": "mattermost_update_failed", "status": status, "detail": delivery_detail, "health": detail})
                save_state(state)
                if verbose:
                    print(f"status={status} update_failed detail={delivery_detail}")
                return 3
            state["post_id"] = new_post_id
            posted = True
            pinned, pin_detail = mm_pin(mm_url, token, new_post_id)
            if not pinned:
                log_event({"level": "warning", "event": "mattermost_pin_failed", "status": status, "post_id": new_post_id, "detail": pin_detail})
    else:
        created, new_post_id, delivery_detail = mm_post(mm_url, token, channel_id, message)
        if not created:
            log_event({"level": "error", "event": "mattermost_create_failed", "status": status, "detail": delivery_detail, "health": detail})
            save_state(state)
            if verbose:
                print(f"status={status} create_failed detail={delivery_detail}")
            return 3
        state["post_id"] = new_post_id
        posted = True
        pinned, pin_detail = mm_pin(mm_url, token, new_post_id)
        if not pinned:
            log_event({"level": "warning", "event": "mattermost_pin_failed", "status": status, "post_id": new_post_id, "detail": pin_detail})

    state["post_url_hint"] = f"{mm_url}/_redirect/pl/{state['post_id']}"
    save_state(state)
    log_event({
        "level": "info",
        "event": "status_updated",
        "status": status,
        "previous_status": prev_status,
        "posted_new_message": posted,
        "post_id": state.get("post_id"),
        "avatar_badge": avatar_detail,
        "bot_description": bot_description_detail,
        "checks_ok": checks_ok,
        "checks_bad": checks_bad,
        "health": detail,
    })
    if verbose:
        print(
            f"status={status} post_id={state.get('post_id')} url={state.get('post_url_hint')} "
            f"failures={state.get('consecutive_failures', 0)} avatar={state.get('avatar_status', 'unknown')} "
            f"profile={state.get('bot_description_status', 'unknown')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
