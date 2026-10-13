"""Tests for PD One/OpenClaw-style per-channel Mattermost scope routing."""

import importlib.util
from pathlib import Path

from gateway.config import Platform
from gateway.pd_one_channel_scopes import (
    build_scope_prompt,
    pdone_profile_home,
    resolve_pd_one_channel_scope,
    scoped_skills,
    scoped_toolsets,
    scope_signature_fragment,
)

# ~/.openclaw/workspace-finance under the process user's home. On the
# production host that is the same workspace path the suite used to spell out.
_FINANCE_WORKSPACE = str(Path.home() / ".openclaw" / "workspace-finance")
# Mattermost ids are 26-char lowercase alphanumeric. These are obvious stand-ins.
_ADMIN_USER_ID = "testuser000000000000000001"
_DISCUSSION_CHANNEL_ID = "testchannel000000000000001"


def test_resolve_scope_from_mattermost_channel_config():
    cfg = {
        "mattermost": {
            "pd_one_channel_scopes": {
                "finance-channel": {
                    "agent_id": "finance",
                    "name": "PD One Finance",
                    "workspace": _FINANCE_WORKSPACE,
                    "allowed_toolsets": ["file", "skills", "clarify"],
                    "prompt": "Finance only.",
                }
            }
        }
    }

    scope = resolve_pd_one_channel_scope(cfg, "mattermost", "finance-channel")

    assert scope is not None
    assert scope["agent_id"] == "finance"
    assert scope["workspace"] == _FINANCE_WORKSPACE


def test_resolve_scope_supports_default_fallback_for_unknown_channel():
    cfg = {
        "mattermost": {
            "pd_one_channel_scopes": {
                "_default": {
                    "agent_id": "employee-assistant",
                    "allowed_toolsets": ["skills", "clarify"],
                    "prompt": "Employee-safe fallback.",
                }
            }
        }
    }

    scope = resolve_pd_one_channel_scope(cfg, "mattermost", "unknown-channel")

    assert scope is not None
    assert scope["agent_id"] == "employee-assistant"


def test_authorized_admin_prefix_overrides_employee_channel_scope():
    cfg = {
        "mattermost": {
            "pd_one_admin_prefix": {"allow_from": [_ADMIN_USER_ID]},
            "pd_one_channel_scopes": {
                "admin-channel": {
                    "agent_id": "admin",
                    "allowed_toolsets": ["terminal", "file"],
                    "prompt": "Admin scope.",
                },
                "employee-channel": {
                    "agent_id": "employee-assistant",
                    "allowed_toolsets": ["skills", "clarify"],
                    "prompt": "Employee scope.",
                },
            },
        }
    }

    scope = resolve_pd_one_channel_scope(
        cfg,
        "mattermost",
        "employee-channel",
        user_id=_ADMIN_USER_ID,
        text="admin: fix the capability",
    )

    assert scope is not None
    assert scope["agent_id"] == "admin"
    assert scope["admin_prefix_invoked"] is True
    assert scope["original_channel_scope"]["agent_id"] == "employee-assistant"
    got = scoped_toolsets(["skills", "terminal", "file"], scope)
    assert got[:3] == ["skills", "terminal", "file"]
    assert "pdone_safe_ops" in got
    assert "clarify" not in got


def test_admin_prefix_escalation_uses_raw_text_not_prepared_context():
    cfg = {
        "mattermost": {
            "pd_one_admin_prefix": {"allow_from": ["admin-user"]},
            "pd_one_channel_scopes": {
                "admin-channel": {"agent_id": "admin", "allowed_toolsets": ["terminal"]},
                "employee-channel": {"agent_id": "employee-assistant", "allowed_toolsets": ["skills"]},
            },
        }
    }
    prepared_message = """[PD One Hermes permission bridge]
Policy context...

[Mattermost thread context]
[New message]
[andy.lin] admin: show current PD One scope only"""

    hidden_scope = resolve_pd_one_channel_scope(
        cfg,
        "mattermost",
        "employee-channel",
        user_id="admin-user",
        text=prepared_message,
    )
    raw_scope = resolve_pd_one_channel_scope(
        cfg,
        "mattermost",
        "employee-channel",
        user_id="admin-user",
        text="admin: show current PD One scope only",
    )

    assert hidden_scope is not None
    assert hidden_scope["agent_id"] == "employee-assistant"
    assert raw_scope is not None
    assert raw_scope["agent_id"] == "admin"
    assert raw_scope["admin_prefix_invoked"] is True
    assert scope_signature_fragment(hidden_scope) != scope_signature_fragment(raw_scope)


def test_unauthorized_admin_prefix_keeps_channel_scope():
    cfg = {
        "mattermost": {
            "pd_one_admin_prefix": {"allow_from": ["admin-user"]},
            "pd_one_channel_scopes": {
                "admin-channel": {"agent_id": "admin", "allowed_toolsets": ["terminal"]},
                "employee-channel": {"agent_id": "employee-assistant", "allowed_toolsets": ["skills"]},
            },
        }
    }

    scope = resolve_pd_one_channel_scope(
        cfg,
        "mattermost",
        "employee-channel",
        user_id="regular-user",
        text="admin: fix the capability",
    )

    assert scope is not None
    assert scope["agent_id"] == "employee-assistant"
    assert "admin_prefix_invoked" not in scope


def test_admin_prefix_authorization_can_use_policy_cache_roles(tmp_path):
    policy_dir = tmp_path / "users"
    policy_dir.mkdir()
    (policy_dir / "andy.json").write_text(
        '{"found": true, "active": true, "roles": ["admin"]}',
        encoding="utf-8",
    )
    cfg = {
        "mattermost": {
            "pd_one_policy_cache_users": str(policy_dir),
            "pd_one_channel_scopes": {
                "admin-channel": {"agent_id": "admin", "allowed_toolsets": ["terminal"]},
                "employee-channel": {"agent_id": "employee-assistant", "allowed_toolsets": ["skills"]},
            },
        }
    }

    scope = resolve_pd_one_channel_scope(
        cfg,
        "mattermost",
        "employee-channel",
        user_id="andy",
        text="admin: fix the capability",
    )

    assert scope is not None
    assert scope["agent_id"] == "admin"


def test_resolve_scope_disabled_for_non_mattermost_platform():
    cfg = {
        "mattermost": {
            "pd_one_channel_scopes": {
                "finance-channel": {"agent_id": "finance"}
            }
        }
    }

    assert resolve_pd_one_channel_scope(cfg, "telegram", "finance-channel") is None


def test_resolve_scope_from_gateway_platform_extra_shape():
    cfg = {
        "platforms": {
            "mattermost": {
                "extra": {
                    "pd_one_channel_scopes": {
                        "finance-channel": {"agent_id": "finance"}
                    }
                }
            }
        }
    }

    scope = resolve_pd_one_channel_scope(cfg, "mattermost", "finance-channel")

    assert scope is not None
    assert scope["agent_id"] == "finance"


def test_load_gateway_config_bridges_mattermost_channel_scopes_into_platform_extra(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    (hermes_home / "config.yaml").write_text(
        """
mattermost:
  enabled: true
  pd_one_admin_prefix:
    allow_from:
    - testuser000000000000000001
  pd_one_channel_scopes:
    finance-channel:
      agent_id: finance
platforms:
  mattermost:
    enabled: true
    token: test-token
    extra:
      url: https://mm.example.com
""".strip(),
        encoding="utf-8",
    )

    from gateway.config import load_gateway_config

    cfg = load_gateway_config()

    scopes = cfg.platforms[Platform.MATTERMOST].extra["pd_one_channel_scopes"]
    assert scopes["finance-channel"]["agent_id"] == "finance"
    admin_prefix = cfg.platforms[Platform.MATTERMOST].extra["pd_one_admin_prefix"]
    assert admin_prefix["allow_from"] == [_ADMIN_USER_ID]



def test_scoped_skills_accepts_string_list_and_dedupes():
    assert scoped_skills({"skills": "google-docs-work-manual"}) == ["google-docs-work-manual"]
    assert scoped_skills({"skills": ["a", "b", "a", ""]}) == ["a", "b"]
    assert scoped_skills({"agent_id": "work-manual"}) == []

def test_scoped_toolsets_ignore_channel_allowlist_keep_platform_and_reviewed_extensions():
    scope = {"allowed_toolsets": ["skills", "file", "skills", "clarify", "arbitrary_root"]}

    got = scoped_toolsets(["terminal", "web", "file", "skills"], scope)
    assert got[:4] == ["terminal", "web", "file", "skills"]
    assert "pdone_safe_ops" in got
    assert "mcp-pdone_safe_ops" in got
    assert "pdone_worker_scheduling" in got
    assert "arbitrary_root" not in got
    assert "clarify" not in got


def test_scoped_toolsets_never_invent_unreviewed_extensions():
    scope = {"allowed_toolsets": ["pd_one_wiki", "pdone_safe_ops", "evil_plugin"]}
    got = scoped_toolsets(["web"], scope)
    assert got[0] == "web"
    assert "pd_one_wiki" in got
    assert "pdone_safe_ops" in got
    assert "evil_plugin" not in got


def test_scoped_toolsets_leave_platform_toolsets_when_scope_has_no_allowlist():
    got = scoped_toolsets(["terminal", "web"], {"agent_id": "finance"})
    assert got[:2] == ["terminal", "web"]
    assert "pdone_safe_ops" in got


def test_build_scope_prompt_contains_hard_boundary_and_paths():
    scope = {
        "agent_id": "finance",
        "name": "PD One Finance",
        "workspace": _FINANCE_WORKSPACE,
        "allowed_toolsets": ["file", "skills"],
        "skills": ["excel-author"],
        "prompt": "Finance only.",
    }

    prompt = build_scope_prompt(scope, channel_id="finance-channel")

    assert "PD One channel scope" in prompt
    assert "finance" in prompt
    assert "finance-channel" in prompt
    assert _FINANCE_WORKSPACE in prompt
    assert "file, skills" in prompt
    assert "Finance only." in prompt
    assert "If the request exceeds this channel scope" in prompt


def test_build_scope_prompt_instructs_wiki_candidate_emission_when_toolset_enabled():
    scope = {
        "agent_id": "senior-staff",
        "name": "PD One Inter-Department Discussion",
        "allowed_toolsets": ["skills", "pd_one_wiki"],
    }

    prompt = build_scope_prompt(scope, channel_id=_DISCUSSION_CHANNEL_ID)

    assert "Wiki candidate workflow" in prompt
    assert "emit_wiki_update_candidate" in prompt
    assert "source_channel_id" in prompt
    assert _DISCUSSION_CHANNEL_ID in prompt


def test_scope_signature_fragment_changes_with_agent_toolsets_and_prompt():
    a = {
        "agent_id": "finance",
        "allowed_toolsets": ["file"],
        "prompt": "Finance only.",
    }
    b = {
        "agent_id": "hr",
        "allowed_toolsets": ["skills"],
        "prompt": "HR only.",
    }

    assert scope_signature_fragment(a) != scope_signature_fragment(b)
    assert scope_signature_fragment(a) == scope_signature_fragment(dict(a))


def test_scope_signature_includes_channel_sender_and_admin_state():
    base = {
        "agent_id": "employee-assistant",
        "channel_id": "channel-a",
        "sender_user_id": "user-a",
        "admin_prefix_invoked": False,
        "allowed_toolsets": ["file"],
    }
    for key, value in (
        ("channel_id", "channel-b"),
        ("sender_user_id", "user-b"),
        ("admin_prefix_invoked", True),
    ):
        changed = dict(base)
        changed[key] = value
        assert scope_signature_fragment(base) != scope_signature_fragment(changed)


def test_mattermost_id_placeholders_keep_wire_shape():
    for value in (_ADMIN_USER_ID, _DISCUSSION_CHANNEL_ID):
        assert len(value) == 26
        assert value.isalnum()
        assert value.islower()
        assert value.startswith("test")


def _use_standin_home(monkeypatch, home: Path) -> None:
    """Point profile-root resolution at *home* and drop any cached answer."""
    import hermes_constants

    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.delenv("HERMES_DATA_DIR_SUFFIX", raising=False)
    monkeypatch.setattr(hermes_constants, "_default_hermes_root_memo", None)


def test_pdone_profile_home_uses_user_home_when_hermes_home_unset(monkeypatch):
    home = Path("/home/testhost")
    _use_standin_home(monkeypatch, home)
    monkeypatch.delenv("HERMES_HOME", raising=False)

    assert pdone_profile_home() == home / ".hermes" / "profiles" / "pdone"


def test_pdone_profile_home_honors_hermes_home_root(monkeypatch):
    home = Path("/home/testhost")
    _use_standin_home(monkeypatch, home)
    monkeypatch.setenv("HERMES_HOME", str(home / ".hermes"))

    assert pdone_profile_home() == home / ".hermes" / "profiles" / "pdone"


def test_pdone_profile_home_honors_custom_hermes_home(monkeypatch, tmp_path):
    home = Path("/home/testhost")
    custom = tmp_path / "custom-root"
    _use_standin_home(monkeypatch, home)
    monkeypatch.setenv("HERMES_HOME", str(custom))

    assert pdone_profile_home() == custom / "profiles" / "pdone"


def test_dashboard_and_policy_bridge_share_pdone_profile_home(monkeypatch):
    home = Path("/home/testhost")
    _use_standin_home(monkeypatch, home)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    for name in (
        "PD_ONE_HERMES_POLICY_ROOT",
        "PD_ONE_POLICY_ROOT",
        "PD_ONE_OPENCLAW_WORKSPACE",
    ):
        monkeypatch.delenv(name, raising=False)

    plugin_path = (
        Path(__file__).resolve().parents[2]
        / "plugins"
        / "pd-one-ops"
        / "dashboard"
        / "plugin_api.py"
    )
    spec = importlib.util.spec_from_file_location("pd_one_ops_plugin_api_under_test", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    from gateway.config import PlatformConfig
    from plugins.platforms.mattermost.adapter import MattermostAdapter

    expected = home / ".hermes" / "profiles" / "pdone"
    assert module._pdone_home() == expected

    adapter = MattermostAdapter(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={"url": "https://mm.example.com", "pd_one_policy_bridge": "true"},
        )
    )
    text = adapter._build_pd_one_policy_context(_ADMIN_USER_ID, _DISCUSSION_CHANNEL_ID, "channel")
    assert text is not None
    assert str(expected / "policies" / "mattermost-channels.md") in text
