"""Employees register their own Apps Script projects on the profile home.

Built-in projects stay shared. A self-registered project is usable only by
the session user who registered it, or by a policy-cache admin. The
requester is never taken from a tool argument.
"""
import json
from contextlib import contextmanager

import pytest

from gateway.session_context import clear_session_vars, set_session_vars
from tools.pd_one_ops import apps_script_registry as registry
from tools.pd_one_ops import pd_one_safe_ops_mcp_part0 as part0
from tools.pd_one_ops import pd_one_safe_ops_mcp_part1 as part1

SCRIPT = "EmpScript01"
PARENT = "ParentFile01"
ADMIN = "ops@prodesign-group.com"
ADA_EMAIL = "ada@prodesign-group.com"
ADA = "user-ada"
BOB = "user-bob"
ADMIN_USER = "user-admin"
HR_USER = "user-hr"
OUTSIDER = "outsider@gmail.com"
REGISTER_PHRASE = "RUN LIVE APPS SCRIPT REGISTER"
PATCH_PHRASE = "RUN LIVE APPS SCRIPT PATCH"
BUILTIN_IDS = {
    "PDONE_APPS_SCRIPT_WORKER_SCHEDULING": "builtin-worker-id",
    "PDONE_APPS_SCRIPT_APPSHEET_HELPER": "builtin-helper-id",
    "PDONE_APPS_SCRIPT_APPSHEET_DATA_MIRROR": "builtin-mirror-id",
    "PDONE_APPS_SCRIPT_FINANCE_FOREX": "builtin-forex-id",
}
BUILTIN_KEYS = (
    "worker_scheduling",
    "appsheet_helper",
    "appsheet_data_mirror",
    "finance_forex_notification",
)


@pytest.fixture(autouse=True)
def _profile(monkeypatch, tmp_path):
    home = tmp_path / "profile"
    home.mkdir()
    cache = tmp_path / "policies"
    cache.mkdir()
    monkeypatch.setenv("HERMES_PROFILE_HOME", str(home))
    monkeypatch.delenv("PD_ONE_PROFILE_HOME", raising=False)
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
    monkeypatch.setenv("PDONE_EMAIL_ADMIN", ADMIN)
    for name, value in BUILTIN_IDS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("tools.pd_one_safe_ops.policy_cache_directory", lambda: str(cache))
    clear_session_vars([])
    yield type("Profile", (), {"home": home, "cache": cache})()
    clear_session_vars([])


@pytest.fixture
def profile(_profile):
    return _profile


def _write_user(profile, user_id, email, roles):
    payload = {
        "found": True,
        "active": True,
        "roles": roles,
        "identity": {"companyEmails": [email]},
    }
    (profile.cache / f"{user_id}.json").write_text(json.dumps(payload), encoding="utf-8")


@contextmanager
def _bound(user_id):
    tokens = set_session_vars(platform="mattermost", user_id=user_id)
    try:
        yield
    finally:
        clear_session_vars(tokens)


def _call(**kwargs):
    return json.loads(part1.apps_script_project_ops(**kwargs))


def _registry_file(profile):
    return profile.home / "pd-one" / "apps-script-registry.json"


def _audit_file(profile):
    return profile.home / "pd-one" / "apps-script-audit.jsonl"


def _install_google(monkeypatch, *, role="writer", email=ADA_EMAIL, drive_error=None, files=None):
    def token(account):
        assert account == ADMIN
        return "ya29.test-token"

    def api(url, *, token, method="GET", body=None, timeout=120):
        assert token == "ya29.test-token"
        if "script.googleapis.com" in url:
            return {"scriptId": SCRIPT, "title": "Employee Tool", "parentId": PARENT}
        if "/permissions" in url:
            return {"permissions": [{"type": "user", "role": role, "emailAddress": email}]}
        if "google-apps.script" in url or "mimeType" in url:
            rows = files if files is not None else [{"id": SCRIPT, "name": "Employee Tool"}]
            return {"files": rows}
        if drive_error:
            raise RuntimeError(drive_error)
        return {"id": PARENT, "name": "Container"}

    monkeypatch.setattr(part0, "_google_access_token", token)
    monkeypatch.setattr(part0, "_google_api_json", api)


def _block_content(monkeypatch):
    def fail_content(_project):
        raise AssertionError("script content was loaded")

    monkeypatch.setattr(part1, "_load_apps_script_content", fail_content)


def test_cross_requester_access_denied(monkeypatch, profile):
    _install_google(monkeypatch)
    _block_content(monkeypatch)
    _write_user(profile, ADA, ADA_EMAIL, ["employee"])
    _write_user(profile, BOB, "bob@prodesign-group.com", ["employee"])
    _write_user(profile, HR_USER, "hr@prodesign-group.com", ["hr"])
    _write_user(profile, ADMIN_USER, "admin@prodesign-group.com", ["admin"])
    with _bound(ADA):
        registered = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
            dry_run=False,
            confirm_live_register=REGISTER_PHRASE,
        )
    assert registered["status"] == "ok"
    assert registered["registered_by"] == ADA
    assert registered["written"] is True

    with _bound(BOB):
        listed = _call(action="list_registered_projects")
        denied = _call(action="get_content", project_key="employee_tool")
        patch = _call(
            action="unique_text_patch",
            project_key="employee_tool",
            old_string="return 1",
            new_string="return 2",
        )
    keys = {row["project_key"] for row in listed["projects"]}
    assert "employee_tool" not in keys
    assert set(BUILTIN_KEYS) <= keys
    assert denied["detail"] == "access_denied"
    assert patch["detail"] == "access_denied"

    with _bound(HR_USER):
        hr_listed = _call(action="list_registered_projects")
    assert "employee_tool" not in {row["project_key"] for row in hr_listed["projects"]}

    with _bound(ADMIN_USER):
        admin_listed = _call(action="list_registered_projects")
    assert "employee_tool" in {row["project_key"] for row in admin_listed["projects"]}


def test_non_owner_registration_refused(monkeypatch, profile):
    _install_google(monkeypatch, role="reader")
    _write_user(profile, ADA, ADA_EMAIL, ["employee"])
    with _bound(ADA):
        payload = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
        )
    assert payload["detail"] == "requester_not_owner_or_writer"
    assert not _registry_file(profile).exists()


def test_other_domain_refused(monkeypatch, profile):
    _install_google(monkeypatch, role="owner", email=OUTSIDER)
    _write_user(profile, ADA, OUTSIDER, ["employee"])
    with _bound(ADA):
        payload = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
            dry_run=False,
            confirm_live_register=REGISTER_PHRASE,
        )
    assert payload["detail"] == "outside_company_domain"
    assert not _registry_file(profile).exists()


def test_model_supplied_requester_ignored(monkeypatch, profile):
    _install_google(monkeypatch)
    _write_user(profile, ADA, OUTSIDER, ["employee"])
    _write_user(profile, ADMIN_USER, "admin@prodesign-group.com", ["admin"])
    with _bound(ADA):
        refused = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
            requester_email=ADA_EMAIL,
            requester_user_id=ADMIN_USER,
            registered_by=ADMIN_USER,
        )
    assert refused["detail"] == "outside_company_domain"
    assert not _registry_file(profile).exists()

    _write_user(profile, ADA, ADA_EMAIL, ["employee"])
    with _bound(ADA):
        accepted = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
            dry_run=False,
            confirm_live_register=REGISTER_PHRASE,
            requester_email=OUTSIDER,
            requester_user_id=ADMIN_USER,
            registered_by=ADMIN_USER,
        )
    assert accepted["registered_by"] == ADA
    stored = json.loads(_registry_file(profile).read_text(encoding="utf-8"))
    assert stored["projects"]["employee_tool"]["registered_by"] == ADA
    assert ADMIN_USER not in json.dumps(stored)


def test_builtins_unchanged_when_registry_overrides(profile):
    path = _registry_file(profile)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema": "pd-one.apps-script-registry.v1",
        "projects": {
            "worker_scheduling": {
                "script_id": "replaced-by-registry",
                "registered_by": ADA,
                "account": ADMIN,
                "title": "override",
                "allowed_actions": ["get_content"],
            },
            "employee_tool": {
                "script_id": SCRIPT,
                "parent_file_id": PARENT,
                "registered_by": ADA,
                "account": ADMIN,
                "title": "Employee Tool",
                "system": "employee_registered",
                "allowed_actions": ["get_content", "verify_readback", "unique_text_patch", "staged_file_replace"],
            },
        },
    }), encoding="utf-8")
    _write_user(profile, BOB, "bob@prodesign-group.com", ["employee"])

    merged = part0.APPS_SCRIPT_ALLOWED_PROJECTS()
    assert merged["worker_scheduling"]["script_id"] == "builtin-worker-id"
    assert merged["appsheet_helper"]["script_id"] == "builtin-helper-id"
    assert merged["appsheet_data_mirror"]["script_id"] == "builtin-mirror-id"
    assert merged["finance_forex_notification"]["script_id"] == "builtin-forex-id"
    assert "registered_by" not in merged["worker_scheduling"]

    with _bound(BOB):
        listed = _call(action="list_registered_projects")
    keys = {row["project_key"] for row in listed["projects"]}
    assert set(BUILTIN_KEYS) <= keys
    assert "employee_tool" not in keys
    worker = next(row for row in listed["projects"] if row["project_key"] == "worker_scheduling")
    assert worker["script_id"] == "builtin-worker-id"
    assert "registered_by" not in worker


def test_audit_lines_record_register_patch_and_readback(monkeypatch, profile):
    _install_google(monkeypatch)
    _write_user(profile, ADA, ADA_EMAIL, ["employee"])
    source = "function ping(){ return 1; }"
    monkeypatch.setattr(
        part1,
        "_load_apps_script_content",
        lambda _project: {"files": [{"name": "Code", "type": "SERVER_JS", "source": source}]},
    )
    monkeypatch.setattr(
        part1,
        "_apps_script_syntax_check",
        lambda *_args, **_kwargs: {"skipped": False, "returncode": 0},
    )
    with _bound(ADA):
        dry = _call(action="register_project", project_key="employee_tool", script_id=SCRIPT)
        assert dry["dry_run"] is True
        assert dry["written"] is False
        assert not _registry_file(profile).exists()
        missing_phrase = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
            dry_run=False,
            confirm_live_patch=PATCH_PHRASE,
        )
        assert REGISTER_PHRASE in missing_phrase["detail"]
        assert not _registry_file(profile).exists()
        _call(
            action="register_project",
            project_key="employee_tool",
            parent_file_id=PARENT,
            dry_run=False,
            confirm_live_register=REGISTER_PHRASE,
        )
        readback = _call(
            action="verify_readback",
            project_key="employee_tool",
            file_name="Code",
            required_strings=["return 1"],
        )
        patch = _call(
            action="unique_text_patch",
            project_key="employee_tool",
            file_name="Code",
            old_string="return 1",
            new_string="return 2",
        )
    assert readback["status"] == "ok"
    assert patch["status"] == "ok"
    assert patch["dry_run"] is True
    text = _audit_file(profile).read_text(encoding="utf-8")
    assert "return 1" not in text
    assert "return 2" not in text
    assert "ya29.test-token" not in text
    assert "refresh_token" not in text
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    assert [row["action"] for row in rows] == [
        "register", "register", "register", "readback", "patch",
    ]
    assert [row["result"] for row in rows] == [
        "dry_run", "error", "registered", "ok", "dry_run",
    ]
    for row in rows:
        assert set(row) == {"who", "at", "script_id", "action", "result"}
        assert row["who"] == ADA
        assert row["script_id"] == SCRIPT
        assert row["at"].endswith("Z")
    stored = _registry_file(profile)
    assert stored.is_file()
    assert str(stored).startswith(str(profile.home))
    assert "tools/pd_one_ops" not in str(stored)
    assert (stored.stat().st_mode & 0o777) == 0o600


def test_gog_token_scope_report_hides_secrets(monkeypatch, tmp_path):
    config = tmp_path / "gogcli"
    config.mkdir()
    (config / "credentials-prodesign-admin.json").write_text(
        json.dumps({"installed": {"client_secret": "client-secret-value", "client_id": "id"}}),
        encoding="utf-8",
    )
    (config / "token.json").write_text(json.dumps({
        "refresh_token": "refresh-secret-value",
        "scopes": [
            "https://www.googleapis.com/auth/script.projects",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(registry, "gogcli_config_dir", lambda: config)
    payload = _call(action="check_gog_scopes")
    encoded = json.dumps(payload)
    assert payload["has_script_projects"] is True
    assert payload["has_drive_read"] is True
    assert payload["status"] == "ok"
    assert "refresh-secret-value" not in encoded
    assert "client-secret-value" not in encoded
    assert "gog auth add" in payload["remediation"]
    assert "script.projects" in payload["remediation"]

    (config / "token.json").write_text(json.dumps({
        "refresh_token": "refresh-secret-value",
        "scopes": ["https://www.googleapis.com/auth/script.projects.readonly"],
    }), encoding="utf-8")
    missing = _call(action="check_gog_scopes")
    assert missing["status"] == "missing_scopes"
    assert missing["has_script_projects"] is False
    assert missing["has_drive_read"] is False
    assert "refresh-secret-value" not in json.dumps(missing)


def test_live_patch_still_requires_confirm_phrase():
    payload = _call(
        action="unique_text_patch",
        project_key="worker_scheduling",
        file_name="Code",
        old_string="return 1",
        new_string="return 2",
        dry_run=False,
    )
    assert payload["status"] == "error"
    assert PATCH_PHRASE in payload["detail"]


def test_pd_one_account_without_drive_access_refused(monkeypatch, profile):
    secret = "drive-body-secret"
    _install_google(monkeypatch, drive_error=f"Google API HTTP 403: {secret}")
    _write_user(profile, ADA, ADA_EMAIL, ["employee"])
    with _bound(ADA):
        payload = _call(
            action="register_project",
            project_key="employee_tool",
            script_id=SCRIPT,
        )
    assert payload["detail"] == "pd_one_account_no_access"
    assert secret not in json.dumps(payload)
    assert not _registry_file(profile).exists()
