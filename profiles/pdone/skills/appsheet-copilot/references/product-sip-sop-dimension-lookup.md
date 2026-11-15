# Product SIP/SOP dimension lookup

Use this when an authorized Pro-Design user asks for product dimensions, rim/mouth dimensions, lid fit dimensions, SIP/SOP documents, or mold/product document references.

## Authorization, searchable scope, and source hierarchy

- SIP/SOP content is not admin-only. It should be indexed/searchable for the authorized work groups that need product/reference-document knowledge: **R&D**, **Sales**, **QA**, **Production**, and **Senior Staff**.
- Product dimensions are operational production/quality information. Check the requester against Mattermost/AppSheet policy before sending details outside admin context, but do not unnecessarily restrict SIP/SOP search to admins when the requester is in one of the authorized work groups above.
- Production managers and users with product-quality / work-manual access may receive the relevant dimensions for their work scope.
- If updating AppSheet/Reference Doc visibility, scope the SIP/SOP Reference_Documents/search surface to role/group tokens for R&D, Sales, QA, Production, and Senior Staff. Current confirmed tokens include `Team_RnD`, `Team_Sales`, `Team_QA`, production-side `Team_Factory` / `Team_Molding_Staff` as appropriate, and `Team_SeniorStaff`; verify exact token names from the current AppSheet definition/Lookup roles before writing changes.
- Canonical documents now live in the Google Drive `sql-srv` mirror, under `sql-srv/SIP&SOP/`:
  - `SIP/` contains inspection/specification sheets; product dimensions are normally here.
  - `SOP/` contains operating procedure documents; use these for procedure context or to cross-check AppSheet Reference Doc records.
- AppSheet `Reference_Documents` contains a useful subset of SIP/SOP metadata and attachment paths. Use it to resolve product/mold/document IDs, but confirm dimensions from the canonical SIP document when possible.

## AppSheet Reference_Documents scan

Use the prototype app API for reads unless Andy explicitly requests deployed-app context.

Example bounded query:

```bash
PYTHONPATH=/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts \
python3 /home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts/appsheet_table_probe.py \
  Reference_Documents \
  'FILTER("Reference_Documents", OR(CONTAINS([Label_Helper1], "1GB-2"), CONTAINS([Products], "1GB"), CONTAINS([All_Related_Assets], "1GB"), CONTAINS([File], "PD-171")))'
```

Fields to inspect:

- `ReferenceDocumentID`
- `Doc Type` (`RefDoc_SIP` / `RefDoc_SOP`)
- `Revision`, `Effective Date`, `Active`
- `Molds` such as `APD-171` or `APD-231`
- `Products`, `All_Related_Assets`
- `File`
- `Label_Helper1` / `Label`

For the 2026-05-15 1GB-2 lookup, AppSheet returned:

- `RD-20250710-095320-31b74c` — `SOP (PD-231 1GB-2 桶)`
- `RD-20250710-095607-1c86ca` — `SOP (PD-171 1GB-2 平蓋)`

## Google Drive sql-srv mirror lookup

Known root:

- `sql-srv` folder id: `1muf80eKLbwmxPErXI8jWm-uTVMLZ4AlZ`
- `sql-srv/SIP&SOP` folder id observed 2026-05: `1dxD8Wb63jHhG0nWAV0W6OzHNyrovYEhN`
- `sql-srv/SIP&SOP/SIP` folder id observed 2026-05: `1bIThJ6kC4dRtrnRkVzK2ejjts7ohp2XN`
- `sql-srv/SIP&SOP/SOP` folder id observed 2026-05: `1aGEeu6DT4JOLh-IhZll9mno48K-IT3Ua`

List or tree the SIP/SOP folders read-only:

```bash
/home/prodesign/.local/bin/gog drive tree \
  --account admin@prodesign-group.com \
  --json --no-input \
  --parent 1bIThJ6kC4dRtrnRkVzK2ejjts7ohp2XN \
  --depth 3 --max 2000
```

Search local tree output for product code, PD number, and Chinese product type (`桶`, `平蓋`, etc.). Prefer current files at SIP folder depth 1 over `_PDF_淘汰資料` unless specifically researching history.

For the 1GB-2 case, current SIP files found under `sql-srv/SIP&SOP/SIP` were:

- `1GB-2桶-SIP-廠內版V2-20220503-PD-231.pdf`
- `1GB-2平蓋-SIP-廠內版V6-20230206-PD-171.pdf`

## Download and extract

Download the canonical SIP PDF to a temp folder:

```bash
mkdir -p /tmp/product-sip
/home/prodesign/.local/bin/gog drive download <FILE_ID> \
  --account admin@prodesign-group.com \
  --no-input \
  --output /tmp/product-sip/<safe-name>.pdf
```

If the PDF is image-only, render it and use visual/OCR extraction. PyMuPDF works well if installed:

```python
import fitz
pdf = "/tmp/product-sip/file.pdf"
doc = fitz.open(pdf)
pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
pix.save(pdf.replace(".pdf", ".png"))
```

Then use vision/OCR on the rendered PNG and extract the dimension table. Report exact labels, nominal values, tolerances, and standard ranges. If visual quality is poor, say which values are uncertain and ask for QA/Engineering confirmation before closing.

## Reporting and review_log closure

When answering an employee:

- State the source documents by name and whether they are AppSheet references or canonical Drive SIP files.
- Provide dimensions with units and tolerances.
- If the request came from `review_log`, close only the original request row after sending the answer to the original requester; do not infer the requester from a later discussion summary.
- Add a concise note with the Mattermost post id and the source documents used.

## Example: 1GB-2 bucket/rim dimensions

From `1GB-2桶-SIP-廠內版V2-20220503-PD-231.pdf`:

- 桶口外徑: `180.0 ± 0.3 mm`; standard range `179.7–180.3 mm` after 24h.
- 桶口內徑參考值: `174 ± 0.3 mm`.
- 桶口厚度: `1.4 ± 0.2 mm`; standard range `1.2–1.6 mm`.
- 桶口結構厚度: `3.1 ± 0.2 mm`; standard range `2.9–3.3 mm`.
- 桶口結構高度: `2.1 ± 0.2 mm`; standard range `1.9–2.3 mm`.
- 第一道卡溝高度: `7.8 ± 0.2 mm`; standard range `7.6–8.0 mm`.

Cross-check from `1GB-2平蓋-SIP-廠內版V6-20230206-PD-171.pdf`:

- 蓋口外徑: `181.0 ± 0.3 mm`; standard range `180.7–181.3 mm` after 24h.
- 止水線直徑: `174.4 ± 0.3 mm`; standard range `174.1–174.7 mm`.
- 蓋面高度: `19.5 ± 0.5 mm`; standard range `19–20 mm`.
