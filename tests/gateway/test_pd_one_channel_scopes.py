"""Tests for PD One/OpenClaw-style per-channel Mattermost scope routing."""

from gateway.config import Platform
from gateway.pd_one_channel_scopes import (
    build_scope_prompt,
    resolve_pd_one_channel_scope,
    scoped_skills,
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


def test_authorized_admin_prefix_overrides_employee_channel_scope():
    cfg = {
        "mattermost": {
            "pd_one_admin_prefix": {"allow_from": ["5nak6m7nmf8kudbrwbtccazbgc"]},
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
        user_id="5nak6m7nmf8kudbrwbtccazbgc",
        text="admin: fix the capability",
    )

    assert scope is not None
    assert scope["agent_id"] == "admin"
    assert scope["admin_prefix_invoked"] is True
    assert scope["original_channel_scope"]["agent_id"] == "employee-assistant"
    assert scoped_toolsets(["skills"], scope) == ["terminal", "file"]


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
    - 5nak6m7nmf8kudbrwbtccazbgc
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
    assert admin_prefix["allow_from"] == ["5nak6m7nmf8kudbrwbtccazbgc"]



def test_scoped_skills_accepts_string_list_and_dedupes():
    assert scoped_skills({"skills": "google-docs-work-manual"}) == ["google-docs-work-manual"]
    assert scoped_skills({"skills": ["a", "b", "a", ""]}) == ["a", "b"]
    assert scoped_skills({"agent_id": "work-manual"}) == []

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


def test_build_scope_prompt_instructs_wiki_candidate_emission_when_toolset_enabled():
    scope = {
        "agent_id": "senior-staff",
        "name": "PD One Inter-Department Discussion",
        "allowed_toolsets": ["skills", "pd_one_wiki"],
    }

    prompt = build_scope_prompt(scope, channel_id="miiyt4zm9frexdbhxokxqgyxeo")

    assert "Wiki candidate workflow" in prompt
    assert "emit_wiki_update_candidate" in prompt
    assert "source_channel_id" in prompt


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
