"""Pre-cutover gate: every enabled gateway adapter must start from the new release.

For each profile, the gateway unit and its drop-ins are rendered against the new
release in memory (nothing is written), and ``adapter_probe`` runs in the new
release's interpreter with the environment that unit would give the gateway:
``Environment=`` and ``EnvironmentFile=`` from the base unit and every drop-in,
and ``HERMES_HOME`` of the profile unless the unit sets its own. A missing
dependency, an adapter that cannot be created, or a declared requirement of the
build's extra that is not installed refuses the cutover before anything changes.
The platforms each profile started go to ``adapters.json`` in the build audit;
the post-restart verify expects them connected.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from scripts.deploy.nemo.layout import gateway_unit_name, profile_home
from scripts.deploy.nemo.units import Target, UnitFile, environment, environment_files, render

PROBE_TIMEOUT_S = 180.0
ADAPTERS_FILE = "adapters.json"
Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class ProfileProbe:
    profile: str
    home: Path
    unit: str
    env: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def unit_environment(files: list[UnitFile], unit: str, target: Target) -> tuple[dict[str, str], list[str]]:
    """Environment the rendered unit gives its process; ``EnvironmentFile=`` overrides
    ``Environment=`` as in systemd. Returns ``(env, errors)``."""
    env: dict[str, str] = {}
    from_files: dict[str, str] = {}
    errors: list[str] = []
    for item in files:
        if item.unit != unit:
            continue
        text = render(item.path.read_text(encoding="utf-8-sig"), target)
        env.update(environment(text))
        for path, optional in environment_files(text):
            if path.is_file():
                from_files.update(_read_env_file(path))
            elif not optional:
                errors.append(f"{item.path}: EnvironmentFile {path} does not exist")
    env.update(from_files)
    return env, errors


def plan_probes(
    home: Path, profiles: tuple[str, ...], files: list[UnitFile], target: Target,
    overrides: dict[str, str] | None = None,
) -> list[ProfileProbe]:
    probes: list[ProfileProbe] = []
    for name in profiles:
        unit = gateway_unit_name(name, overrides)
        env, errors = unit_environment(files, unit, target)
        probes.append(ProfileProbe(name, Path(env.get("HERMES_HOME") or profile_home(home, name)),
                                   unit, env, errors))
    return probes


def probe_env(probe: ProfileProbe, base: dict[str, str]) -> dict[str, str]:
    """The caller's environment minus the worker's own interpreter settings, plus the unit's."""
    env = {key: value for key, value in base.items() if key not in {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"}}
    env["HERMES_HOME"] = str(probe.home)
    env.update(probe.env)
    return env


def run_gate(
    release: Path, probes: list[ProfileProbe], out_dir: Path, *, extras: list[str],
    python: Path | None = None, run: Runner = subprocess.run, timeout: float = PROBE_TIMEOUT_S,
) -> tuple[bool, dict]:
    interpreter = python or release / ".venv" / "bin" / "python"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    for probe in probes:
        out = out_dir / f"adapters-{probe.profile}.json"
        out.unlink(missing_ok=True)
        argv = [str(interpreter), "-m", "scripts.deploy.nemo.adapter_probe", "--out", str(out)]
        for extra in extras:
            argv += ["--extra", extra]
        entry: dict = {"home": str(probe.home), "unit": probe.unit, "platforms": [],
                       "failures": [{"platform": "*", "detail": error} for error in probe.errors],
                       "missing": []}
        try:
            done = run(argv, cwd=str(release), env=probe_env(probe, dict(os.environ)), timeout=timeout,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
            code, stderr = done.returncode, (done.stderr or b"")
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, stderr = 1, str(exc).encode()
        if out.is_file():
            report = json.loads(out.read_text(encoding="utf-8-sig"))
            entry["platforms"] = list(report.get("platforms") or [])
            entry["failures"] += list(report.get("failures") or [])
            entry["missing"] = list(report.get("missing") or [])
        elif code != 0:
            tail = stderr.decode("utf-8", "replace").strip()[-1000:]
            entry["failures"].append({"platform": "*", "detail": f"probe exited {code}: {tail}"})
        results[probe.profile] = entry
    ok = all(not item["failures"] and not item["missing"] for item in results.values())
    (out_dir / ADAPTERS_FILE).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ok, results


def summary(results: dict) -> list[str]:
    lines: list[str] = []
    for profile, entry in results.items():
        started = ", ".join(entry["platforms"]) or "no adapters"
        lines.append(f"{profile} ({entry['unit']}): {started}")
        lines.extend(f"  fail {item['platform']}: {item['detail']}" for item in entry["failures"])
        lines.extend(f"  missing {item}" for item in entry["missing"])
    return lines
