# ECRN signed-document compilation after approvals

Use this when an ECRN approval pilot thread reaches `complete` and Andy/admin asks PD One to prepare the signed ECRN document for the requester to print and obtain final physical signatures.

## Durable workflow lesson

After all electronic approvals are collected, do **not** stop at a Mattermost completion notice. The expected next artifact is the original ECRN document with the collected approvals inserted into the relevant signature cells.

## Required sequence

1. Verify the ECRN runner state and thread approvals are complete.
2. Retrieve the **original ECRN `.doc` attachment** from the ECRN root post. Do not use a previously regenerated/reformatted draft as the source.
3. Extract/inspect the table structure enough to identify the relevant signature cells.
4. Insert compact approval text into the existing cells, preserving the original document layout as much as possible:
   - person display name
   - timestamp, preferably Taiwan local time (TPE) unless asked otherwise
   - approval/comment text exactly as provided when relevant, e.g. `同意`
   - include additional comments if the approver provided more than a bare approval token
   - within a signature cell, sort by approval timestamp ascending (earliest at the top, latest at the bottom)
   - remove a terminal Mattermost bilingual auto-edit marker such as `<!-- bilingual-autoedit:v1 -->` and omit the translated duplicate; bare bilingual approval pairs should render once as canonical `同意`; marker-like text embedded in a normal comment must remain literal
   - capture the preferred printable block and auto-edit metadata before truncating the runner's audit excerpt so long translated replies cannot leak duplicate or partial marker text into the DOCX
5. Keep the table/form layout intact. Do **not** rebuild the document as new HTML/Word content unless the user explicitly asks for a clean recreated form.
6. Default for the approved `~ecrn` send-mode runner: automatically post the signed Word-openable document back to the original ECRN thread after all required approvals are complete. Verify the Mattermost post/file receipt and store a state marker such as `signed_document_posted` to prevent duplicate sends.
7. Only use Andy/admin review-first handling when Andy/admin explicitly requests it for that case; then do not post back to the `~ecrn` production thread until approved.

## Cell placement pattern from E-202606-01 pilot

For the original `良器公司 工程變更申請單(ECRN)` legacy `.doc`, the relevant table rows were:

- `業務` signature cell: insert all Sales approvers.
- `生管` signature cell: insert Production Control approver(s).
- `成型` signature cell: insert Injection Molding approver(s).
- `倉庫` signature cell: insert Logistics / materials/logistics approver(s).
- `品管` signature cell: insert QA approver(s).

Keep unrelated paper/final-approval fields such as `副總經理審核` and `總經理審核` empty unless the corresponding approval was actually collected for that field.

## Implementation notes

- Legacy `.doc` files may require a Word-compatible library to edit without rebuilding layout. If using Spire.Doc or similar, load the original `.doc`, modify only existing `TableCell` paragraphs, save back to `.doc`, then reload and verify target cell text.
- If a library injects an evaluation warning, do not ship a document with visible tool watermarks/warnings; use a licensed/non-watermark path or remove only the injected warning if technically safe and verified.
- Verify by reading the saved document back and checking:
  - table row/cell structure is still present,
  - expected approval text is in the intended cells,
  - no tool warning or accidental extra page/title was introduced.

## User preference captured

Andy explicitly corrected that PD One must preserve the original document formatting: “Don’t change the formatting of the document. Take the original document then insert the contents into the relevant table cells.” Treat this as the default for future ECRN signed-document work.
