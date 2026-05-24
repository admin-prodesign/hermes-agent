"""Tests for PD One/OpenClaw-style per-channel Mattermost scope routing."""

from gateway.config import Platform
from gateway.pd_one_channel_scopes import (
    build_scope_prompt,
    resolve_pd_one_channel_scope,
    scoped_toolsets,
    scope_signature_fragment,
)


def test_resolve_scope_from_mattermost_channel_config():
    cfg = {
        "mattermost": {
            "pd_one_channel_scopes": {
                "finance-channel": {
                    "agent_id": "finance",
                    "name": "PD One Finance",
                    "workspace": "/home/prodesign/.openclaw/workspace-finance",
                    "allowed_toolsets": ["file", "skills", "clarify"],
                    "prompt": "Finance only.",
                }
            }
        }
    }

    scope = resolve_pd_one_channel_scope(cfg, "mattermost", "finance-channel")

    assert scope is not None
    assert scope["agent_id"] == "finance"
    assert scope["workspace"] == "/home/prodesign/.openclaw/workspace-finance"


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


def test_scoped_toolsets_replace_platform_toolsets_and_preserve_order():
    scope = {"allowed_toolsets": ["skills", "file", "skills", "clarify"]}

    assert scoped_toolsets(["terminal", "web", "file"], scope) == [
        "skills",
        "file",
        "clarify",
    ]


def test_scoped_toolsets_leave_platform_toolsets_when_scope_has_no_allowlist():
    assert scoped_toolsets(["terminal", "web"], {"agent_id": "finance"}) == [
        "terminal",
        "web",
    ]


def test_build_scope_prompt_contains_hard_boundary_and_paths():
    scope = {
        "agent_id": "finance",
        "name": "PD One Finance",
        "workspace": "/home/prodesign/.openclaw/workspace-finance",
        "allowed_toolsets": ["file", "skills"],
        "skills": ["excel-author"],
        "prompt": "Finance only.",
    }

    prompt = build_scope_prompt(scope, channel_id="finance-channel")

    assert "PD One channel scope" in prompt
    assert "finance" in prompt
    assert "finance-channel" in prompt
    assert "/home/prodesign/.openclaw/workspace-finance" in prompt
    assert "file, skills" in prompt
    assert "Finance only." in prompt
    assert "If the request exceeds this channel scope" in prompt


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
