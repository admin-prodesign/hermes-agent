"""Contracts for the PD One office skills under profiles/pdone/skills/.

The live 2026-11-17 snapshot landed the generic banking pptx-author example.
These checks keep that example out, require the visual render, require the
shared type-size rule, and require matplotlib on the nemo extra.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "profiles" / "pdone" / "skills"

# Skill directories added from the nemo office snapshot. pd-one-admin is a
# different tree and is not part of this guard.
OFFICE_SKILL_DIRS = (
    "finance/pptx-author",
    "pd-one/pd-one-firm-template",
    "pd-one/pd-one-molding-kpi-monthly-deck",
    "pd-one/pd-one-pptx-office-package",
    "pd-one/pd-one-pptx-template-migration",
    "pd-one/notebooklm-pptx-native-rebuild",
    "visual-office-qa",
    "productivity/docx",
    "productivity/xlsx",
    "productivity/pdf",
    "productivity/office-artifact-release-review",
    "creative/pd-one-infographic-generator",
    "creative/powerpoint-to-html-presentation",
)

TYPE_SIZE_SKILLS = (
    "finance/pptx-author/SKILL.md",
    "pd-one/pd-one-firm-template/SKILL.md",
    "pd-one/pd-one-molding-kpi-monthly-deck/SKILL.md",
    "pd-one/pd-one-pptx-office-package/SKILL.md",
    "pd-one/pd-one-pptx-template-migration/SKILL.md",
    "productivity/docx/SKILL.md",
    "productivity/xlsx/SKILL.md",
    "creative/pd-one-infographic-generator/SKILL.md",
    "visual-office-qa/SKILL.md",
)

TYPE_SIZE_RULE = (
    "Type size: titles at least 28 pt; body at least 14 pt; "
    "10 pt only for footnotes and sources. "
    "Shrink or split text that would overflow, and keep content inside "
    "the layout safe area."
)

# Case-insensitive. slide_layouts[ is an index pick; iterating
# master.slide_layouts to match layout.name is the named-layout path.
BANNED_TERMS = (
    "project aurora",
    "football-field",
    "football_field",
    "football field",
    "pip install",
    "./out/",
    "slide_layouts[",
    "layout-by-index",
)

_BINARY_SUFFIXES = {
    ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".woff", ".woff2", ".ttf", ".otf", ".zip",
}


def _skill_texts(rel: str) -> list[tuple[Path, str]]:
    root = SKILLS / rel
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        found.append((path, path.read_text(encoding="utf-8", errors="replace")))
    return found


def test_office_skill_directories_exist() -> None:
    missing = [rel for rel in OFFICE_SKILL_DIRS if not (SKILLS / rel).is_dir()]
    assert not missing, missing


def test_office_skills_omit_banking_example_and_index_layouts() -> None:
    leaks: list[str] = []
    for rel in OFFICE_SKILL_DIRS:
        for path, text in _skill_texts(rel):
            lowered = text.lower()
            for term in BANNED_TERMS:
                if term in lowered:
                    leaks.append(f"{path.relative_to(REPO)} contains {term!r}")
    assert not leaks, "\n".join(leaks)


def test_pptx_author_requires_visual_office_qa_render() -> None:
    text = (SKILLS / "finance/pptx-author/SKILL.md").read_text(encoding="utf-8")
    assert "office_visual_qa.py" in text
    assert "contact-sheet.png" in text
    assert "required final step" in text
    render_lines = [
        line for line in text.splitlines()
        if "office_visual_qa.py" in line and "python" in line
    ]
    assert render_lines, "pptx-author must show the office_visual_qa.py command"
    assert all("--skip-libreoffice" not in line for line in render_lines)
    assert "LibreOffice" in text


@pytest.mark.parametrize("rel", TYPE_SIZE_SKILLS)
def test_type_size_rule_present(rel: str) -> None:
    path = SKILLS / rel
    assert path.is_file(), rel
    assert TYPE_SIZE_RULE in path.read_text(encoding="utf-8")


def test_matplotlib_declared_in_nemo_extra_beside_python_pptx() -> None:
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    specs = pyproject["project"]["optional-dependencies"]["nemo"]
    names = [Requirement(spec).name for spec in specs]
    assert "python-pptx" in names
    assert "matplotlib" in names
    assert names.index("matplotlib") == names.index("python-pptx") + 1
    matplotlib = next(spec for spec in specs if Requirement(spec).name == "matplotlib")
    pptx = next(spec for spec in specs if Requirement(spec).name == "python-pptx")
    assert matplotlib.startswith("matplotlib==")
    assert pptx.startswith("python-pptx==")
    test_group = pyproject["dependency-groups"]["test"]
    test_matplotlib = [
        spec for spec in test_group if Requirement(spec).name == "matplotlib"
    ]
    assert test_matplotlib == [matplotlib]


def test_matplotlib_importable() -> None:
    import matplotlib

    assert matplotlib.__version__
