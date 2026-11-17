"""Guards for PD One firm-template authoring after the #97 visual QA gaps.

A deck built through prepare_deck must contain only the slides the caller
added, with no SAMPLE / 示意 chrome, no empty placeholder, and no bullet
on the cover subtitle. The visual-office-qa image must alias JhengHei and Aptos.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import zipfile
from pathlib import Path

import pytest
from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "profiles/pdone/skills/pd-one/pd-one-firm-template/firm-template.pptx"
HELPER = (
    REPO / "profiles/pdone/skills/pd-one/pd-one-firm-template/scripts/prepare_deck.py"
)
QA_IMAGE = REPO / "profiles/pdone/skills/visual-office-qa"
_HF_TYPES = frozenset({"dt", "ftr", "sldNum"})
_SLIDE_XML = re.compile(r"ppt/slides/slide\d+\.xml")
_LAYOUT_XML = re.compile(r"ppt/slideLayouts/slideLayout\d+\.xml")
_MASTER_XML = re.compile(r"ppt/slideMasters/slideMaster\d+\.xml")
_SUBTITLE = "2026 年 11 月 · 產銷彙整 November 2026 operations review"


def _load_helper():
    spec = importlib.util.spec_from_file_location("pd_one_prepare_deck", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prepare_deck():
    return _load_helper()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _package(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xml")
        }


def _real_template() -> Path | None:
    if not TEMPLATE.is_file():
        return None
    try:
        Presentation(str(TEMPLATE))
    except Exception:
        return None
    return TEMPLATE


def _write_fixture(path: Path) -> Path:
    """Small golden: gallery slides, a SAMPLE chip, a comments card, a subtitle bullet."""
    presentation = Presentation()
    master = presentation.slide_masters[0]
    master._element.find(qn("p:cSld")).set("name", "Pro-Design Light")
    layouts = master.slide_layouts
    cover = layouts[0]
    content = layouts[1]
    cover._element.find(qn("p:cSld")).set("name", "封面 Title")
    content._element.find(qn("p:cSld")).set("name", "內文 Content")
    _inject_subtitle_bullet(cover)
    _inject_sample_chrome(content)
    for _ in range(4):
        presentation.slides.add_slide(content)
    presentation.slides[0].shapes.title.text = "SAMPLE 示意 gallery"
    presentation.save(str(path))
    return path


def _inject_subtitle_bullet(layout) -> None:
    for shape in layout.shapes._spTree.iter(qn("p:sp")):
        placeholder = shape.find(".//" + qn("p:ph"))
        if placeholder is None or placeholder.get("type") != "subTitle":
            continue
        text_body = shape.find(qn("p:txBody"))
        lst_style = text_body.find(qn("a:lstStyle"))
        for child in list(lst_style):
            lst_style.remove(child)
        level = etree.SubElement(lst_style, qn("a:lvl1pPr"))
        etree.SubElement(level, qn("a:buFont")).set("typeface", "Aptos")
        bullet = etree.SubElement(level, qn("a:buChar"))
        bullet.set("char", "•")


def _inject_sample_chrome(layout) -> None:
    tree = layout.shapes._spTree
    tree.append(_labeled_shape("SAMPLE chip", "SAMPLE  ·  示意", shape_id="90"))
    tree.append(_labeled_shape("Comments card", "", shape_id="91"))


def _labeled_shape(name: str, text: str, *, shape_id: str):
    shape = etree.Element(qn("p:sp"))
    nv_sp = etree.SubElement(shape, qn("p:nvSpPr"))
    marker = etree.SubElement(nv_sp, qn("p:cNvPr"))
    marker.set("id", shape_id)
    marker.set("name", name)
    etree.SubElement(nv_sp, qn("p:cNvSpPr"))
    etree.SubElement(nv_sp, qn("p:nvPr"))
    text_body = etree.SubElement(shape, qn("p:txBody"))
    etree.SubElement(text_body, qn("a:bodyPr"))
    etree.SubElement(text_body, qn("a:lstStyle"))
    paragraph = etree.SubElement(text_body, qn("a:p"))
    if text:
        run = etree.SubElement(paragraph, qn("a:r"))
        text_elm = etree.SubElement(run, qn("a:t"))
        text_elm.text = text
    return shape


def _fill_body(slide) -> None:
    skip = {
        PP_PLACEHOLDER.TITLE,
        PP_PLACEHOLDER.CENTER_TITLE,
        PP_PLACEHOLDER.SUBTITLE,
        PP_PLACEHOLDER.DATE,
        PP_PLACEHOLDER.FOOTER,
        PP_PLACEHOLDER.SLIDE_NUMBER,
        PP_PLACEHOLDER.CHART,
    }
    for shape in slide.placeholders:
        if shape.placeholder_format.type in skip:
            continue
        if shape.has_text_frame:
            shape.text = "全廠良率 97.4%，較上月提升 1.2 個百分點"
            return


def _insert_chart(slide) -> None:
    data = CategoryChartData()
    data.categories = ["甲線 Line A", "乙線 Line B", "丙線 Line C"]
    data.add_series("本期 Current", (12, 15, 11))
    chart = next(
        shape
        for shape in slide.placeholders
        if shape.placeholder_format.type == PP_PLACEHOLDER.CHART
    )
    chart.insert_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, data)


def _author(helper, template: Path, dest: Path, *, chart: bool) -> int:
    raw = Presentation(str(template))
    gallery = len(raw.slides)
    master_count = len(raw.slide_masters)
    layout_count = sum(len(master.slide_layouts) for master in raw.slide_masters)
    assert gallery >= 2

    presentation = helper.load_authoring_presentation(template)
    assert len(presentation.slides) == 0
    assert len(presentation.slide_masters) == master_count
    assert (
        sum(len(master.slide_layouts) for master in presentation.slide_masters)
        == layout_count
    )

    cover = presentation.slides.add_slide(
        helper.layout_by_name(presentation, "封面 Title")
    )
    cover.shapes.title.text = "週會 Weekly review"
    helper.set_cover_subtitle(cover, "• " + _SUBTITLE)
    body = presentation.slides.add_slide(
        helper.layout_by_name(presentation, "內文 Content")
    )
    body.shapes.title.text = "良率較上月上升 Yield rose versus last month"
    _fill_body(body)
    authored = 2
    if chart:
        chart_slide = presentation.slides.add_slide(
            helper.layout_by_name(presentation, "長條圖 Bar")
        )
        chart_slide.shapes.title.text = "各線產出 Output by line"
        _insert_chart(chart_slide)
        authored = 3
    helper.finish_authoring(presentation)
    assert len(presentation.slides) == authored
    presentation.save(str(dest))

    parts = _package(dest)
    _assert_package(
        parts, authored=authored, masters=master_count, layouts=layout_count
    )
    return authored


def _assert_package(
    parts: dict[str, str], *, authored: int, masters: int, layouts: int
) -> None:
    slides = [name for name in parts if _SLIDE_XML.fullmatch(name)]
    assert len(slides) == authored
    assert len([name for name in parts if _MASTER_XML.fullmatch(name)]) == masters
    assert len([name for name in parts if _LAYOUT_XML.fullmatch(name)]) == layouts
    blob = "\n".join(parts.values())
    assert "SAMPLE" not in blob
    assert "示意" not in blob
    assert "Comments card" not in blob
    for name in slides:
        _assert_no_empty_placeholder(parts[name], name)
    _assert_cover_subtitle(parts)


def _assert_no_empty_placeholder(xml: str, name: str) -> None:
    root = etree.fromstring(xml.encode("utf-8"))
    for element in root.iter():
        if _local(element.tag) not in {"sp", "graphicFrame"}:
            continue
        placeholder = None
        for child in element.iter():
            if _local(child.tag) == "ph":
                placeholder = child
                break
        if placeholder is None:
            continue
        if (placeholder.get("type") or "") in _HF_TYPES:
            continue
        if any(_local(child.tag) == "chart" for child in element.iter()):
            continue
        text = "".join(
            node.text or "" for node in element.iter() if _local(node.tag) == "t"
        ).strip()
        assert text, (
            f"{name} still has an empty placeholder idx={placeholder.get('idx')}"
        )


def _assert_cover_subtitle(parts: dict[str, str]) -> None:
    found = False
    for name, xml in parts.items():
        if not _SLIDE_XML.fullmatch(name):
            continue
        root = etree.fromstring(xml.encode("utf-8"))
        for shape in root.iter():
            if _local(shape.tag) != "sp":
                continue
            texts = [
                node.text or ""
                for node in shape.iter()
                if _local(node.tag) == "t" and node.text
            ]
            if not any(_SUBTITLE in text for text in texts):
                continue
            found = True
            assert all("•" not in text for text in texts)
            for paragraph in shape.iter():
                if _local(paragraph.tag) != "p":
                    continue
                paragraph_text = "".join(
                    node.text or ""
                    for node in paragraph.iter()
                    if _local(node.tag) == "t"
                )
                if _SUBTITLE not in paragraph_text:
                    continue
                props = next(
                    (node for node in paragraph if _local(node.tag) == "pPr"),
                    None,
                )
                assert props is not None
                locals_ = {_local(node.tag) for node in props}
                assert "buNone" in locals_
                assert "buChar" not in locals_
                assert "buAutoNum" not in locals_
    assert found, "cover subtitle text missing from the deck"

    layout_hits = 0
    for name, xml in parts.items():
        if not _LAYOUT_XML.fullmatch(name):
            continue
        root = etree.fromstring(xml.encode("utf-8"))
        canvas = next(node for node in root if _local(node.tag) == "cSld")
        if canvas.get("name") != "封面 Title":
            continue
        for shape in root.iter():
            if _local(shape.tag) != "sp":
                continue
            placeholder = next(
                (node for node in shape.iter() if _local(node.tag) == "ph"),
                None,
            )
            if placeholder is None or placeholder.get("type") != "subTitle":
                continue
            lst_style = next(
                (node for node in shape.iter() if _local(node.tag) == "lstStyle"),
                None,
            )
            assert lst_style is not None
            locals_ = {_local(node.tag) for node in lst_style.iter()}
            assert "buNone" in locals_
            assert "buChar" not in locals_
            assert "buAutoNum" not in locals_
            layout_hits += 1
    assert layout_hits >= 1


def test_fixture_deck_drops_gallery_and_sample_chrome(tmp_path, prepare_deck) -> None:
    template = _write_fixture(tmp_path / "fixture.pptx")
    _author(prepare_deck, template, tmp_path / "fixture-out.pptx", chart=False)


def test_firm_template_deck_matches_authored_slides(tmp_path, prepare_deck) -> None:
    template = _real_template()
    if template is None:
        pytest.skip(
            "firm-template.pptx could not be loaded; the fixture guard still runs"
        )
    digest = hashlib.sha256(template.read_bytes()).hexdigest()
    _author(prepare_deck, template, tmp_path / "firm-out.pptx", chart=True)
    assert hashlib.sha256(template.read_bytes()).hexdigest() == digest


def test_filled_comments_keep_the_card_and_drop_sample(tmp_path, prepare_deck) -> None:
    template = _real_template()
    if template is None:
        pytest.skip(
            "firm-template.pptx could not be loaded; the fixture guard still runs"
        )
    presentation = prepare_deck.load_authoring_presentation(template)
    slide = presentation.slides.add_slide(
        prepare_deck.layout_by_name(presentation, "長條圖 Bar")
    )
    slide.shapes.title.text = "各線產出 Output by line"
    _insert_chart(slide)
    comments = next(
        shape for shape in slide.placeholders if shape.placeholder_format.idx == 3
    )
    comments.text = "重點：換模逾時 18 分"
    prepare_deck.finish_authoring(presentation)
    assert len(presentation.slides) == 1
    dest = tmp_path / "comments.pptx"
    presentation.save(str(dest))
    blob = "\n".join(_package(dest).values())
    assert "SAMPLE" not in blob
    assert "示意" not in blob
    assert "Comments card" in blob
    assert "換模逾時" in blob


def test_visual_office_qa_fontconfig_aliases() -> None:
    conf = (QA_IMAGE / "fonts/99-pd-one-aliases.conf").read_text(encoding="utf-8")
    dockerfile = (QA_IMAGE / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts/99-pd-one-aliases.conf" in dockerfile
    assert "/etc/fonts/conf.d/99-pd-one-aliases.conf" in dockerfile
    assert "JhengHei" in conf
    assert "Noto Sans CJK TC" in conf
    assert "Aptos" in conf
    assert "Liberation Sans" in conf
    assert conf.index("JhengHei") < conf.index("Noto Sans CJK TC")
    assert conf.index("Aptos") < conf.index("Liberation Sans")
