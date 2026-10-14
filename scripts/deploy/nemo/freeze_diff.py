"""Compare ``uv pip freeze`` output. A missing nemo pin fails the build."""

from __future__ import annotations

from scripts.deploy.nemo.layout import NEMO_PACKAGES


def parse_freeze(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-e"):
            continue
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[_normalize(name)] = version.strip()
    return pins


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def constraint_text(text: str) -> str:
    """Drop editable installs. ``uv pip install -c`` cannot use ``-e`` lines."""
    kept = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-e"):
            continue
        kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def compare(old_text: str, new_text: str) -> tuple[str, list[str]]:
    """Return a unified-style report and the nemo packages that disappeared."""
    old, new = parse_freeze(old_text), parse_freeze(new_text)
    lines: list[str] = []
    for name in sorted(set(old) | set(new)):
        if name not in old:
            lines.append(f"+ {name}=={new[name]}")
        elif name not in new:
            lines.append(f"- {name}=={old[name]}")
        elif old[name] != new[name]:
            lines.append(f"~ {name}=={old[name]} -> {name}=={new[name]}")
    missing = [name for name in NEMO_PACKAGES if name in old and name not in new]
    if not lines:
        lines.append("(no pin changes)")
    return "\n".join(lines) + "\n", missing
