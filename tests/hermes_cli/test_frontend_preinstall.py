"""A sealed release must not npm-install the dashboard at runtime."""

from pathlib import Path

from hermes_cli.main_web_build import _do_build_web_ui
from hermes_cli.source_build import (
    FRONTEND_PREINSTALL_MARKER, note_runtime_npm_skipped, runtime_npm_install_allowed,
)
from scripts.deploy.nemo.layout import FRONTEND_MARKER_RELATIVE


def test_marker_constant_matches_the_deploy_script() -> None:
    assert FRONTEND_MARKER_RELATIVE == FRONTEND_PREINSTALL_MARKER


def test_runtime_npm_install_follows_the_marker_and_writability(tmp_path: Path, monkeypatch) -> None:
    assert runtime_npm_install_allowed(tmp_path) is True
    marker = tmp_path / FRONTEND_PREINSTALL_MARKER
    marker.parent.mkdir(parents=True)
    marker.write_text("preinstalled\n", encoding="utf-8")
    assert runtime_npm_install_allowed(tmp_path) is False
    marker.unlink()
    (tmp_path / "node_modules").mkdir()
    monkeypatch.setattr("hermes_cli.source_build.os.access", lambda _path, _mode: False)
    assert runtime_npm_install_allowed(tmp_path) is False


def test_sealed_web_build_uses_the_existing_bundle(tmp_path: Path, capsys) -> None:
    from hermes_cli import source_build

    root = tmp_path / "repo"
    web = root / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text("{}\n", encoding="utf-8")
    index = root / "hermes_cli" / "web_dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("ok", encoding="utf-8")
    marker = root / FRONTEND_PREINSTALL_MARKER
    marker.parent.mkdir(parents=True)
    marker.write_text("preinstalled\n", encoding="utf-8")
    source_build._npm_skip_logged = False
    assert _do_build_web_ui(web) is True
    assert capsys.readouterr().err.count("Skipping npm install") == 1
    assert _do_build_web_ui(web) is True
    assert capsys.readouterr().err.count("Skipping npm install") == 0


def test_sealed_web_build_reports_a_missing_bundle(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    web = root / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text("{}\n", encoding="utf-8")
    marker = root / FRONTEND_PREINSTALL_MARKER
    marker.parent.mkdir(parents=True)
    marker.write_text("preinstalled\n", encoding="utf-8")
    assert _do_build_web_ui(web) is False


def test_skip_log_is_once_per_process(capsys) -> None:
    from hermes_cli import source_build

    source_build._npm_skip_logged = False
    note_runtime_npm_skipped()
    note_runtime_npm_skipped()
    assert capsys.readouterr().err.count("Skipping npm install") == 1
