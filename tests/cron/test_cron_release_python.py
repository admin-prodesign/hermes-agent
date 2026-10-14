"""Profile cron scripts run on the release venv, including shell wrappers.

The pdone HR-sync, reaper, and digest jobs failed when a bare ``python3``
loaded them. ``.py`` is launched with the release interpreter. Wrappers and
``#!/usr/bin/env python3`` children see that interpreter's ``bin`` first on
``PATH``, without resolving a venv symlink onto the system directory.
"""

import shlex
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    (hermes_home / "cron" / "output").mkdir(parents=True)
    (hermes_home / "scripts").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    import cron.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "HERMES_DIR", hermes_home)
    monkeypatch.setattr(jobs_mod, "CRON_DIR", hermes_home / "cron")
    monkeypatch.setattr(jobs_mod, "JOBS_FILE", hermes_home / "cron" / "jobs.json")
    monkeypatch.setattr(jobs_mod, "OUTPUT_DIR", hermes_home / "cron" / "output")
    return hermes_home


def _pin_release_venv(monkeypatch, venv: Path) -> None:
    monkeypatch.setattr("hermes_cli._launchers.resolve_store_python", lambda repo: None)
    monkeypatch.setattr("hermes_constants.project_venv_dir", lambda repo: venv)


def _venv(tmp_path: Path, name: str) -> Path:
    venv = tmp_path / name
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text(
        "home = /usr/bin\ninclude-system-site-packages = false\n",
        encoding="utf-8",
    )
    return venv


def _symlink_python(venv: Path) -> Path:
    """A venv ``python3`` that is a symlink, the usual layout."""
    python = venv / "bin" / "python3"
    python.symlink_to(sys.executable)
    return python


def _marker_python(venv: Path, marker: str) -> Path:
    """An executable named ``python3`` that announces itself, then runs real Python."""
    python = venv / "bin" / "python3"
    python.write_text(
        "#!/bin/sh\n"
        f"echo {marker}\n"
        f"exec {shlex.quote(sys.executable)} \"$@\"\n",
        encoding="utf-8",
    )
    python.chmod(python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return python


@pytest.mark.platforms("posix")
def test_shell_wrapper_finds_release_python_without_resolving_the_symlink(
    cron_env, tmp_path, monkeypatch
):
    """``python3`` inside a ``.sh`` wrapper is the release venv's symlink, not ``/usr/bin``."""
    venv = _venv(tmp_path, "release-venv")
    python = _symlink_python(venv)
    _pin_release_venv(monkeypatch, venv)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    script = cron_env / "scripts" / "reaper.sh"
    script.write_text(
        "#!/bin/sh\n"
        "python3 -c 'import os, shutil\n"
        "path0 = os.environ[\"PATH\"].split(os.pathsep)[0]\n"
        "print(\"PATH0=\" + path0)\n"
        "print(\"WHICH=\" + shutil.which(\"python3\"))\n"
        "print(\"VENV=\" + os.environ.get(\"VIRTUAL_ENV\", \"\"))\n"
        "print(\"CWA=\" + os.environ.get(\"_HERMES_CRON_CWA_TLS\", \"\"))\n"
        "print(\"PY=\" + str(\"cwa_site\" in (os.environ.get(\"PYTHONPATH\") or \"\")))'\n",
        encoding="utf-8",
    )
    from cron.scheduler_script import _run_job_script

    success, output = _run_job_script("reaper.sh")
    assert success is True, output
    path0, which, virtual_env, cwa, pypath = output.splitlines()
    assert Path(path0.removeprefix("PATH0=")) == python.parent
    assert Path(path0.removeprefix("PATH0=")) != Path(sys.executable).resolve().parent
    assert Path(which.removeprefix("WHICH=")) == python
    assert Path(virtual_env.removeprefix("VENV=")) == venv
    assert cwa == "CWA="
    assert pypath == "PY=False"


@pytest.mark.platforms("posix")
def test_py_shebang_still_runs_on_the_release_interpreter(cron_env, tmp_path, monkeypatch):
    """A ``#!/usr/bin/env python3`` line on the cron script is not the launcher."""
    venv = _venv(tmp_path, "release-venv")
    _marker_python(venv, "release-python")
    _pin_release_venv(monkeypatch, venv)
    script = cron_env / "scripts" / "digest.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "print('body')\n",
        encoding="utf-8",
    )
    from cron.scheduler_script import _run_job_script

    success, output = _run_job_script("digest.py")
    assert success is True, output
    assert output.splitlines() == ["release-python", "body"]


@pytest.mark.platforms("posix")
def test_job_interpreter_bin_leads_path_for_py_only(cron_env, tmp_path, monkeypatch):
    """A job interpreter replaces the release pin for ``.py`` and not for shell."""
    release = _venv(tmp_path, "release-venv")
    _marker_python(release, "release-python")
    user = _venv(tmp_path, "user-venv")
    user_python = _marker_python(user, "user-python")
    _pin_release_venv(monkeypatch, release)
    from cron.scheduler_script import _run_job_script

    py = cron_env / "scripts" / "job.py"
    py.write_text("print('py-body')\n", encoding="utf-8")
    success, output = _run_job_script("job.py", interpreter=str(user_python))
    assert success is True, output
    assert output.splitlines() == ["user-python", "py-body"]

    shell = cron_env / "scripts" / "wrap.sh"
    shell.write_text(
        "#!/bin/sh\npython3 -c 'print(\"shell-body\")'\n",
        encoding="utf-8",
    )
    success, output = _run_job_script("wrap.sh", interpreter=str(user_python))
    assert success is True, output
    assert output.splitlines() == ["release-python", "shell-body"]


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("script_name, body_host", [
    ("fetch.py", True),
    ("typhoon_check.py", False),
])
def test_cwa_typhoon_script_arms_tls_hook_only_for_that_script(
    cron_env, tmp_path, monkeypatch, script_name, body_host
):
    """The strict-flag exception loads for a CWA or typhoon script and not for others."""
    venv = _venv(tmp_path, "release-venv")
    _symlink_python(venv)
    _pin_release_venv(monkeypatch, venv)
    from cron.scheduler_script import _run_job_script

    probe = (
        "import os, urllib.request\n"
        "print('FLAG=' + os.environ.get('_HERMES_CRON_CWA_TLS', ''))\n"
        "hook = 'cwa_site' in (os.environ.get('PYTHONPATH') or '')\n"
        "print('HOOK=' + str(hook))\n"
        "print('URLOPEN=' + str(getattr(urllib.request.urlopen, '_hermes_cwa_tls', False)))\n"
        "try:\n"
        "    from requests.sessions import Session\n"
        "    print('REQUESTS=' + str(getattr(Session, '_hermes_cwa_tls', False)))\n"
        "except ImportError:\n"
        "    print('REQUESTS=absent')\n"
    )
    if body_host:
        probe = "URL = 'https://www.cwa.gov.tw/V8/C/P/Typhoon/'\n" + probe
    (cron_env / "scripts" / script_name).write_text(probe, encoding="utf-8")
    success, output = _run_job_script(script_name)
    assert success is True, output
    flag, hook, urlopen, requests_flag = output.splitlines()
    assert flag == "FLAG=1"
    assert hook == "HOOK=True"
    assert urlopen == "URLOPEN=True"
    assert requests_flag in {"REQUESTS=True", "REQUESTS=absent"}

    # The control file must not be named typhoon and must not mention the host.
    (cron_env / "scripts" / "other.py").write_text(
        "import os, urllib.request\n"
        "print('FLAG=' + os.environ.get('_HERMES_CRON_CWA_TLS', ''))\n"
        "hook = 'cwa_site' in (os.environ.get('PYTHONPATH') or '')\n"
        "print('HOOK=' + str(hook))\n"
        "print('URLOPEN=' + str(getattr(urllib.request.urlopen, '_hermes_cwa_tls', False)))\n",
        encoding="utf-8",
    )
    success, output = _run_job_script("other.py")
    assert success is True, output
    assert output.splitlines() == ["FLAG=", "HOOK=False", "URLOPEN=False"]
