"""Provider-aware health probes using Hermes runtime credential resolution."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from tools.pd_one_ops.mattermost_status import config as cfg


def _json_safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:220]}"


def _auth_context_detail() -> dict[str, Any]:
    current = os.getenv("HERMES_HOME", "")
    expected = str(cfg.EXPECTED_HERMES_HOME) if cfg.EXPECTED_HERMES_HOME else ""
    try:
        current_resolved = str(Path(current).expanduser().resolve(strict=False)) if current else ""
    except Exception:
        current_resolved = current
    try:
        expected_resolved = str(cfg.EXPECTED_HERMES_HOME.resolve(strict=False)) if expected else ""
    except Exception:
        expected_resolved = expected
    return {
        "strict_profile_auth": cfg.STRICT_PROFILE_AUTH,
        "auth_home": current_resolved,
        "expected_auth_home": expected_resolved,
        "profile_auth_context_ok": (not cfg.STRICT_PROFILE_AUTH)
        or bool(current_resolved and current_resolved == expected_resolved),
    }


def _auth_context_error() -> str | None:
    ctx = _auth_context_detail()
    if not ctx.get("profile_auth_context_ok"):
        return (
            f"monitor auth context mismatch: HERMES_HOME={ctx.get('auth_home') or '<unset>'} "
            f"expected={ctx.get('expected_auth_home')}"
        )
    return None


def load_runtime_model(path: Path | None = None) -> dict[str, str]:
    """Read model.default / model.provider only. Never load API keys."""
    config_path = path or cfg.PDONE_CONFIG
    out = {"default": "", "provider": "", "label": "Model"}
    if not config_path.exists():
        return out
    try:
        in_model = False
        for raw in config_path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("model:"):
                in_model = True
                continue
            if not in_model:
                continue
            if raw and not raw[0].isspace():
                break
            line = raw.strip()
            if line.startswith("#") or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key == "default":
                out["default"] = val
            elif key == "provider":
                out["provider"] = val
        default = out["default"]
        provider = out["provider"]
        if default.startswith("grok") or provider in {"xai-oauth", "xai"}:
            out["label"] = "Grok"
        elif provider:
            out["label"] = provider
        elif default:
            out["label"] = default
        return out
    except Exception:
        return out


def resolve_canary_model() -> str:
    route = resolve_canary_route()
    return route["model"]


def resolve_canary_route() -> dict[str, str]:
    """Utility lane (auxiliary.monitor) when pinned; otherwise the main model from config."""
    from agent.auxiliary_client import _get_aux_model_for_provider, _resolve_task_provider_model
    from hermes_cli.config_effective import load_user_config_effective

    data = load_user_config_effective() or {}
    model_cfg = data.get("model") if isinstance(data.get("model"), dict) else {}
    main_provider = str(model_cfg.get("provider") or "").strip()
    main_model = str(model_cfg.get("default") or model_cfg.get("model") or "").strip()

    task_provider, task_model, *_rest = _resolve_task_provider_model("monitor")
    provider = (task_provider or "").strip()
    model = (task_model or "").strip()
    if not provider or provider == "auto":
        provider = main_provider
    if not model:
        model = main_model
    if not model and provider:
        picked = _get_aux_model_for_provider(provider)
        if picked:
            model = picked
    return {"provider": provider or "auto", "model": model or ""}


def _ensure_release_on_path() -> None:
    root = str(cfg.HERMES_RELEASE_ROOT)
    if root and root not in sys.path:
        sys.path.insert(0, root)


def load_provider_runtime_credentials(
    *,
    provider: str | None = None,
    target_model: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve/refresh runtime credentials for the configured provider (no secret logging)."""
    context_err = _auth_context_error()
    if context_err:
        return None, context_err
    _ensure_release_on_path()
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider

        route = resolve_canary_route()
        requested = (provider or route.get("provider") or "").strip() or None
        if requested == "auto":
            requested = None
        model = (target_model or route.get("model") or "").strip() or None
        runtime = resolve_runtime_provider(requested=requested, target_model=model)
        if isinstance(runtime, dict) and runtime.get("api_key"):
            merged = dict(runtime)
            merged.update(_auth_context_detail())
            return merged, None
        return None, "provider_auth_missing_runtime_token"
    except Exception as exc:
        return None, _json_safe_error(exc)


def _provider_display_name(runtime: dict[str, Any] | None) -> str:
    if not runtime:
        return "Provider"
    provider = str(runtime.get("provider") or runtime.get("requested_provider") or "").strip()
    if provider in {"xai-oauth", "xai"}:
        return "xAI Grok"
    return provider or "Provider"


def _http_json_headers(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float = cfg.REQUEST_TIMEOUT,
) -> tuple[bool, int, Any]:
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        return False, 0, _json_safe_error(exc)


def _auth_headers(runtime: dict[str, Any]) -> dict[str, str]:
    token = str(runtime.get("api_key") or "").strip()
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    provider = str(runtime.get("provider") or "").lower()
    if provider in {"xai-oauth", "xai"}:
        try:
            from tools.xai_http import hermes_xai_default_headers

            headers.update(hermes_xai_default_headers())
        except Exception:
            pass
    return headers


def _models_url(runtime: dict[str, Any]) -> str:
    base = str(runtime.get("base_url") or "").rstrip("/")
    suffix = cfg.PROVIDER_MODEL_URL_SUFFIX
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    if base.endswith("/v1") and suffix.startswith("/v1/"):
        suffix = suffix[len("/v1") :]
    return base + suffix


def check_provider_metadata() -> tuple[bool, str, dict[str, Any]]:
    label = "Provider"
    if not cfg.PROVIDER_CHECK_ENABLED:
        return True, "Provider metadata check disabled", {"skipped": "disabled"}
    runtime, err = load_provider_runtime_credentials()
    if err or not runtime:
        detail = {"error": err or "missing_runtime", **_auth_context_detail()}
        return False, "Provider OAuth/token unavailable", detail
    label = _provider_display_name(runtime)
    base_url = str(runtime.get("base_url") or "").rstrip("/")
    detail: dict[str, Any] = {
        "base_url": base_url,
        "provider": runtime.get("provider"),
        "source": runtime.get("source"),
        "last_refresh": runtime.get("last_refresh"),
        **_auth_context_detail(),
    }
    if cfg.STRICT_PROFILE_AUTH and not detail.get("profile_auth_context_ok"):
        detail["error"] = "auth_context_mismatch"
        return False, f"{label} auth context mismatch", detail
    url = _models_url(runtime)
    ok, code, data = _http_json_headers(url, _auth_headers(runtime))
    detail["models_http_code"] = code
    if ok:
        if isinstance(data, dict):
            models = data.get("models") or data.get("data") or data.get("items") or []
            detail["models_count"] = len(models) if isinstance(models, list) else None
        return True, f"{label} OAuth/model catalog OK", detail
    detail["error"] = str(data)[:220]
    return False, f"{label} model catalog failed (HTTP {code})", detail


def _run_inference_canary(model: str) -> tuple[bool, dict[str, Any]]:
    started = time.monotonic()
    try:
        runtime, err = load_provider_runtime_credentials(target_model=model)
        if err or not runtime:
            return False, {"error": err or "runtime_unavailable", "model": model}
        _ensure_release_on_path()
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning

        route = resolve_canary_route()
        provider = str(runtime.get("provider") or route.get("provider") or "")
        response = call_llm(
            task="monitor",
            provider=provider if provider and provider != "auto" else None,
            model=model,
            messages=[{"role": "user", "content": cfg.CANARY_PROMPT}],
            max_tokens=8,
            timeout=cfg.CANARY_TIMEOUT,
            temperature=0,
            main_runtime={**runtime, "model": model},
        )
        text = extract_content_or_reasoning(response) or ""
        return True, {
            "model": model,
            "provider": provider,
            "auth_source": runtime.get("source"),
            **_auth_context_detail(),
            "prompt_chars": len(cfg.CANARY_PROMPT),
            "returned_chars": len(text),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "transport": "auxiliary.call_llm",
            "note": "Canary uses the configured utility/monitor model with minimal input and no tools.",
        }
    except Exception as exc:
        return False, {
            "model": model,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": _json_safe_error(exc),
        }


def run_hermes_path_canary(model: str, prompt: str) -> tuple[bool, dict[str, Any]]:
    """Full Hermes AIAgent path in a child process (hourly)."""
    import subprocess

    started = time.monotonic()
    module_path = Path(__file__).resolve()
    code = f'''
import importlib.util, json, os, sys, time
spec = importlib.util.spec_from_file_location("pd_one_mm_status_providers", {str(module_path)!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    runtime, err = mod.load_provider_runtime_credentials(target_model={model!r})
    if err or not runtime:
        print(json.dumps({{"ok": False, "error": err or "runtime_unavailable"}}))
        raise SystemExit(0)
    mod._ensure_release_on_path()
    from run_agent import AIAgent
    agent = AIAgent(
        api_key=runtime.get("api_key"),
        base_url=runtime.get("base_url"),
        provider=runtime.get("provider"),
        api_mode=runtime.get("api_mode"),
        model={model!r},
        enabled_toolsets=[],
        quiet_mode=True,
        max_iterations=1,
        max_tokens=8,
        platform="cli",
        skip_context_files=True,
        skip_memory=True,
        ephemeral_system_prompt="You are a health-check canary. Reply exactly OK and nothing else.",
    )
    agent.suppress_status_output = True
    agent.stream_delta_callback = None
    agent.tool_gen_callback = None
    t0 = time.monotonic()
    response = agent.chat({prompt!r}) or ""
    print(json.dumps({{
        "ok": "OK" in response.strip()[:20],
        "response_preview": response.strip()[:40],
        "auth_source": runtime.get("source"),
        **mod._auth_context_detail(),
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": f"{{type(exc).__name__}}: {{exc}}"}}))
'''
    env = os.environ.copy()
    env.setdefault("HERMES_IGNORE_RULES", "1")
    env.setdefault("HERMES_YOLO_MODE", "1")
    release = str(cfg.HERMES_RELEASE_ROOT)
    if release:
        paths = [release] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    try:
        cp = subprocess.run(
            [sys.executable, "-c", code],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=cfg.HERMES_CANARY_TIMEOUT,
            env=env,
        )
        parsed: dict[str, Any] | None = None
        for line in reversed(cp.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and "ok" in candidate:
                parsed = candidate
                break
        if parsed is None:
            return False, {
                "model": model,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "exit_code": cp.returncode,
                "error": (cp.stdout or "no child output")[-500:],
            }
        ok = bool(parsed.pop("ok")) and cp.returncode == 0
        return ok, {
            "model": model,
            "prompt_chars": len(prompt),
            "transport": "Hermes AIAgent, no tools, skip memory/context",
            "child_exit_code": cp.returncode,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            **parsed,
        }
    except subprocess.TimeoutExpired:
        return False, {
            "model": model,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": f"Hermes-path canary timed out after {cfg.HERMES_CANARY_TIMEOUT}s",
        }
    except Exception as exc:
        return False, {
            "model": model,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": _json_safe_error(exc),
        }


def cached_canary_runner(
    state: dict[str, Any],
    *,
    state_key: str,
    enabled: bool,
    force_env: str,
    interval_seconds: int,
    failure_backoff_seconds: int,
    stale_grace_seconds: int,
    disabled_msg: str,
    stale_msg: str,
    ok_prefix: str,
    fail_msg: str,
    runner: Callable[[], tuple[bool, dict[str, Any]]],
    parse_iso_ts: Callable[[Any], float | None],
    utc_now_iso: Callable[[], str],
    tpe_stamp: Callable[[], str],
) -> tuple[bool, str, dict[str, Any]]:
    if not enabled:
        return True, disabled_msg, {"skipped": "disabled"}
    canary = state.get(state_key) if isinstance(state.get(state_key), dict) else {}
    now = time.time()
    last_run_ts = parse_iso_ts(canary.get("last_run_utc"))
    last_success_ts = parse_iso_ts(canary.get("last_success_utc"))
    due = os.getenv(force_env, "").lower() in {"1", "true", "yes"}
    effective_interval = interval_seconds
    if canary.get("ok") is False and failure_backoff_seconds > 0:
        effective_interval = max(interval_seconds, failure_backoff_seconds)
    due = due or last_run_ts is None or (now - last_run_ts) >= effective_interval
    if state_key in {"codex_canary", "hermes_path_canary"} and cfg.STRICT_PROFILE_AUTH:
        ctx = _auth_context_detail()
        if canary.get("auth_home") != ctx.get("auth_home") or canary.get("profile_auth_context_ok") is not True:
            due = True
    if not due:
        cached = {"cached": True, **canary}
        if canary.get("ok") is False:
            return False, fail_msg, cached
        age = int(now - last_success_ts) if last_success_ts else None
        if last_success_ts and age is not None and age <= interval_seconds + stale_grace_seconds:
            return True, f"{ok_prefix} ({int(age / 60)}m ago)", cached
        return False, stale_msg, cached

    ok, detail = runner()
    record = {
        "last_run_utc": utc_now_iso(),
        "last_run_tpe": tpe_stamp(),
        "ok": ok,
        **detail,
    }
    if ok:
        record["last_success_utc"] = record["last_run_utc"]
        record["last_success_tpe"] = record["last_run_tpe"]
    elif canary.get("last_success_utc"):
        record["last_success_utc"] = canary.get("last_success_utc")
        record["last_success_tpe"] = canary.get("last_success_tpe")
    state[state_key] = record
    if ok:
        return True, ok_prefix, record
    return False, fail_msg, record
