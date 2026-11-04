#!/usr/bin/env python3
"""List and extract named Word tables on allowlisted UNC shares via the requester's NTFS rights.

Staff-wide and read-only. Every list/extract calls ``pd_one_sqlsrv_windows_acl_read.authorize``
for the exact Mattermost sender before the sql-srv helper identity is used. The helper never
returns a path the requester cannot Read. Extra UNC roots come from ``pd_one.unc_docx_roots``.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from tools.pd_one_ops import pd_one_sqlsrv_windows_acl_read as acl

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
LIST_LIMIT_MAX = 200
EXTRACT_MAX_FILES = 10
EXTRACT_MAX_BYTES = 5_000_000
TABLE_SCAN_MAX = 40
TABLE_ROW_MAX = 80
TABLE_CELL_TEXT_MAX = 1000
BUILTIN_ROOTS: list[dict[str, Any]] = [
    {
        "root": r"\\sql-srv\SIP&SOP\SIP\_原檔_新版本",
        "skip_folders": ["淘汰或已發行新版SIP原檔留存"],
    }
]


def _external() -> bool:
    return os.environ.get("PD_ONE_EXTERNAL_INTERPRETER", "").strip() not in {"", "0"}


def fail(message: str, extra: dict[str, Any] | None = None, code: int = 2) -> None:
    payload = {"ok": False, "authorized": False, "status": "error", "error": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def normalize_unc(raw: str) -> str:
    text = str(raw or "").strip().replace("/", "\\")
    if not text.startswith("\\\\"):
        fail("UNC path required", {"path": raw})
    parts = [part for part in text.split("\\") if part]
    if len(parts) < 2:
        fail("UNC path must include a share", {"path": raw})
    if any(part in {".", ".."} for part in parts):
        fail("Refusing path with . or .. components", {"path": raw})
    if any(":" in part for part in parts):
        fail("Refusing path component containing ':'", {"path": raw})
    return "\\\\" + "\\".join(parts)


def under_root(path: str, root: str) -> bool:
    path_l = normalize_unc(path).casefold()
    root_l = normalize_unc(root).casefold()
    return path_l == root_l or path_l.startswith(root_l + "\\")


def _root_entry(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str) and raw.strip():
        return {"root": normalize_unc(raw), "skip_folders": []}
    if not isinstance(raw, dict):
        return None
    root = str(raw.get("root") or "").strip()
    if not root:
        return None
    skips = raw.get("skip_folders") or raw.get("skip") or []
    if isinstance(skips, str):
        skips = [skips]
    return {
        "root": normalize_unc(root),
        "skip_folders": [str(name).strip() for name in skips if str(name).strip()],
    }


def merge_roots(builtin: list[dict[str, Any]], extra: list[Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    for item in list(builtin) + list(extra):
        entry = _root_entry(item)
        if entry is None:
            continue
        key = entry["root"].casefold()
        if key in index:
            existing = merged[index[key]]
            seen = {name.casefold() for name in existing["skip_folders"]}
            for name in entry["skip_folders"]:
                if name.casefold() not in seen:
                    existing["skip_folders"].append(name)
                    seen.add(name.casefold())
            continue
        index[key] = len(merged)
        merged.append(entry)
    return merged


def configured_roots() -> list[dict[str, Any]]:
    extra: list[Any] = []
    raw = os.environ.get("PD_ONE_UNC_DOCX_ROOTS", "").strip()
    if _external() or raw:
        extra = json.loads(raw) if raw else []
    else:
        from tools.pd_one_ops.site_config import unc_docx_roots

        extra = unc_docx_roots()
    roots = merge_roots(BUILTIN_ROOTS, extra)
    if not roots:
        fail("no allowlisted UNC Word roots are configured")
    return roots


def matching_root(path: str) -> dict[str, Any] | None:
    normalized = normalize_unc(path)
    for entry in configured_roots():
        if under_root(normalized, entry["root"]):
            return {**entry, "path": normalized}
    return None


def require_allowlisted(path: str) -> dict[str, Any]:
    found = matching_root(path)
    if found is None:
        fail(
            "path is outside the allowlisted UNC Word roots",
            {"path": path, "allowlisted_roots": [entry["root"] for entry in configured_roots()]},
        )
    if acl.RED_LINE_PATH_RE.search(found["path"]):
        fail("payroll, credential, and HR-evaluation paths are not readable through PD One", {"path": found["path"]})
    return found


def page_names(names: list[str], cursor: str, limit: int) -> dict[str, Any]:
    limit = max(1, min(int(limit), LIST_LIMIT_MAX))
    ordered = sorted(str(name) for name in names if str(name).strip())
    if cursor:
        ordered = [name for name in ordered if name > cursor]
    page = ordered[:limit]
    return {
        "items": page,
        "has_more": len(ordered) > limit,
        "next_cursor": page[-1] if page and len(ordered) > limit else "",
    }


def _q(name: str) -> str:
    return f"{W}{name}"


def _cell_text(cell: ET.Element) -> str:
    return "".join(node.text or "" for node in cell.findall(f".//{_q('t')}"))


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(f".//{_q('t')}"))


def table_cells(table: ET.Element, *, max_rows: int = TABLE_ROW_MAX) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in list(table.findall(_q("tr")))[:max_rows]:
        cells = []
        for cell in row.findall(_q("tc")):
            text = _cell_text(cell)
            if len(text) > TABLE_CELL_TEXT_MAX:
                text = text[:TABLE_CELL_TEXT_MAX] + "…"
            cells.append(text)
        rows.append(cells)
    return rows


def table_matches_name(rows: list[list[str]], table_name: str, preceding: str = "") -> bool:
    needle = table_name.strip().casefold()
    if not needle:
        return False
    if needle in preceding.casefold():
        return True
    for row in rows[:3]:
        for cell in row:
            if needle in (cell or "").casefold():
                return True
    return False


def extract_named_tables(document_xml: bytes | str, table_name: str) -> dict[str, Any]:
    name = str(table_name or "").strip()
    if not name:
        fail("table_name is required for extract")
    raw = document_xml.encode("utf-8") if isinstance(document_xml, str) else document_xml
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        fail("DOCX document XML contains a forbidden declaration")
    root = ET.fromstring(raw)
    body = root.find(_q("body"))
    blocks = list(body) if body is not None else list(root)
    matches: list[dict[str, Any]] = []
    scanned = 0
    pending = ""
    for child in blocks:
        if child.tag == _q("p"):
            pending = _paragraph_text(child)
            continue
        if child.tag != _q("tbl"):
            continue
        scanned += 1
        if scanned > TABLE_SCAN_MAX:
            break
        rows = table_cells(child)
        if table_matches_name(rows, name, pending):
            matches.append({"table_index": scanned - 1, "row_count": len(rows), "rows": rows})
        pending = ""
    return {
        "table_name": name,
        "tables_scanned": scanned,
        "match_count": len(matches),
        "tables": matches,
    }


def extract_named_tables_from_docx(data: bytes, table_name: str) -> dict[str, Any]:
    if len(data) > EXTRACT_MAX_BYTES:
        fail(f"DOCX exceeds the {EXTRACT_MAX_BYTES} byte extract limit")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            fail("DOCX is missing word/document.xml")
            raise AssertionError("unreachable") from exc
    return extract_named_tables(document_xml, table_name)


def ace_grants_read(aces: list[dict[str, Any]]) -> bool:
    return acl._read_aces(aces, "Allow") and not acl._read_aces(aces, "Deny")


def filter_items_for_requester(
    items: list[dict[str, Any]],
    *,
    identities: list[str],
    admin_bypass: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Drop helper-visible names the requester cannot Read. Admin bypass stays inside authorize()."""
    if admin_bypass:
        kept = [item for item in items if isinstance(item, dict) and not acl._red_line(item.get("full_name"))]
        return kept, len(items) - len(kept)
    if not identities:
        return [], len(items)
    wanted = {name.casefold() for name in identities}
    kept: list[dict[str, Any]] = []
    withheld = 0
    for item in items:
        if not isinstance(item, dict):
            withheld += 1
            continue
        if acl._red_line(item.get("full_name")):
            withheld += 1
            continue
        aces = [ace for ace in (item.get("matched_aces") or []) if isinstance(ace, dict)]
        if aces:
            matched = [ace for ace in aces if str(ace.get("identity") or "").casefold() in wanted]
            if ace_grants_read(matched):
                kept.append({key: value for key, value in item.items() if key != "matched_aces"})
                continue
            withheld += 1
            continue
        if item.get("requester_can_read") is True:
            kept.append(item)
            continue
        withheld += 1
    return kept, withheld


def list_payload(root: str, skip_folders: list[str], cursor: str, limit: int, identities: list[str], admin_bypass: bool) -> str:
    skip_ps = ",".join(ps_quote(name) for name in skip_folders) or ps_quote("")
    ident_ps = ",".join(ps_quote(name) for name in identities) or ps_quote("")
    return f"""
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$result = [ordered]@{{
  ok = $true
  command = 'list'
  target = {ps_quote(root)}
  items = @()
  errors = @()
  denied_count = 0
  scanned = 0
}}
function Add-Err([string]$msg) {{ $result.errors += $msg; $result.ok = $false }}
$skip = @({skip_ps})
$idents = @({ident_ps})
$cursor = {ps_quote(cursor)}
$limit = {int(limit)}
$adminBypass = ${str(bool(admin_bypass)).lower()}
$set = @{{}}
foreach ($id in $idents) {{ if ($id) {{ $set[$id.ToLower()] = $true }} }}
function Skip-Folder([string]$full) {{
  if ($skip.Count -eq 0) {{ return $false }}
  foreach ($part in $full.Split('\\')) {{
    if ($skip -contains $part) {{ return $true }}
  }}
  return $false
}}
function Requester-CanRead([string]$full) {{
  if ($adminBypass) {{ return $true }}
  if ($set.Count -eq 0) {{ return $false }}
  try {{
    $acl = Get-Acl -LiteralPath $full
    $allow = $false
    $deny = $false
    foreach ($ace in $acl.Access) {{
      $id = $ace.IdentityReference.Value
      if (-not $set.ContainsKey($id.ToLower())) {{ continue }}
      $rights = $ace.FileSystemRights.ToString()
      $readish = $rights -match 'Read|ReadAndExecute|Modify|FullControl|ListDirectory|GenericRead'
      if ($readish -and $ace.AccessControlType.ToString() -eq 'Deny') {{ $deny = $true }}
      if ($readish -and $ace.AccessControlType.ToString() -eq 'Allow') {{ $allow = $true }}
    }}
    return [bool]($allow -and -not $deny)
  }} catch {{ return $false }}
}}
try {{
  if (-not (Test-Path -LiteralPath {ps_quote(root)})) {{ Add-Err 'Path not found or helper cannot see it'; throw 'missing' }}
  $files = @(Get-ChildItem -LiteralPath {ps_quote(root)} -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {{ $_.Extension -eq '.docx' -and -not (Skip-Folder $_.FullName) }} |
    Sort-Object FullName)
  if ($cursor) {{ $files = @($files | Where-Object {{ $_.FullName -gt $cursor }}) }}
  foreach ($f in $files) {{
    $result.scanned++
    if ($f.FullName -match {ps_quote(acl.RED_LINE_PATH_RE.pattern)}) {{ $result.denied_count++; continue }}
    if (-not (Requester-CanRead $f.FullName)) {{ $result.denied_count++; continue }}
    $result.items += [ordered]@{{
      full_name = $f.FullName
      length = $f.Length
      last_write_time = $f.LastWriteTime.ToString('o')
      requester_can_read = $true
    }}
    if (@($result.items).Count -ge ($limit + 1)) {{ break }}
  }}
}} catch {{
  if ($_.Exception.Message -ne 'missing') {{ Add-Err $_.Exception.Message }}
}}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '__OUT__' -Encoding UTF8
"""


def extract_payload(path: str, max_bytes: int) -> str:
    return f"""
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$result = [ordered]@{{
  ok = $true
  command = 'extract'
  path = {ps_quote(path)}
  document_xml = $null
  length = 0
  errors = @()
}}
function Add-Err([string]$msg) {{ $result.errors += $msg; $result.ok = $false }}
try {{
  if (-not (Test-Path -LiteralPath {ps_quote(path)})) {{ Add-Err 'Path not found or helper cannot see it'; throw 'missing' }}
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [IO.Compression.ZipFile]::OpenRead({ps_quote(path)})
  try {{
    $entry = $zip.GetEntry('word/document.xml')
    if ($null -eq $entry) {{ Add-Err 'DOCX is missing word/document.xml'; throw 'missing' }}
    if ($entry.Length -gt {int(max_bytes)}) {{ Add-Err 'word/document.xml exceeds extract limit'; throw 'missing' }}
    $stream = $entry.Open()
    $reader = New-Object IO.StreamReader($stream)
    try {{ $result.document_xml = $reader.ReadToEnd() }} finally {{ $reader.Close(); $stream.Close() }}
    $result.length = $result.document_xml.Length
  }} finally {{ $zip.Dispose() }}
}} catch {{
  if ($_.Exception.Message -ne 'missing') {{ Add-Err $_.Exception.Message }}
}}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath '__OUT__' -Encoding UTF8
"""


def run_helper(payload: str) -> dict[str, Any]:
    helper = acl._sqlsrv()
    vals = helper.load_env()
    session, host, user, password = helper.make_session(vals)
    result = helper.run_via_task(session, user, password, payload, timeout=180)
    result["via"] = {"host": host, "helper": "sqlsrv_readonly", "smb_identity": "redacted-vm-helper"}
    return result


def authorize_path(requester_user_id: str, path: str) -> dict[str, Any]:
    if not str(requester_user_id or "").strip():
        fail("requester_user_id is required; UNC Word access follows that employee's NTFS rights")
    return acl.authorize(requester_user_id, path)


def _auth_summary(auth: dict[str, Any]) -> dict[str, Any]:
    return {
        key: auth.get(key)
        for key in ("authorized", "admin_bypass", "windows_sam", "matched_ace_count", "identities", "path")
    }


def default_root() -> dict[str, Any]:
    return configured_roots()[0]


def cmd_list(args: argparse.Namespace) -> None:
    spec = require_allowlisted(args.root or default_root()["root"])
    auth = authorize_path(args.requester_user_id, spec["root"])
    if not auth.get("authorized"):
        fail(auth.get("error") or "not authorized", {"path": spec["root"], "authorization": _auth_summary(auth)})
    identities = [str(name) for name in (auth.get("identities") or []) if str(name).strip()]
    admin_bypass = bool(auth.get("admin_bypass"))
    if not admin_bypass and not identities:
        fail(
            "NTFS identities unavailable; refusing to list under the helper identity",
            {"path": spec["root"], "authorization": _auth_summary(auth)},
        )
    skip = [] if args.include_skipped else list(spec.get("skip_folders") or [])
    limit = max(1, min(int(args.limit), LIST_LIMIT_MAX))
    raw = run_helper(list_payload(spec["root"], skip, args.cursor or "", limit, identities, admin_bypass))
    items, withheld = filter_items_for_requester(
        [item for item in (raw.get("items") or []) if isinstance(item, dict)],
        identities=identities,
        admin_bypass=admin_bypass,
    )
    page = items[:limit]
    has_more = len(items) > limit
    emit({
        "ok": True,
        "status": "ok",
        "capability": "pd_one_unc_docx_table",
        "action": "list",
        "root": spec["root"],
        "cursor": args.cursor or "",
        "limit": limit,
        "has_more": has_more,
        "next_cursor": page[-1]["full_name"] if page and has_more else "",
        "item_count": len(page),
        "items": page,
        "denied_count": int(raw.get("denied_count") or 0) + withheld,
        "scanned": raw.get("scanned", 0),
        "errors": raw.get("errors") or [],
        "requester_user_id": args.requester_user_id,
        "authorization": _auth_summary(auth),
        "via": raw.get("via"),
        "safety": {
            "read_only": True,
            "writes_implemented": False,
            "per_user_ntfs": True,
            "helper_identity_does_not_bypass_acl": True,
            "allowlisted_unc_only": True,
        },
    })


def _extract_paths(args: argparse.Namespace) -> list[str]:
    found = [str(path).strip() for path in (args.paths or []) if str(path).strip()]
    if args.path:
        found.insert(0, str(args.path).strip())
    unique: list[str] = []
    seen: set[str] = set()
    for path in found:
        key = path.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    if not unique:
        fail("extract requires --path")
    if len(unique) > EXTRACT_MAX_FILES:
        fail(f"extract accepts at most {EXTRACT_MAX_FILES} files")
    return unique


def extract_one(path: str, table_name: str, requester_user_id: str) -> dict[str, Any]:
    spec = require_allowlisted(path)
    auth = authorize_path(requester_user_id, spec["path"])
    summary = _auth_summary(auth)
    if not auth.get("authorized"):
        return {
            "ok": False,
            "authorized": False,
            "path": spec["path"],
            "error": auth.get("error") or "not authorized",
            "authorization": summary,
        }
    raw = run_helper(extract_payload(spec["path"], EXTRACT_MAX_BYTES))
    errors = [str(error) for error in (raw.get("errors") or [])]
    xml_text = raw.get("document_xml")
    if errors or not xml_text:
        return {
            "ok": False,
            "authorized": True,
            "path": spec["path"],
            "error": "; ".join(errors) or "helper did not return document.xml",
            "authorization": summary,
        }
    tables = extract_named_tables(xml_text, table_name)
    return {
        "ok": True,
        "authorized": True,
        "path": spec["path"],
        "authorization": summary,
        **tables,
    }


def cmd_extract(args: argparse.Namespace) -> None:
    name = str(args.table_name or "").strip()
    if not name:
        fail("table_name is required for extract")
    results = [extract_one(path, name, args.requester_user_id) for path in _extract_paths(args)]
    emit({
        "ok": all(item.get("ok") for item in results),
        "status": "ok" if all(item.get("ok") for item in results) else "error",
        "capability": "pd_one_unc_docx_table",
        "action": "extract",
        "table_name": name,
        "file_count": len(results),
        "files": results,
        "requester_user_id": args.requester_user_id,
        "safety": {
            "read_only": True,
            "writes_implemented": False,
            "per_user_ntfs": True,
            "helper_identity_does_not_bypass_acl": True,
            "allowlisted_unc_only": True,
        },
    })


def cmd_run(args: argparse.Namespace) -> None:
    if args.action == "list":
        cmd_list(args)
        return
    cmd_extract(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requester-user-id", required=True)
    parser.add_argument("--action", choices=("list", "extract"), default="list")
    parser.add_argument("--root", default="")
    parser.add_argument("--path", default="")
    parser.add_argument("--paths", action="append", default=[])
    parser.add_argument("--table-name", default="")
    parser.add_argument("--cursor", default="")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--include-skipped", action="store_true")
    parser.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
