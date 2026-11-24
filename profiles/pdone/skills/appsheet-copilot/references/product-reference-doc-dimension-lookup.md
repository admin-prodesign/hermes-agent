# Product reference document and dimension lookup

Use this pattern when a Pro-Design employee asks for product dimensions, rim/opening sizes, SIP/SOP details, or a product drawing/reference document.

## Source order

1. **Authorization/context**: identify the requester from the live channel/review row before deciding disclosure. Production, QA, engineering, and other operations roles may be authorized for product dimension data, while HR/training/personnel records require tighter approval.
2. **AppSheet Reference Doc module**: query `Reference_Documents` in the prototype app to find the relevant product/mold/doc records. Useful fields include:
   - `Doc Type` (`RefDoc_SIP`, `RefDoc_SOP`)
   - `ReferenceDocumentID`
   - `Molds` / `All_Related_Assets`
   - `Products`
   - `File`
   - `Label_Helper1` / `Label`
3. **Canonical Drive mirror**: search/read Google Drive root `sql-srv` only when the task explicitly asks for SIP/SOP/product-file lookup. Current canonical SIP/SOP tree is `sql-srv/SIP&SOP`, with separate `SIP` and `SOP` subfolders plus old/original-file folders.
4. **SIP over SOP for dimensions**: use SIP PDFs as the dimension source of truth. SOP records help identify the product/mold/doc ID, but SIP sheets usually contain the standard dimension table.

## Useful probes

Find AppSheet reference docs by product/mold terms:

```bash
PYTHONPATH=/home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts \
python3 /home/prodesign/.openclaw/workspace/skills/appsheet-copilot/scripts/appsheet_table_probe.py \
  Reference_Documents \
  'FILTER("Reference_Documents", OR(CONTAINS([Label_Helper1], "<TERM>"), CONTAINS([Products], "<TERM>"), CONTAINS([All_Related_Assets], "<TERM>"), CONTAINS([File], "<TERM>")))'
```

Browse canonical Drive SIP/SOP root once the task explicitly includes `sql-srv`/SIP/SOP scope:

```bash
/home/prodesign/.local/bin/gog drive ls --account admin@prodesign-group.com --json --no-input --parent 1muf80eKLbwmxPErXI8jWm-uTVMLZ4AlZ --max 200
/home/prodesign/.local/bin/gog drive tree --account admin@prodesign-group.com --json --no-input --parent <SIP_OR_SOP_FOLDER_ID> --depth 3 --max 2000
```

Download only the narrowed target files, then extract/render the PDF for dimension reading. If text extraction is empty, render to image and visually read the standard dimension table; scanned SIP PDFs often have no embedded text.

## Reporting pattern

- State both source layers checked: AppSheet `Reference_Documents` record(s) and canonical Drive `sql-srv/SIP&SOP` file(s).
- Give the document identifiers: `ReferenceDocumentID`, PD/mold number, filename, revision/effective date when visible.
- Separate bucket/body dimensions from matching lid dimensions.
- Use exact labels from the SIP sheet, include tolerance and standard range when both are visible.
- If answering an employee from `review_log`, send through PD One to the original requester identified by `user_label`/channel/user id, not by a prior handoff summary.

## Example: 1GB-2 rim/opening lookup

For `1GB-2 桶 桶口尺寸資訊`, AppSheet records resolved related docs:

- `RD-20250710-095320-31b74c` — SOP `(PD-231 1GB-2 桶)`
- `RD-20250710-095607-1c86ca` — SOP `(PD-171 1GB-2 平蓋)`

Canonical SIP PDFs in `sql-srv/SIP&SOP/SIP`:

- `1GB-2桶-SIP-廠內版V2-20220503-PD-231.pdf`
- `1GB-2平蓋-SIP-廠內版V6-20230206-PD-171.pdf`

Extracted SIP dimensions:

- Bucket PD-231: 桶口外徑 `180.0±0.3 mm`, range `179.7–180.3`; 桶口內徑參考值 `174±0.3 mm`; 桶口厚度 `1.4±0.2 mm`, range `1.2–1.6`; 桶口結構厚度 `3.1±0.2 mm`, range `2.9–3.3`; 桶口結構高度 `2.1±0.2 mm`, range `1.9–2.3`; 第一道卡溝高度 `7.8±0.2 mm`, range `7.6–8.0`.
- Matching lid PD-171: 蓋口外徑 `181.0±0.3 mm`, range `180.7–181.3`; 止水線直徑 `174.4±0.3 mm`, range `174.1–174.7`; 蓋面高度 `19.5±0.5 mm`, range `19–20`.
