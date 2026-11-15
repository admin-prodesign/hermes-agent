"""Allowlisted UNC Word list/extract follows the requester's NTFS rights.

PDAPP-20261104-61CDF611. The helper identity must not leak names or table cells
the requester cannot Read. Finance and other non-allowlisted UNC paths are
refused before any ACL or SMB call.
"""
from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import pytest

from tools.pd_one_ops import pd_one_unc_docx_table as unc

REQUESTER = "requester-id-placeholder"
ADMIN = "admin-id-placeholder"
SIP_ROOT = r"\\sql-srv\SIP&SOP\SIP\_原檔_新版本"
SIP_FILE = SIP_ROOT + r"\SIP-001.docx"
FINANCE = r"\\sql-srv\Finance\budget.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class FakeHelper:
    def __init__(self, listing: dict[str, Any] | None = None, extract: dict[str, Any] | None = None) -> None:
        self.listing = listing or {"ok": True, "items": [], "denied_count": 0, "scanned": 0, "errors": []}
        self.extract = extract or {"ok": True, "document_xml": "", "errors": []}
        self.payloads: list[str] = []

    def load_env(self) -> dict[str, str]:
        return {}

    def make_session(self, values: dict[str, str]) -> tuple[str, str, str, str]:
        return ("session", "helper-host", "helper-user", "helper-secret")

    def run_via_task(self, session: Any, user: str, password: str, payload: str, timeout: int) -> dict[str, Any]:
        self.payloads.append(payload)
        if "document_xml" in payload or "ZipFile" in payload:
            return dict(self.extract)
        return dict(self.listing)


def _docx_xml(*tables: list[list[str]], titles: list[str] | None = None) -> str:
    chunks = [f'<w:document xmlns:w="{W_NS}"><w:body>']
    for index, rows in enumerate(tables):
        title = (titles or [""] * len(tables))[index]
        if title:
            chunks.append(f"<w:p><w:r><w:t>{title}</w:t></w:r></w:p>")
        chunks.append("<w:tbl>")
        for row in rows:
            chunks.append("<w:tr>")
            for cell in row:
                chunks.append(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>")
            chunks.append("</w:tr>")
        chunks.append("</w:tbl>")
    chunks.append("</w:body></w:document>")
    return "".join(chunks)


def _docx_bytes(*tables: list[list[str]], titles: list[str] | None = None) -> bytes:
    xml = _docx_xml(*tables, titles=titles)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ))
        archive.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ))
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    monkeypatch.delenv("PD_ONE_EXTERNAL_INTERPRETER", raising=False)
    monkeypatch.delenv("PD_ONE_UNC_DOCX_ROOTS", raising=False)


def _authorize(monkeypatch, payload: dict[str, Any], helper: FakeHelper | None = None) -> FakeHelper:
    calls: list[tuple[str, str]] = []

    def fake_authorize(user_id: str, path: str) -> dict[str, Any]:
        calls.append((user_id, path))
        return dict(payload)

    monkeypatch.setattr(unc.acl, "authorize", fake_authorize)
    fake = helper or FakeHelper()
    monkeypatch.setattr(unc.acl, "sqlsrv", fake)
    fake.authorize_calls = calls  # type: ignore[attr-defined]
    return fake


def _run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    try:
        code = unc.main(list(argv))
    except SystemExit as exc:
        code = int(exc.code or 0)
    return code, json.loads(capsys.readouterr().out)


def test_builtin_sip_root_is_allowlisted_and_finance_is_not():
    assert unc.matching_root(SIP_FILE)["root"] == SIP_ROOT
    assert unc.matching_root(FINANCE) is None
    with pytest.raises(SystemExit):
        unc.require_allowlisted(FINANCE)


def test_ampersand_share_and_dotted_escape_are_normalized():
    assert unc.normalize_unc(r"//sql-srv/SIP&SOP/SIP/_原檔_新版本") == SIP_ROOT
    with pytest.raises(SystemExit):
        unc.normalize_unc(SIP_ROOT + r"\..\Finance\secret.docx")


def test_pagination_walks_past_two_hundred_names():
    names = [f"{SIP_ROOT}\\sip-{index:04d}.docx" for index in range(250)]
    first = unc.page_names(names, "", 200)
    assert first["has_more"] is True and len(first["items"]) == 200
    second = unc.page_names(names, first["next_cursor"], 200)
    assert second["has_more"] is False and len(second["items"]) == 50
    assert second["items"][0] == names[200]


def test_named_table_extracts_weight_and_skips_appearance():
    xml = _docx_xml(
        [["重量檢測", "規格"], ["上限", "10g"]],
        [["外觀檢查", "結果"], ["刮傷", "無"]],
        titles=["重量檢測", "外觀檢查"],
    )
    weight = unc.extract_named_tables(xml, "重量檢測")
    assert weight["match_count"] == 1
    assert weight["tables"][0]["rows"][1] == ["上限", "10g"]
    appearance = unc.extract_named_tables(xml, "外觀檢查")
    assert appearance["match_count"] == 1
    assert appearance["tables"][0]["rows"][0][0] == "外觀檢查"


def test_helper_visible_name_without_requester_ace_is_withheld():
    items = [
        {"full_name": SIP_FILE, "requester_can_read": True},
        {"full_name": FINANCE, "matched_aces": []},
    ]
    kept, withheld = unc.filter_items_for_requester(
        items, identities=["JSPD\\person"], admin_bypass=False
    )
    assert [item["full_name"] for item in kept] == [SIP_FILE]
    assert withheld == 1


def test_list_refuses_before_helper_when_ntfs_denies(monkeypatch, capsys):
    helper = _authorize(monkeypatch, {
        "authorized": False, "admin_bypass": False, "identities": ["JSPD\\person"],
        "error": "NTFS does not grant Read",
    })
    code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--root", SIP_ROOT)
    assert code != 0 and payload["authorized"] is False
    assert helper.payloads == []
    assert helper.authorize_calls == [(REQUESTER, SIP_ROOT)]


def test_admin_bypass_can_list_without_identities(monkeypatch, capsys):
    helper = _authorize(
        monkeypatch,
        {"authorized": True, "admin_bypass": True, "identities": []},
        FakeHelper(listing={
            "ok": True, "scanned": 1, "denied_count": 0, "errors": [],
            "items": [{"full_name": SIP_FILE, "requester_can_read": True}],
        }),
    )
    code, payload = _run(capsys, "--requester-user-id", ADMIN, "--root", SIP_ROOT)
    assert code == 0 and payload["items"][0]["full_name"] == SIP_FILE
    assert helper.authorize_calls == [(ADMIN, SIP_ROOT)]


def test_list_refuses_when_identities_are_missing(monkeypatch, capsys):
    helper = _authorize(monkeypatch, {"authorized": True, "admin_bypass": False, "identities": []})
    code, payload = _run(capsys, "--requester-user-id", REQUESTER, "--root", SIP_ROOT)
    assert code != 0 and "identities unavailable" in payload["error"]
    assert helper.payloads == []


def test_list_pages_only_requester_readable_docx(monkeypatch, capsys):
    listing = {
        "ok": True,
        "scanned": 3,
        "denied_count": 1,
        "errors": [],
        "items": [
            {"full_name": SIP_ROOT + r"\a.docx", "requester_can_read": True},
            {"full_name": SIP_ROOT + r"\b.docx", "requester_can_read": True},
            {"full_name": SIP_ROOT + r"\hidden.docx", "matched_aces": []},
        ],
    }
    helper = _authorize(
        monkeypatch,
        {"authorized": True, "admin_bypass": False, "identities": ["JSPD\\person"], "windows_sam": "person"},
        FakeHelper(listing=listing),
    )
    code, payload = _run(
        capsys, "--requester-user-id", REQUESTER, "--root", SIP_ROOT, "--limit", "1",
    )
    assert code == 0
    assert payload["item_count"] == 1
    assert payload["items"][0]["full_name"].endswith(r"\a.docx")
    assert payload["has_more"] is True
    assert payload["safety"]["helper_identity_does_not_bypass_acl"] is True
    assert helper.payloads and "Get-Acl" in helper.payloads[0]


def test_finance_never_reaches_authorize_or_helper(monkeypatch, capsys):
    helper = _authorize(monkeypatch, {"authorized": True, "admin_bypass": True, "identities": []})
    code, payload = _run(
        capsys, "--requester-user-id", REQUESTER, "--action", "extract",
        "--path", FINANCE, "--table-name", "重量檢測",
    )
    assert code != 0 and "allowlisted" in payload["error"]
    assert helper.payloads == []
    assert helper.authorize_calls == []


def test_extract_reauthorizes_each_file_and_returns_named_cells(monkeypatch, capsys):
    xml = _docx_xml([["重量檢測", "規格"], ["下限", "2g"]])
    helper = _authorize(
        monkeypatch,
        {"authorized": True, "admin_bypass": False, "identities": ["JSPD\\person"]},
        FakeHelper(extract={"ok": True, "document_xml": xml, "errors": []}),
    )
    code, payload = _run(
        capsys, "--requester-user-id", REQUESTER, "--action", "extract",
        "--path", SIP_FILE, "--table-name", "重量檢測",
    )
    assert code == 0
    assert payload["files"][0]["tables"][0]["rows"][1] == ["下限", "2g"]
    assert helper.authorize_calls == [(REQUESTER, SIP_FILE)]
    assert helper.payloads and "word/document.xml" in helper.payloads[0]


def test_unauthorized_extract_never_reads_document_xml(monkeypatch, capsys):
    helper = _authorize(monkeypatch, {
        "authorized": False, "admin_bypass": False, "identities": ["JSPD\\person"],
        "error": "NTFS does not grant Read",
    })
    code, payload = _run(
        capsys, "--requester-user-id", REQUESTER, "--action", "extract",
        "--path", SIP_FILE, "--table-name", "重量檢測",
    )
    assert code == 0
    assert payload["ok"] is False
    assert payload["files"][0]["authorized"] is False
    assert helper.payloads == []


def test_docx_zip_fixture_round_trip():
    data = _docx_bytes([["重量檢測", "值"]], titles=["重量檢測"])
    found = unc.extract_named_tables_from_docx(data, "重量檢測")
    assert found["match_count"] == 1
    assert found["tables"][0]["rows"][0] == ["重量檢測", "值"]
