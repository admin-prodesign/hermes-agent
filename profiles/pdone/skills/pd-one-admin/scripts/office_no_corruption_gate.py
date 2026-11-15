#!/usr/bin/env python3
"""Office no-corruption gate for XLSX/XLSM/DOCX/PPTX.

Performs structural ZIP/OpenXML checks, optional library reopen checks, and optional
LibreOffice headless conversion. Exits 0 only when required structural checks pass;
prints WARN lines for unavailable optional validators unless --strict-optional is set.

For PPTX/POTX, also fails on PowerPoint Repair triggers:
  presentation→theme rel missing, sparse presentation rIds, type=cust,
  p:ph on non-rect geom, duplicate/reserved footer ph idx collisions.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EXPECTED = {
    ".xlsx": ["[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"],
    ".xlsm": ["[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"],
    ".docx": ["[Content_Types].xml", "word/document.xml", "_rels/.rels"],
    ".pptx": ["[Content_Types].xml", "ppt/presentation.xml", "_rels/.rels"],
    ".potx": ["[Content_Types].xml", "ppt/presentation.xml", "_rels/.rels"],
}

# Prefer profile scripts validate_pptx (theme/dense/cust/nonrect/dupidx).
_VALIDATE_CANDIDATES = (
    Path("/home/prodesign/.hermes/profiles/pdone/scripts/validate_pptx.py"),
    Path(__file__).resolve().parents[3] / "scripts" / "validate_pptx.py",
)


def result(level: str, message: str, **extra):
    print(json.dumps({"level": level, "message": message, **extra}, ensure_ascii=False))


def fail(message: str, **extra):
    result("FAIL", message, **extra)
    raise SystemExit(1)


def warn_or_fail(strict: bool, message: str, **extra):
    if strict:
        fail(message, **extra)
    result("WARN", message, **extra)


def check_zip(path: Path, ext: str):
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                fail("ZIP CRC/integrity check failed", member=bad)
            names = set(zf.namelist())
            missing = [m for m in EXPECTED[ext] if m not in names]
            if missing:
                fail("Missing expected OpenXML members", missing=missing)
            result("OK", "ZIP/OpenXML structural check passed", members=len(names))
    except zipfile.BadZipFile as e:
        fail("Not a valid ZIP/OpenXML Office file", error=str(e))


def check_library(path: Path, ext: str, strict_optional: bool):
    if ext in {".xlsx", ".xlsm"}:
        try:
            from openpyxl import load_workbook
        except Exception as e:
            warn_or_fail(strict_optional, "openpyxl unavailable; workbook reopen check skipped", error=str(e))
            return
        try:
            wb = load_workbook(path, keep_vba=(ext == ".xlsm"), data_only=False, read_only=False)
            result("OK", "openpyxl reopen check passed", sheets=wb.sheetnames, sheet_count=len(wb.sheetnames))
        except Exception as e:
            fail("openpyxl failed to reopen workbook", error=repr(e))
    elif ext == ".docx":
        try:
            import docx  # python-docx
        except Exception as e:
            warn_or_fail(strict_optional, "python-docx unavailable; DOCX reopen check skipped", error=str(e))
            return
        try:
            d = docx.Document(str(path))
            result("OK", "python-docx reopen check passed", paragraphs=len(d.paragraphs), tables=len(d.tables))
        except Exception as e:
            fail("python-docx failed to reopen document", error=repr(e))
    elif ext == ".pptx":
        try:
            from pptx import Presentation
        except Exception as e:
            warn_or_fail(strict_optional, "python-pptx unavailable; PPTX reopen check skipped", error=str(e))
            return
        try:
            p = Presentation(str(path))
            result("OK", "python-pptx reopen check passed", slides=len(p.slides))
        except Exception as e:
            fail("python-pptx failed to reopen presentation", error=repr(e))


def check_sldsz_type(path: Path) -> None:
    """Fail if p:sldSz type does not match ECMA enumerated cx/cy (PowerPoint Repair)."""
    import re

    enum = {"screen16x9": (9144000, 5143500), "screen16x10": (9144000, 5715000), "screen4x3": (9144000, 6858000)}
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("ppt/presentation.xml").decode("utf-8")
    m = re.search(r"<p:sldSz\b([^>]*)/?>", xml)
    if not m:
        fail("ppt/presentation.xml missing p:sldSz")
    attrs = m.group(1)
    typ = re.search(r'\btype="([^"]+)"', attrs)
    cx = re.search(r'\bcx="(\d+)"', attrs)
    cy = re.search(r'\bcy="(\d+)"', attrs)
    if not typ:
        result("OK", "p:sldSz has no type (custom size is allowed)", cx=cx.group(1) if cx else None, cy=cy.group(1) if cy else None)
        return
    if not cx or not cy:
        fail("p:sldSz type is set but cx/cy missing", type=typ.group(1))
    expected = enum.get(typ.group(1).lower())
    got = (int(cx.group(1)), int(cy.group(1)))
    if expected and got != expected:
        fail(
            "p:sldSz type does not match enumerated size; PowerPoint will Repair",
            type=typ.group(1),
            expected=list(expected),
            got=list(got),
        )
    result("OK", "p:sldSz type matches enumerated size", type=typ.group(1), cx=got[0], cy=got[1])


def check_pptx_repair_triggers(path: Path) -> None:
    """Fail on theme_rel / dense rIds / cust / nonrect ph / dupidx (ZIP+sldSz alone is too weak)."""
    validate_path = next((p for p in _VALIDATE_CANDIDATES if p.is_file()), None)
    if validate_path is None:
        fail(
            "validate_pptx.py missing; cannot enforce PPTX Repair-trigger checks",
            tried=[str(p) for p in _VALIDATE_CANDIDATES],
        )
    scripts_dir = str(validate_path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from validate_pptx import repair_trigger_errors  # type: ignore
    except Exception as e:
        fail("failed to import validate_pptx", error=repr(e), path=str(validate_path))
    # Mandatory Repair triggers; include sealed-template layout floors.
    errs = repair_trigger_errors(path, include_layout_floors=True)
    if errs:
        fail(
            "PPTX Repair-trigger checks failed",
            count=len(errs),
            errors=errs[:40],
        )
    result("OK", "PPTX Repair-trigger checks passed (theme_rel/dense_rids/cust/nonrect/dupidx)")
    check_pptx_slide_header_footer(path)


def check_pptx_slide_header_footer(path: Path):
    """Fail when a layout has dt/ftr/sldNum but the using slide does not.

    python-pptx does not clone those latent placeholders. Skip the sealed
    firm template (its sample slides are layout demos, not deliveries).
    """
    import xml.etree.ElementTree as ET

    sealed = Path("/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx")
    try:
        if path.resolve() == sealed.resolve():
            result("INFO", "Skipping slide header/footer check on sealed firm template")
            return
    except OSError:
        pass
    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    HF = {"dt", "ftr", "sldNum"}

    def hf_types(xml_bytes: bytes) -> set[str]:
        root = ET.fromstring(xml_bytes)
        return {ph.get("type") for ph in root.iter(P + "ph") if ph.get("type") in HF}

    missing: list[dict] = []
    with zipfile.ZipFile(path) as zf:
        layouts = {
            name: hf_types(zf.read(name))
            for name in zf.namelist()
            if name.startswith("ppt/slideLayouts/") and name.endswith(".xml") and "/_rels/" not in name
        }
        slides = [
            name
            for name in zf.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml") and "/_rels/" not in name
        ]
        if not slides:
            return
        for slide_name in slides:
            rels_name = "ppt/slides/_rels/" + Path(slide_name).name + ".rels"
            layout_path = ""
            rels = ET.fromstring(zf.read(rels_name))
            for rel in list(rels):
                tgt = rel.get("Target") or ""
                if "slideLayout" in tgt:
                    layout_path = "ppt/slideLayouts/" + tgt.rsplit("/", 1)[-1]
                    break
            need = layouts.get(layout_path) or set()
            if not need:
                continue
            have = hf_types(zf.read(slide_name))
            lack = sorted(need - have)
            if lack:
                missing.append({"slide": slide_name, "layout": layout_path, "missing": lack})
    if missing:
        fail(
            "PPTX slides missing layout header/footer placeholders (dt/ftr/sldNum)",
            count=len(missing),
            slides=missing[:20],
        )
    result("OK", "PPTX slide header/footer placeholders present", slides=len(slides))


def check_libreoffice(path: Path, ext: str, strict_optional: bool):
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        warn_or_fail(strict_optional, "LibreOffice/soffice unavailable; headless open/convert validation skipped")
        return
    with tempfile.TemporaryDirectory(prefix="office-gate-") as td:
        outdir = Path(td)
        target = "pdf" if ext in {".docx", ".pptx"} else ("xlsx" if ext == ".xlsx" else "xlsm")
        cmd = [soffice, "--headless", "--nologo", "--nofirststartwizard", "--convert-to", target, "--outdir", str(outdir), str(path)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if proc.returncode != 0:
            fail("LibreOffice conversion failed", returncode=proc.returncode, stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:])
        outputs = [p for p in outdir.iterdir() if p.is_file()]
        nonzero = [p for p in outputs if p.stat().st_size > 0]
        if not nonzero:
            fail("LibreOffice conversion produced no non-empty output", stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:])
        result("OK", "LibreOffice headless conversion passed", outputs=[{"name": p.name, "size": p.stat().st_size} for p in nonzero])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--strict-optional", action="store_true", help="Fail when optional validators are unavailable")
    ap.add_argument("--skip-libreoffice", action="store_true")
    args = ap.parse_args()
    path = Path(args.path)
    if not path.exists() or not path.is_file():
        fail("File does not exist", path=str(path))
    ext = path.suffix.lower()
    if ext not in EXPECTED:
        fail("Unsupported Office extension", ext=ext)
    if path.stat().st_size <= 0:
        fail("File is empty")
    result("INFO", "Starting Office no-corruption gate", path=str(path), size=path.stat().st_size, ext=ext)
    check_zip(path, ext)
    check_library(path, ext, args.strict_optional)
    if ext in {".pptx", ".potx"}:
        check_sldsz_type(path)
        check_pptx_repair_triggers(path)
    if not args.skip_libreoffice:
        check_libreoffice(path, ext, args.strict_optional)
    result("OK", "Office no-corruption gate completed")


if __name__ == "__main__":
    main()
