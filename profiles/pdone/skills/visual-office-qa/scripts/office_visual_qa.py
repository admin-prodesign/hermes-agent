#!/usr/bin/env python3
"""Render DOCX/PPTX to PNGs for visual QA.

Requires LibreOffice/soffice for Office -> PDF, and either pdftoppm or
ImageMagick for PDF -> PNG. Optionally uses Pillow for a contact sheet.
Canonical documentation: [[syntheses/visual-office-qa-renderer|Visual Office QA Renderer]]

"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def which_any(names: list[str]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)  # health: allow HX006 -- vendored 2026-11-17 nemo office-skill snapshot; keep the live script


def make_contact_sheet(images: list[Path], out: Path, thumb_width: int = 900) -> str:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:  # health: allow BLE001 -- vendored 2026-11-17 nemo office-skill snapshot; keep the live script
        montage = which_any(["montage"])
        if montage:
            cmd = [montage, *map(str, images), "-thumbnail", f"{thumb_width}x", "-tile", "2x", "-geometry", "+24+36", str(out)]
            proc = run(cmd)
            if proc.returncode == 0 and out.exists():
                return "imagemagick"
            return f"imagemagick-failed: {proc.stdout.strip()}"
        return "unavailable: install Pillow or ImageMagick montage"

    thumbs = []
    for img_path in images:
        img = Image.open(img_path).convert("RGB")
        ratio = thumb_width / img.width
        thumb = img.resize((thumb_width, max(1, int(img.height * ratio))))
        thumbs.append((img_path.name, thumb))

    cols = 2 if len(thumbs) > 1 else 1
    label_h = 36
    pad = 24
    rows = math.ceil(len(thumbs) / cols)
    cell_w = thumb_width + pad * 2
    cell_h = max(t.height for _, t in thumbs) + label_h + pad * 2
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (name, thumb) in enumerate(thumbs):
        row, col = divmod(idx, cols)
        x = col * cell_w + pad
        y = row * cell_h + pad + label_h
        draw.text((x, row * cell_h + pad), name, fill=(0, 0, 0))
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + thumb.width - 1, y + thumb.height - 1), outline=(180, 180, 180), width=2)
    sheet.save(out)
    return "pillow"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX/PPTX to visual QA PNGs")
    parser.add_argument("office_file", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--no-docker", action="store_true", help="do not use the Docker fallback when host renderers are missing")
    args = parser.parse_args()

    src = args.office_file.expanduser().resolve()
    if not src.exists():
        print(f"ERROR: file not found: {src}", file=sys.stderr)
        return 2
    if src.suffix.lower() not in {".docx", ".pptx"}:
        print(f"ERROR: expected .docx or .pptx, got {src.suffix}", file=sys.stderr)
        return 2

    out_dir = (args.out_dir or (src.parent / f"{src.stem}-visual-qa")).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    soffice = which_any(["soffice", "libreoffice", "lowriter"])
    pdftoppm = which_any(["pdftoppm"])
    magick = which_any(["magick", "convert"])
    summary: list[str] = [f"# Visual QA summary for `{src.name}`", ""]

    if not soffice:
        docker = which_any(["docker"])
        image = os.environ.get("OFFICE_VISUAL_QA_DOCKER_IMAGE", "visual-office-qa:latest")
        if docker and not args.no_docker:
            inspect = run([docker, "image", "inspect", image])
            if inspect.returncode == 0:
                skill_dir = Path(__file__).resolve().parents[1]
                src_parent = src.parent
                cmd = [
                    docker, "run", "--rm",
                    "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp",  # no-tmp: ok — container HOME for the visual-office-qa Docker fallback
                    "-v", f"{skill_dir}:/skill:ro",
                    "-v", f"{src_parent}:/input:ro",
                    "-v", f"{out_dir}:/out",
                    "-w", "/skill",
                    image,
                    "python3", "/skill/scripts/office_visual_qa.py",
                    f"/input/{src.name}", "--out-dir", "/out",
                    "--dpi", str(args.dpi), "--no-docker",
                ]
                proc = run(cmd)
                stdout = proc.stdout.replace("/out\n", f"{out_dir}\n")
                print(stdout, end="")
                return proc.returncode
        summary += [
            "## Status",
            "FAILED: no LibreOffice/soffice renderer found in PATH and no usable Docker fallback image was found.",
            "",
            "Install host dependencies (`libreoffice poppler-utils python3-pil`) or build the fallback image:",
            "",
            "```bash",
            "docker build -t visual-office-qa:latest /home/prodesign/.hermes/profiles/pdone/skills/visual-office-qa",
            "```",
        ]
        (out_dir / "qa-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        print(out_dir / "qa-summary.md")
        return 1

    with tempfile.TemporaryDirectory(prefix="office-visual-qa-") as tmp_name:
        tmp = Path(tmp_name)
        profile = tmp / "lo-profile"
        conv_cmd = [soffice, "--headless", f"-env:UserInstallation=file://{profile}", "--convert-to", "pdf", "--outdir", str(tmp), str(src)]
        conv = run(conv_cmd)
        summary += ["## Office -> PDF", "```", " ".join(conv_cmd), conv.stdout.strip(), "```", ""]
        pdfs = sorted(tmp.glob("*.pdf"))
        if conv.returncode != 0 or not pdfs:
            summary += ["## Status", "FAILED: Office file did not render to PDF."]
            (out_dir / "qa-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
            return 1
        pdf = out_dir / "rendered.pdf"
        shutil.copy2(pdfs[0], pdf)

    pngs: list[Path] = []
    if pdftoppm:
        prefix = out_dir / "page"
        proc = run([pdftoppm, "-png", "-r", str(args.dpi), str(pdf), str(prefix)])
        summary += ["## PDF -> PNG", "```", " ".join([pdftoppm, "-png", "-r", str(args.dpi), str(pdf), str(prefix)]), proc.stdout.strip(), "```", ""]
        pngs = sorted(out_dir.glob("page-*.png"))
    elif magick:
        proc = run([magick, "-density", str(args.dpi), str(pdf), str(out_dir / "page-%03d.png")])
        summary += ["## PDF -> PNG", "```", " ".join([magick, "-density", str(args.dpi), str(pdf), str(out_dir / "page-%03d.png")]), proc.stdout.strip(), "```", ""]
        pngs = sorted(out_dir.glob("page-*.png"))
    else:
        summary += ["## Status", "PARTIAL: PDF rendered, but no `pdftoppm` or ImageMagick found to create PNG screenshots."]

    if pngs:
        contact = out_dir / "contact-sheet.png"
        sheet_status = make_contact_sheet(pngs, contact)
        summary += ["## Renders", f"Pages/slides rendered: {len(pngs)}", "", *[f"- `{p.name}`" for p in pngs], "", f"Contact sheet: `{contact.name}` ({sheet_status})", ""]
        summary += ["## Manual visual checklist", "- Check text clipping/overflow and unexpected wrapping.", "- Check missing images/logos, broken fonts, CJK glyph fallback, and alignment.", "- Check margins, page/slide count, blank pages/slides, headers/footers, and tables/signature areas.", "- If any issue is visible, fix the source Office file and re-run this script."]
    summary += ["", "## Status", "PASS: render artifacts created for visual inspection." if pngs else "PARTIAL: inspect rendered.pdf manually or install a PNG rasterizer."]
    (out_dir / "qa-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(out_dir)
    return 0 if pngs else 1


if __name__ == "__main__":
    raise SystemExit(main())
