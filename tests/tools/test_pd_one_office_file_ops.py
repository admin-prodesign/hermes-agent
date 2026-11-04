"""Employee-safe Office file ops under approved PD One document roots."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest

from tools.pd_one_ops import pd_one_office_file_ops as office_ops

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"


def _zip_xlsx(path: Path, rows: list[list[str]]) -> None:
    shared = []
    index = {}
    sheet_rows = []
    for row in rows:
        cells = []
        for col, value in enumerate(row, start=1):
            label = chr(64 + col)
            if value not in index:
                index[value] = len(shared)
                shared.append(value)
            cells.append(f'<c r="{label}{len(sheet_rows)+1}" t="s"><v>{index[value]}</v></c>')
        sheet_rows.append(f'<row r="{len(sheet_rows)+1}">{"".join(cells)}</row>')
    shared_xml = "".join(f"<si><t>{text}</t></si>" for text in shared)
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{R}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{R}/sharedStrings" Target="sharedStrings.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst xmlns="{S}" count="{len(shared)}" uniqueCount="{len(shared)}">{shared_xml}</sst>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{S}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, xml in parts.items():
            package.writestr(name, xml)


class _FakeWorksheet:
    def __init__(self, title: str):
        self.title = title
        self._rows: list[list] = []

    def append(self, row: list) -> None:
        self._rows.append(list(row))


class _FakeWorkbook:
    def __init__(self):
        self.active = object()
        self.calculation = types.SimpleNamespace(fullCalcOnLoad=False)
        self._sheets: list[_FakeWorksheet] = []
        self._path: Path | None = None

    def remove(self, _sheet) -> None:
        return None

    def create_sheet(self, title: str) -> _FakeWorksheet:
        sheet = _FakeWorksheet(title)
        self._sheets.append(sheet)
        return sheet

    def save(self, path: Path | str) -> None:
        self._path = Path(path)
        rows: list[list] = []
        for sheet in self._sheets:
            rows.extend(sheet._rows)
        _zip_xlsx(self._path, [[str(cell) for cell in row] for row in rows])

    def close(self) -> None:
        return None


@pytest.fixture
def pdone_root(tmp_path, monkeypatch):
    root = tmp_path / "pdone"
    (root / "tmp").mkdir(parents=True)
    monkeypatch.setattr("tools.pd_one_ops.pd_one_safe_ops_part0.ROOT", lambda: root)
    monkeypatch.setattr("tools.pd_one_ops.pd_one_office_file_ops.ROOT", lambda: root)
    return root


def test_xlsx_write_verifies_chinese_shared_strings(pdone_root, monkeypatch):
    fake = _FakeWorkbook()

    class _WorkbookFactory:
        def __call__(self):
            return fake

    monkeypatch.setitem(sys.modules, "openpyxl", types.SimpleNamespace(Workbook=_WorkbookFactory()))
    spec_path = pdone_root / "tmp" / "spec.json"
    out_path = pdone_root / "tmp" / "out.xlsx"
    spec_path.write_text(
        json.dumps(
            {
                "sheets": [
                    {
                        "name": "数据",
                        "rows": [["标题", "中文"], ["=A1&\"!\"", "测试"]],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = office_ops.write_office_file(out_path, spec_path)
    assert result["status"] == "ok"
    assert result["build"]["shared_strings_verified"] is True
    assert result["build"]["has_formulas"] is True
    assert result["build"]["formula_cached_values_claimed"] is False
    assert fake.calculation.fullCalcOnLoad is True
    with zipfile.ZipFile(out_path) as archive:
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
    assert "中文" in shared
    assert "测试" in shared


def test_csv_round_trip(pdone_root):
    source = pdone_root / "tmp" / "source.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["a", "b"])
        writer.writerow(["1", "2"])
    read_back = office_ops.read_office_file(source)
    assert read_back["rows"] == [["a", "b"], ["1", "2"]]
    spec_path = pdone_root / "tmp" / "csv-spec.json"
    out_path = pdone_root / "tmp" / "copy.csv"
    spec_path.write_text(json.dumps({"rows": read_back["rows"]}), encoding="utf-8")
    write_back = office_ops.write_office_file(out_path, spec_path)
    assert write_back["status"] == "ok"
    assert out_path.read_text(encoding="utf-8").splitlines() == ["a,b", "1,2"]


def test_path_outside_approved_roots_rejected(pdone_root, tmp_path):
    outside = tmp_path / "outside.csv"
    outside.write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside approved"):
        office_ops.read_office_file(outside)


def test_mcp_wrapper_does_not_invoke_shell(pdone_root, monkeypatch):
    captured: dict[str, list] = {}

    def fake_run_json(cmd, timeout=60):
        captured["cmd"] = cmd
        assert cmd[0] == sys.executable
        assert cmd[2] == "office-file-ops"
        return json.dumps({"status": "ok", "capability": "pd_one_office_file_ops"})

    monkeypatch.setattr("tools.pd_one_ops.pd_one_safe_ops_mcp_part0.run_json", fake_run_json)
    from tools.pd_one_ops import pd_one_safe_ops_mcp as mcp

    payload = json.loads(
        mcp.pd_one_office_file_ops(
            action="read",
            input_path=str(pdone_root / "tmp" / "missing.csv"),
        )
    )
    assert payload["status"] == "ok"
    assert "office-file-ops" in captured["cmd"]
    assert all(part not in {"bash", "sh", "/bin/sh"} for part in captured["cmd"])
