"""Regression for execute_document_ops _PdUnset shadowing on work-manual writes."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.pd_one_ops import google_docs_document_ops as docs

_AUTHORIZED_REQUESTER = "abcdefghijklmnopqrstuvwxyz"
_BAD_REQUESTER = "zyxwvutsrqponmlkjihgfedcba"


def _blocked_translator(_text: str, _lang: str) -> str:
    return ""


def _heading(
    text: str,
    *,
    level: str = "HEADING_1",
    start_index: int = 50,
    tab_id: str = "tab0",
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        level=level,
        start_index=start_index,
        tab_id=tab_id,
        heading_id=f"id-{start_index}",
        end_index=start_index + len(text),
    )


def _fake_doc() -> dict:
    return {
        "documentId": "doc-test-001",
        "title": "ERP Work Manual",
        "revisionId": "rev-1",
        "tabs": [
            {
                "tabProperties": {"tabId": "tab0"},
                "documentTab": {
                    "namedStyles": {
                        "styles": [
                            {
                                "namedStyleType": "NORMAL_TEXT",
                                "textStyle": {"bold": False},
                            }
                        ]
                    }
                },
            }
        ],
    }


class _FakeDocsModule:
    HEADER_TYPE_CHOICES: tuple[str, ...] = ()
    HEADER_TYPE_TO_STYLE_KEY: dict[str, str] = {}

    def __init__(self, headings: list[SimpleNamespace]):
        self._headings = headings

    def body_content(self, _doc: dict, tab_id: str | None) -> tuple[list, str]:
        return [], str(tab_id or "tab0")

    def collect_headings(self, _doc: dict, _tab_id: str | None) -> list[SimpleNamespace]:
        return list(self._headings)

    def build_doc_url(self, document_id: str, tab_id: str) -> str:
        return f"https://docs.google.com/document/d/{document_id}/edit#tab={tab_id}"

    def document_style(self, _doc: dict, tab_id: str | None) -> tuple[dict, str]:
        return {}, str(tab_id or "tab0")

    def document_tab(self, doc: dict, tab_id: str | None) -> tuple[dict, str]:
        resolved = str(tab_id or "tab0")
        for tab in doc.get("tabs") or []:
            if tab.get("tabProperties", {}).get("tabId") == resolved:
                return tab.get("documentTab") or {}, resolved
        return doc["tabs"][0]["documentTab"], resolved


class _FakeDocsClient:
    def __init__(self, document: dict):
        self._document = document
        self.batch_update_calls = 0

    def get_document(self, _document_id: str, _mode: str) -> dict:
        return self._document

    def _request(self, *_args, **_kwargs) -> dict:
        self.batch_update_calls += 1
        raise AssertionError("batchUpdate must not run in dry-run regression tests")


@pytest.fixture
def docs_fixture(tmp_path, monkeypatch) -> tuple[Path, _FakeDocsClient]:
    receipt_root = tmp_path / "receipts"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema": "pd-one.google-docs-document-ops.v1",
                "allowed_requester_ids": [_AUTHORIZED_REQUESTER],
                "documents": {
                    "erp-work-manual": {
                        "document_id": "doc-test-001",
                        "title": "ERP Work Manual",
                        "scope": "work-manual",
                        "live_enabled": True,
                        "allowed_actions": [
                            "insert_section_before_heading",
                            "unique_text_patch",
                            "append_changelog",
                            "inspect",
                        ],
                        "account": "admin@example.com",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(docs, "RECEIPT_ROOT", lambda: receipt_root)
    client = _FakeDocsClient(_fake_doc())
    return registry_path, client


def _insert_section_kwargs(registry_path: Path, client: _FakeDocsClient, **overrides):
    parent = _heading("父章 Parent Chapter", level="HEADING_1", start_index=50)
    anchor = _heading("錨標 Anchor Heading", level="HEADING_2", start_index=200)
    module = _FakeDocsModule([parent, anchor])
    base = {
        "action": "insert_section_before_heading",
        "document_key": "erp-work-manual",
        "requester_user_id": _AUTHORIZED_REQUESTER,
        "dry_run": True,
        "registry_path": registry_path,
        "docs_module": module,
        "client": client,
        "anchor_heading": "錨標 Anchor Heading",
        "parent_heading": "父章 Parent Chapter",
        "section_heading": "新節 New Section",
        "body_paragraphs": ["步驟一\u000bStep one"],
        "heading_style": "HEADING_2",
    }
    base.update(overrides)
    return base


def test_dry_run_insert_section_before_heading_work_manual_no_unset_error(
    docs_fixture,
):
    """Work-manual dry runs must read caller args, not _PdUnset sentinels."""
    registry_path, client = docs_fixture
    result = docs.execute_document_ops(**_insert_section_kwargs(registry_path, client))

    assert "pd one local used before assignment" not in str(result)
    assert client.batch_update_calls == 0
    assert result.get("status") in {"ok", "error"}
    if result.get("status") == "ok":
        assert result.get("plan", {}).get("operation") == "insert_section_before_heading"


def test_insert_section_rejects_unauthorized_requester(docs_fixture):
    registry_path, client = docs_fixture
    result = docs.execute_document_ops(
        **_insert_section_kwargs(
            registry_path,
            client,
            requester_user_id=_BAD_REQUESTER,
        )
    )
    assert result.get("status") == "error"
    assert result.get("error") == "not_authorized"
    assert client.batch_update_calls == 0


def test_insert_section_rejects_chinese_only_body_paragraph(docs_fixture):
    registry_path, client = docs_fixture
    result = docs.execute_document_ops(
        **_insert_section_kwargs(
            registry_path,
            client,
            body_paragraphs=["只有中文沒有英文"],
            translator=_blocked_translator,
        )
    )
    assert result.get("status") == "error"
    assert result.get("error") == "invalid_request"
    detail = str(result.get("detail", "")).casefold()
    assert "body_paragraphs" in detail or "automatic english translation failed" in detail
    assert "pd one local used before assignment" not in str(result)
    assert client.batch_update_calls == 0