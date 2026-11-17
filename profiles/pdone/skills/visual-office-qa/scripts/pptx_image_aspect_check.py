#!/usr/bin/env python3
"""Fail closed if any PPTX picture is stretched vs its embedded source pixels."""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def check_pptx(path: Path, max_rel: float = 0.02) -> dict:
    prs = Presentation(str(path))
    issues = []
    pictures = 0
    for slide_idx, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
                continue
            pictures += 1
            try:
                blob = shape.image.blob
            except Exception as exc:
                issues.append(
                    {
                        "slide": slide_idx,
                        "name": getattr(shape, "name", ""),
                        "error": f"could not read embedded image: {exc}",
                    }
                )
                continue
            with Image.open(BytesIO(blob)) as im:
                native_w, native_h = im.size
            if native_w < 1 or native_h < 1:
                issues.append(
                    {
                        "slide": slide_idx,
                        "name": getattr(shape, "name", ""),
                        "error": "native image has zero dimension",
                    }
                )
                continue
            native_ar = native_w / native_h
            placed_ar = shape.width / shape.height
            rel = abs(placed_ar - native_ar) / native_ar
            if rel > max_rel:
                issues.append(
                    {
                        "slide": slide_idx,
                        "name": getattr(shape, "name", ""),
                        "native_px": [native_w, native_h],
                        "native_ar": round(native_ar, 4),
                        "placed_ar": round(placed_ar, 4),
                        "rel_error": round(rel, 4),
                    }
                )
    return {
        "path": str(path),
        "pictures": pictures,
        "max_rel": max_rel,
        "distorted": len(issues),
        "issues": issues,
        "ok": pictures > 0 and not issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--max-rel", type=float, default=0.02)
    args = parser.parse_args()
    if not args.pptx.is_file():
        print(json.dumps({"ok": False, "error": f"missing file: {args.pptx}"}, ensure_ascii=False))
        return 2
    result = check_pptx(args.pptx, args.max_rel)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["pictures"] == 0:
        return 0
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
