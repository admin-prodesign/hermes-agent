"""Environment and path defaults for the PD One Mattermost status monitor."""
from __future__ import annotations

import os
from pathlib import Path

from hermes_constants import get_hermes_home


def _hermes_home() -> Path:
    return get_hermes_home().expanduser()


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    return Path(raw).expanduser() if raw else default


_HOME = _hermes_home()

STATE_DIR = _env_path("PD_ONE_STATUS_STATE_DIR", _HOME / "state" / "pd-one-mattermost-status")
LOG_DIR = _env_path("PD_ONE_STATUS_LOG_DIR", _HOME / "logs" / "pd-one-mattermost-status")
AVATAR_DIR = _env_path("PD_ONE_STATUS_AVATAR_DIR", STATE_DIR / "avatar")
ENV_FILE = _env_path("PD_ONE_GATEWAY_ENV", _HOME / "gateway.systemd.env")
PDONE_CONFIG = _env_path("PD_ONE_STATUS_CONFIG", _HOME / "config.yaml")

CHANNEL_ID = os.getenv("PD_ONE_STATUS_MATTERMOST_CHANNEL", "").strip()
GATEWAY_UNIT = os.getenv("PD_ONE_STATUS_GATEWAY_UNIT", "hermes-gateway-pdone.service")
HEALTH_URL = os.getenv("PD_ONE_STATUS_HEALTH_URL", "").strip()

PROVIDER_CHECK_ENABLED = os.getenv("PD_ONE_STATUS_PROVIDER_CHECK", "1").lower() not in {"0", "false", "no"}
PROVIDER_MODEL_URL_SUFFIX = os.getenv("PD_ONE_STATUS_PROVIDER_MODELS_SUFFIX", "/v1/models")

CANARY_ENABLED = os.getenv("PD_ONE_STATUS_CANARY", "1").lower() not in {"0", "false", "no"}
CANARY_INTERVAL_SECONDS = int(os.getenv("PD_ONE_STATUS_CANARY_INTERVAL_SECONDS", "900"))
CANARY_FAILURE_BACKOFF_SECONDS = int(os.getenv("PD_ONE_STATUS_CANARY_FAILURE_BACKOFF_SECONDS", "900"))
CANARY_TIMEOUT = float(os.getenv("PD_ONE_STATUS_CANARY_TIMEOUT", "15"))
CANARY_PROMPT = os.getenv("PD_ONE_STATUS_CANARY_PROMPT", ".")
CANARY_STALE_GRACE_SECONDS = int(os.getenv("PD_ONE_STATUS_CANARY_STALE_GRACE_SECONDS", "120"))

HERMES_CANARY_ENABLED = os.getenv("PD_ONE_STATUS_HERMES_CANARY", "1").lower() not in {"0", "false", "no"}
HERMES_CANARY_INTERVAL_SECONDS = int(os.getenv("PD_ONE_STATUS_HERMES_CANARY_INTERVAL_SECONDS", "3600"))
HERMES_CANARY_TIMEOUT = float(os.getenv("PD_ONE_STATUS_HERMES_CANARY_TIMEOUT", "45"))
HERMES_CANARY_PROMPT = os.getenv("PD_ONE_STATUS_HERMES_CANARY_PROMPT", "Reply exactly OK.")

HERMES_RELEASE_ROOT = Path(
    os.getenv("PD_ONE_STATUS_HERMES_RELEASE_ROOT", os.environ.get("HERMES_AGENT_DIR", "")).strip()
    or Path(__file__).resolve().parents[3]
)

EXPECTED_HERMES_HOME = Path(os.getenv("PD_ONE_STATUS_EXPECTED_HERMES_HOME", str(_HOME))).expanduser()
STRICT_PROFILE_AUTH = os.getenv("PD_ONE_STATUS_STRICT_PROFILE_AUTH", "1").lower() not in {"0", "false", "no"}

if STRICT_PROFILE_AUTH and str(EXPECTED_HERMES_HOME):
    os.environ.setdefault("HERMES_HOME", str(EXPECTED_HERMES_HOME))

FAILURES_TO_OFFLINE = int(os.getenv("PD_ONE_STATUS_FAILURES_TO_OFFLINE", "3"))
REQUEST_TIMEOUT = float(os.getenv("PD_ONE_STATUS_TIMEOUT", "8"))

AVATAR_BADGING_ENABLED = os.getenv("PD_ONE_STATUS_AVATAR_BADGING", "1").lower() not in {"0", "false", "no"}
BOT_DESCRIPTION_BADGING_ENABLED = os.getenv("PD_ONE_STATUS_BOT_DESCRIPTION", "1").lower() not in {"0", "false", "no"}

BOT_DESCRIPTIONS = {
    "online": "🟢 Online / 在線 — PD One is healthy. See pinned status post for details.",
    "degraded": "🟡 Degraded / 狀態不穩定 — PD One has a temporary health-check issue. See pinned status post for details.",
    "offline": "🔴 Offline / 離線 — PD One failed repeated health checks. See pinned status post for details.",
}

AVATAR_PATHS = {
    "online": AVATAR_DIR / "pd-one-avatar-online.png",
    "degraded": AVATAR_DIR / "pd-one-avatar-degraded.png",
    "offline": AVATAR_DIR / "pd-one-avatar-offline.png",
}
