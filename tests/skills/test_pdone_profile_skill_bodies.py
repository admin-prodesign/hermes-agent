"""Size guard for PD One profile skills vendored under profiles/pdone/skills/.

Once a listed SKILL.md exists in the repo, it must stay at or under 8192 bytes
so auto_load / skill_view do not pin oversized bodies.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO / "profiles" / "pdone" / "skills"
MAX_SKILL_MD_BYTES = 8192

# Relative to SKILLS_ROOT — matches nemo layout and pd_one_ops path helpers.
PDONE_SKILL_MD_PATHS: dict[str, str] = {
    "pd-one-hermes-permissions": "pd-one-hermes-permissions/SKILL.md",
    "monthly-worker-scheduling": "monthly-worker-scheduling/SKILL.md",
    "appsheet-copilot": "appsheet-copilot/SKILL.md",
    "pd-one-admin": "pd-one-admin/SKILL.md",
    "automation-reliability": "automation-reliability/SKILL.md",
    "automation-source-key-integrity": (
        "automation-reliability/automation-source-key-integrity/SKILL.md"
    ),
    "approval-queue-incident-response": (
        "automation-reliability/approval-queue-incident-response/SKILL.md"
    ),
    "stateful-runner-delivery": (
        "automation-reliability/stateful-runner-delivery/SKILL.md"
    ),
    "gog": "gog/SKILL.md",
    "worker-scheduling-optimization-rules": "worker-scheduling-optimization-rules/SKILL.md",
    "it-meeting-briefing": "it-meeting-briefing/SKILL.md",
    "it-meeting-progress-summary": "it-meeting-progress-summary/SKILL.md",
}


def _skill_md(name: str) -> Path:
    return SKILLS_ROOT / PDONE_SKILL_MD_PATHS[name]


@pytest.mark.parametrize("name", sorted(PDONE_SKILL_MD_PATHS))
def test_pdone_profile_skill_md_at_most_8k_when_vendored(name: str) -> None:
    path = _skill_md(name)
    assert path.is_file(), (
        f"{path.relative_to(REPO)} missing; vendored pdone skills must be present in git"
    )
    size = path.stat().st_size
    assert size <= MAX_SKILL_MD_BYTES, (
        f"{path.relative_to(REPO)} is {size} bytes; lean/split to <= {MAX_SKILL_MD_BYTES} "
        f"(move detail to references/*.md)"
    )


def test_pdone_skill_readme_lists_every_guarded_skill() -> None:
    readme = SKILLS_ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for name in PDONE_SKILL_MD_PATHS:
        needle = name.split("/")[-1] if "/" in name else name
        assert needle in text, f"README should mention {name!r} for operators"
