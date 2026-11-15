# ECRN digital approval discovery

## When to use
Use this reference when Andy/admin asks PD One to analyze, digitize, pilot, or redesign Pro-Design ECRN / engineering-change approval workflows.

## Key source locations found
- Google Sheet: `良器-技術發展部-ECRN`
  - ID: `1fOk3hDP1Q7bBB224w1HxPVXLJopaXvUd49oU1PWgSSU`
  - Purpose: ECRN number register and tracking sheet.
  - Created around 2022-06-01; active and recently modified in 2026.
- Existing Mattermost Playbook migration artifact:
  - Template: `/home/prodesign/.openclaw/workspace/artifacts/mattermost-playbooks-migration-20260601/templates/0000-台灣良器-ECRN.md`
  - Raw playbook ID: `qiuprhudn7rm5ezcp6opsp8d3w`
  - Migration audit showed 0 observed runs, so do not assume the playbook was operationally used.
- Historical Yammer/Mattermost migration records contain ECRN discussion and announcement evidence; use bounded keyword searches only when the requester is admin/approved and the scope permits history review.

## Current process facts discovered
The old playbook describes ECRN as required when product size, function, weight, or BOM changes, to confirm customer acceptability.

Google Sheet monthly tabs issue numbers like `E-202605-01` and track:
- ECRN number
- change item
- applicant
- paper R&D archive confirmation (`紙本研發歸檔確認`)
- Yammer/company-wide announcement confirmation (`YAMMER 全公司發布確認`)
- notes

Sheet instructions seen on monthly tabs:
1. Applicant fills the monthly serial number/change item, e.g. `E-202206-03`.
2. Paper should return to R&D for archive.
3. Yammer/company-wide announcement should be made/confirmed.

Existing Mattermost ECRN playbook checklist:
1. **ECRN data creation**
   - Requester updates ECRN summary/change content.
   - If attachments exist, open a topic in the ECRN channel and paste the link into the playbook summary.
   - Create ECRN code and add it to the ECRN master sheet.
2. **Department checks**
   - Sales / 業務
   - Injection Molding / 成型
   - QA / 品保
   - Mold Repair / 模修
   - Materials / 資材
3. **Final check**
   - VP / 副總
   - General Manager / 總經理
   - Document Control Center issuance/archive / 文管中心發行歸檔

## Recommended digital pilot pattern
For a small first pilot, do **not** rebuild a full system immediately. Keep the ECRN Google Sheet as the number source and use one Mattermost thread/playbook run per ECRN to replace paper signature chasing.

Suggested pilot scope:
- Low-risk SOP/SIP/inspection wording/cycle-time/measurement-position changes.
- Exclude mold structure, product structure, customer spec, material cost, ERP/BOM pricing, or high-impact operational changes unless separately approved.

Mattermost thread first post should include:
- ECRN number and short title: `E-YYYYMM-NN | product | short change`
- before value
- after value
- reason
- affected SOP/SIP/BOM/drawing/customer
- attachment or source links
- required approver list

Approval replies should be standardized:
- `同意 / Approve`
- `不同意 / Reject`
- `需修改 / Need changes`

PD One can summarize:
- who approved
- who is pending
- blockers/questions
- ready/not ready for final release

After final approval:
- Document Control marks issued/archived.
- ECRN Sheet should receive the Mattermost thread link and completion status, but this is a write and requires explicit approved-user confirmation/dry-run where practical.

## Signed-document generation after approvals
When Andy/admin asks to generate the signed ECRN document after all required approvals are complete:
1. Re-verify the live runner state/thread before generating: Sales must be complete and downstream approvers must match the ECRN form `會辦單位` checkbox routing, not a hard-coded department list.
2. Generate from the original ECRN Word attachment, insert digital approval names/timestamps/post IDs into the matching signature rows, then run structural DOCX validation and visual Office QA/render when practical.
3. Post the signed DOCX back into the same Mattermost ECRN thread as `pdone`, not as a top-level message. Include a concise bilingual status note.
4. @mention the original submitter resolved from the root post user id; do not assume the display name from thread text.
5. Verify delivery by reading back the created Mattermost post: correct `root_id`, channel, non-empty `file_ids`, filename, and file size. Report the post ID and file ID as receipts.

## Pitfalls
- Employee-facing workspace search may not surface the ECRN sources. For Andy/admin reprocessing, use the admin workspace and Google Sheet registry/source references instead of concluding no ECRN file exists.
- The existing Mattermost ECRN playbook exists, but 0 observed runs means it is evidence of intended checklist structure, not evidence of actual current practice.
- Do not expose private policy mechanics or broad raw history in shared employee-facing replies. Summarize only the minimum needed for the approved request.
