"""Authoring entry for the sealed Pro-Design firm template.

The golden keeps 56 gallery slides, a SAMPLE chip, and an empty comments
card so the template itself can be previewed. ``load_firm_presentation()``
leaves that chrome in place, and a cover subtitle with no ``buNone`` picks
up the master otherStyle bullet. This module is the documented authoring
path: drop the gallery, keep masters and layouts, then strip chrome the
new deck does not fill. It never writes ``firm-template.pptx``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

_HF_TYPES = frozenset({"dt", "ftr", "sldNum"})
_LIGHT_MASTER = "Pro-Design Light"
_COMMENTS_CARD = "Comments card"
_COMMENTS_IDX = "3"
_LEADING_BULLET = re.compile(r"^[\s•●∙·‧▪▫◦\-–—*]+")
_LIST_LEVELS = frozenset(
    {
        "defPPr",
        "lvl1pPr",
        "lvl2pPr",
        "lvl3pPr",
        "lvl4pPr",
        "lvl5pPr",
        "lvl6pPr",
        "lvl7pPr",
        "lvl8pPr",
        "lvl9pPr",
    }
)


def load_authoring_presentation(template: str | Path) -> Any:
    """Load ``template`` and drop every gallery slide.

    Masters and layouts stay. SAMPLE / 示意 shapes are removed from layouts,
    and every subtitle list style is set to ``buNone`` so the master bullet
    cannot render on a cover.
    """
    presentation = Presentation(str(template))
    _drop_all_slides(presentation)
    _strip_sample_shapes(presentation)
    _clear_all_subtitle_list_styles(presentation)
    return presentation


def layout_by_name(
    presentation: Any, name: str, master_name: str = _LIGHT_MASTER
) -> Any:
    """Return the named layout on ``master_name``. Never index the layout list."""
    for master in presentation.slide_masters:
        if master.name != master_name:
            continue
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    raise KeyError(f"{master_name} has no layout {name!r}")


def set_cover_subtitle(slide: Any, text: str) -> None:
    """Write the cover subtitle with no bullet character and no list bullet.

    Assigning ``placeholder.text`` builds a paragraph without ``buNone``.
    The master otherStyle then draws a bullet. This writes the subtitle
    placeholder directly and clears the layout list style too.
    """
    cleaned = _strip_leading_bullet(text)
    if not cleaned:
        raise ValueError("cover subtitle is empty")
    target = _subtitle_shape(slide)
    if target is None:
        raise KeyError("slide has no subtitle placeholder")
    _write_subtitle_text(target, cleaned, _subtitle_shape(slide.slide_layout))
    _clear_subtitle_list_style(slide.slide_layout)


def finish_authoring(presentation: Any) -> None:
    """Drop unused placeholders, SAMPLE chrome, and an unused comments card.

    Call this after titles, body, and charts are filled and before
    ``save_presentation()``. Header, footer, and slide-number placeholders
    stay so that save can clone them. A chart that already holds a chart
    stays. A comments card stays only on a layout whose slide filled comments.
    """
    for slide in presentation.slides:
        _clear_unused_placeholders(slide)
    _strip_sample_shapes(presentation)
    _drop_unused_comments_cards(presentation)


def _drop_all_slides(presentation: Any) -> None:
    slide_ids = presentation.slides._sldIdLst
    for slide_id in list(slide_ids):
        rel_id = slide_id.get(qn("r:id"))
        if rel_id:
            presentation.part.drop_rel(rel_id)
        slide_ids.remove(slide_id)


def _each_layout(presentation: Any):
    for master in presentation.slide_masters:
        yield from master.slide_layouts


def _sp_tree(container: Any):
    return container.shapes._spTree


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _shape_name(element: Any) -> str:
    marker = element.find(".//" + qn("p:cNvPr"))
    if marker is None:
        return ""
    return marker.get("name") or ""


def _element_text(element: Any) -> str:
    return "".join(node.text or "" for node in element.iter(qn("a:t")))


def _is_sample_shape(element: Any) -> bool:
    blob = f"{_shape_name(element)} {_element_text(element)}"
    return "SAMPLE" in blob or "示意" in blob


def _is_comments_card(element: Any) -> bool:
    return _shape_name(element).strip() == _COMMENTS_CARD


def _remove_matching(tree: Any, predicate) -> None:
    for child in list(tree):
        if _local(child.tag) in {"nvGrpSpPr", "grpSpPr"}:
            continue
        if predicate(child):
            tree.remove(child)


def _strip_sample_shapes(presentation: Any) -> None:
    for layout in _each_layout(presentation):
        _remove_matching(_sp_tree(layout), _is_sample_shape)


def _placeholder(element: Any):
    return element.find(".//" + qn("p:ph"))


def _clear_unused_placeholders(slide: Any) -> None:
    tree = _sp_tree(slide)
    for child in list(tree):
        if _local(child.tag) not in {"sp", "graphicFrame"}:
            continue
        if _is_sample_shape(child):
            tree.remove(child)
            continue
        placeholder = _placeholder(child)
        if placeholder is None:
            continue
        if (placeholder.get("type") or "") in _HF_TYPES:
            continue
        if child.find(".//" + qn("c:chart")) is not None:
            continue
        if _element_text(child).strip():
            continue
        tree.remove(child)


def _slide_has_comment_text(slide: Any) -> bool:
    for child in _sp_tree(slide):
        placeholder = _placeholder(child)
        if placeholder is None or placeholder.get("idx") != _COMMENTS_IDX:
            continue
        if _element_text(child).strip():
            return True
    return False


def _layout_comments_used(presentation: Any, layout: Any) -> bool:
    layout_part = layout.part
    for slide in presentation.slides:
        if slide.slide_layout.part is not layout_part:
            continue
        if _slide_has_comment_text(slide):
            return True
    return False


def _drop_unused_comments_cards(presentation: Any) -> None:
    for layout in _each_layout(presentation):
        if _layout_comments_used(presentation, layout):
            continue
        _remove_matching(_sp_tree(layout), _is_comments_card)


def _subtitle_shape(container: Any):
    if container is None:
        return None
    for child in _sp_tree(container).iter(qn("p:sp")):
        placeholder = _placeholder(child)
        if placeholder is not None and placeholder.get("type") == "subTitle":
            return child
    return None


def _ensure_bu_none(paragraph: Any) -> None:
    props = paragraph.find(qn("a:pPr"))
    if props is None:
        props = etree.Element(qn("a:pPr"))
        paragraph.insert(0, props)
    props.set("marL", "0")
    props.set("indent", "0")
    for child in list(props):
        if _local(child.tag).startswith("bu"):
            props.remove(child)
    etree.SubElement(props, qn("a:buNone"))


def _force_lst_style_bu_none(lst_style: Any) -> None:
    levels = [child for child in list(lst_style) if _local(child.tag) in _LIST_LEVELS]
    if not levels:
        level = etree.SubElement(lst_style, qn("a:lvl1pPr"))
        level.set("marL", "0")
        level.set("indent", "0")
        etree.SubElement(level, qn("a:buNone"))
        return
    for level in levels:
        for child in list(level):
            if _local(child.tag).startswith("bu"):
                level.remove(child)
        etree.SubElement(level, qn("a:buNone"))


def _clear_subtitle_list_style(layout: Any) -> None:
    for shape in _sp_tree(layout).iter(qn("p:sp")):
        placeholder = _placeholder(shape)
        if placeholder is None or placeholder.get("type") != "subTitle":
            continue
        text_body = shape.find(qn("p:txBody"))
        if text_body is None:
            continue
        lst_style = text_body.find(qn("a:lstStyle"))
        if lst_style is None:
            lst_style = etree.Element(qn("a:lstStyle"))
            body_props = text_body.find(qn("a:bodyPr"))
            if body_props is not None:
                body_props.addnext(lst_style)
            else:
                text_body.insert(0, lst_style)
        _force_lst_style_bu_none(lst_style)
        for paragraph in text_body.findall(qn("a:p")):
            _ensure_bu_none(paragraph)


def _clear_all_subtitle_list_styles(presentation: Any) -> None:
    for layout in _each_layout(presentation):
        _clear_subtitle_list_style(layout)


def _copied_run_props(font_source: Any):
    if font_source is None:
        return None
    source = font_source.find(".//" + qn("a:rPr"))
    if source is None:
        return None
    return etree.fromstring(etree.tostring(source))


def _write_subtitle_text(shape: Any, text: str, font_source: Any) -> None:
    text_body = shape.find(qn("p:txBody"))
    if text_body is None:
        raise KeyError("subtitle placeholder has no text body")
    for paragraph in list(text_body.findall(qn("a:p"))):
        text_body.remove(paragraph)
    paragraph = etree.SubElement(text_body, qn("a:p"))
    _ensure_bu_none(paragraph)
    run = etree.SubElement(paragraph, qn("a:r"))
    run_props = _copied_run_props(font_source)
    if run_props is not None:
        run.append(run_props)
    text_elm = etree.SubElement(run, qn("a:t"))
    text_elm.text = text


def _strip_leading_bullet(text: str) -> str:
    return _LEADING_BULLET.sub("", text or "").strip()
