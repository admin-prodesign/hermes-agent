# PD One SOP assistant workflow

Use this when implementing, debugging, or smoke-testing employee-facing SOP generation in PD One.

## Target playbook

Scoped employees should be able to ask PD One for an SOP draft (for example `5LH-3 桶`) without receiving broad file-system/admin access.

Expected sequence:

1. Employee asks for a new/revised SOP.
2. PD One uses scoped SOP search against the SOP master workbook to find similar existing products.
3. PD One asks the employee to confirm the source/template product when more than one plausible match exists.
4. PD One creates a local draft only. Draft state and preview artifacts live under the PD One employee workspace, not on `\\sql-srv`.
5. PD One asks targeted questions for missing/changed fields and updates the local draft.
6. PD One generates a Word preview and makes the `.docx` available to the scoped employee.
7. PD One explicitly asks two questions before any official write:
   - Is the Word document/result correct?
   - Should these values be submitted to update the master XLSX?
8. Only if the employee confirms both, PD One creates an admin-approval ticket/request for Andy.
9. After Andy approves the finalization ticket, the admin finalizer performs both official writes as one verified operation:
   - update the SOP master workbook at `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\_SOP資料總表 Product SOP master.xlsx`;
   - store the approved final `.docx` in the same original-SOP-documents folder as the other editable Word originals: `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\<final SOP filename>.docx`.
10. Until Andy says the flow has run cleanly several times, official writes to the SOP master XLSX and final SOP output remain admin-approval-gated.
11. After enough clean runs, policy can be relaxed deliberately for this specific SOP finalization action; do not silently remove approval.

## Implementation pattern

Prefer scoped tools over granting raw admin/file tools to `employee-assistant`:

- `scoped_sop_search`
- `scoped_sop_create_draft`
- `scoped_sop_update_draft`
- `scoped_sop_attach_photo`
- `scoped_sop_generate_preview`
- `scoped_sop_approval_packet`
- existing `request_approval`

The scoped tools should:

- read the official master workbook through the existing bounded `sqlsrv_readonly.py` / `vm01` helper;
- keep employee draft state local and reversible;
- expose only fields/artifacts needed for SOP drafting;
- never write `\\sql-srv` from the employee tool path;
- include a baseline SHA256 of the master workbook in approval packets;
- include preview artifact path/SHA256 and changed fields in approval packets;
- require positive employee confirmation before generating the approval packet.

## Similar-product search expectations

For bucket/cover style product codes, deterministic ranking should favor:

- same family prefix, e.g. `5LH`;
- same part noun, e.g. `桶` vs `蓋`;
- closest numeric/variant distance, e.g. `5LH-3 桶` should rank `5LH-2 桶` above unrelated products;
- rows with populated SOP steps/photos.

Use the ranking reasons in the employee response so the requester can confirm the source product.

## Word document preview

The goal is the proper Word document based on the canonical mail-merge template:

- `\\sql-srv\SIP&SOP\SOP\原檔\_產品包裝SOP.docx`

Do not call a fallback/minimal DOCX “the proper Word document.” A fallback is acceptable only as an explicit degraded preview while debugging, and the smoke report must say it did not pass the proper-template requirement.

Durable rendering approach:

- Read the Word template from `\\sql-srv` via the read-only helper.
- Prefer deterministic OpenXML replacement over unattended Word COM for employee previews when the template uses standard `MERGEFIELD` placeholders. This preserves the canonical `.docx` template while avoiding Word/OLEDB prompts and WinRM scheduled-task hangs.
- Verify the generated DOCX by unzipping the package: in `word/document.xml`, target product and changed field values must be present, source-template product should not remain in product/name fields, and `MERGEFIELD` must be absent/zero. Also inspect `word/settings.xml`, `word/_rels/settings.xml.rels`, `word/recipientData.xml`, and `[Content_Types].xml`; if the canonical template is a mail-merge main document, the preview must strip `<w:mailMerge>`, `mailMergeSource`/`recipientData` relationships, `word/recipientData.xml`, and its content-type override so Word opens the preview as a normal DOCX without prompting for the old `\\sql-srv` Excel data source.
- Treat `canonical-template-openxml-merge` as a proper-template renderer for preview readiness when it starts from `_產品包裝SOP.docx` and passes the DOCX XML checks; do not require `word-com-mailmerge` specifically unless the task is visual/Office-fidelity QA.
- Use `vm01`/Word COM only when visual/Office fidelity actually requires Word automation. Word COM can start on `vm01`, but `MailMerge.OpenDataSource`/`Execute` may hang unattended; if used, run with bounded timeout, clean `WINWORD.EXE`/tasks/transient files, and clearly report degradation.

If any renderer falls back to a synthetic/minimal DOCX, capture the renderer failure in artifact metadata and keep employee/admin messages clear that the proper template did not render.

## Admin approval request shape

When employee confirms the Word document and XLSX write-back, the approval request should include:

- target product and requester;
- source product/row used as template;
- changed fields;
- preview DOCX path and SHA256;
- final DOCX filename and destination path under `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\`;
- baseline master XLSX SHA256;
- baseline destination-state evidence: target DOCX path does not exist, or if replacing, the existing DOCX hash/metadata and explicit replace intent;
- exact intended write scope (`sop_finalize:<draft_id>:\\sql-srv\..._SOP資料總表 Product SOP master.xlsx` plus `\\sql-srv\SIP&SOP\SOP\原檔\<final SOP filename>.docx`);
- acceptance criteria requiring re-read/verification, no unrelated workbook row changes, and destination DOCX hash matching the approved preview/final artifact.

The approval ticket logs the request; it does not itself write the workbook or copy the final DOCX. The admin executor/finalizer must perform the approved scope after Andy approves.

## Official finalization write-back

Folder structure verified through the `vm01`/`sqlsrv_readonly.py` path:

- Published SOP PDFs live directly under `\\\\sql-srv\\SIP&SOP\\SOP\\`.
- Editable/original SOP Word documents live under `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\`.
- SOP source photos live under `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\_SOP照片\\<product/family>\\`.
- The master workbook is `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\_SOP資料總表 Product SOP master.xlsx`.
- The canonical template is `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\_產品包裝SOP.docx`.

The finalizer should therefore treat `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\` as the destination for the approved final `.docx`. It should not store final Word originals only in local draft space, and it should not put the `.docx` at the PDF-publishing root unless a separate PDF/export path is explicitly approved.

Finalization sequence after Andy approval:

1. Re-read/stat the master workbook and destination path from `\\sql-srv` via `vm01`; confirm the master hash still matches the approval baseline, or stop and request re-approval.
2. If the destination `.docx` already exists, stop unless the approval explicitly authorized replacement and includes the existing file hash/metadata.
3. Create local backups of any file that will be replaced/edited: at minimum the baseline master workbook, plus existing destination DOCX if replacing.
4. If employee-uploaded draft photos are part of the approved packet, copy those exact approved image bytes first to `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\_SOP照片\\<product/family>\\`, creating the product photo folder only through the admin write helper's bounded `--create-parent` path.
5. Re-read each official photo from `\\sql-srv` and verify its SHA256 before continuing.
6. Apply only the approved workbook row/cell changes, including `照片路徑`, `照片N`, and `第N` values that point to the approved official photo files.
7. Copy the approved final DOCX to `\\\\sql-srv\\SIP&SOP\\SOP\\原檔\\<final SOP filename>.docx`.
8. Re-read both official outputs from `\\sql-srv` and verify: workbook intended-row values match, no unrelated row changes are present, destination DOCX exists, and destination DOCX hash equals the approved final artifact.
9. Record final artifact metadata in the ticket/result: workbook path/hash before+after, DOCX path/hash, photo path/hash list, filename, timestamp, and verification result.

Any tool that writes to `\\sql-srv` must be separate from the read-only helper. Do not extend employee-scoped tools or `sqlsrv_readonly.py` into a general write path; keep official finalization admin-only and ticket-scoped.

## Beta rollout / post-change readiness gate

Before announcing SOP drafting/photo intake as a beta, verify the employee-facing capability is live end-to-end, not just implemented in source:

1. For every new scoped wrapper, update all three places before restart:
   - plugin source registration/contract export;
   - `openclaw.plugin.json` `contracts.tools` declaration;
   - the target agent's `openclaw.json` tool allowlist, e.g. `employee-assistant.tools.alsoAllow`.
2. Run `openclaw config validate --json` and static checks before restart.
3. Restart/reload the gateway only after the config/manifest/source agree.
4. Inspect startup logs for plugin-contract errors such as `plugin must declare contracts.tools for: <tool>`; treat that as a rollout blocker even if the gateway starts.
5. Run the live employee-assistant security/SOP probe and confirm the tool inventory includes the new wrapper, for example `scoped_sop_attach_photo`.
6. Check gateway health after the probe has settled. A first health call can timeout or show event-loop degradation during startup/probe/model activity; do not call the rollout clean until a later health sample is `ok: true`, plugin errors are empty, and Mattermost is connected.
7. Commit/push OpenClaw config/source changes and refresh Hermes backup after the live probe passes.

## Smoke-test checklist

A passing smoke test should prove all of the following before employee notification or rollout:

1. Scoped employee policy allows the requester and denies unscoped employees.
2. The live `employee-assistant` system-prompt/tool inventory actually exposes all required `scoped_sop_*` tools, not merely that the plugin source code, plugin manifest, or `openclaw.json` contains them.
3. `scoped_sop_search` ranks the expected similar product first.
4. Draft creation/update does not write `\\sql-srv`.
5. Preview DOCX exists, opens, has no unresolved `MERGEFIELD`, has no active mail-merge data-source binding that makes Word ask for `\\sql-srv`/Excel when opened, and is rendered from the proper template if the test claims production readiness.
6. A realistic hypothetical product run has been produced and inspected (for example `5LH-3 桶` from `5LH-2 桶`), with artifact path/SHA shown in the admin report.
7. PD One prompt asks both confirmation questions.
8. Confirmation produces a pending admin-approval ticket automatically.
9. If a temporary workbook write is used for backend verification, the original master XLSX is restored byte-for-byte and verified by SHA256; no smoke row remains.
10. Commit only the narrow SOP files/config/runbooks; avoid unrelated dirty wiki/runtime state.

## Pitfalls

- `request_approval` can time out on review-log append after a ticket is already created. Inspect approval-ticket state/logs before claiming nothing was captured.
- If `request_approval` already has `employee_confirmed=true` and readiness validation passes, the plugin should confirm/notify the ticket immediately; do not force a redundant “please confirm again” employee step.
- Do not treat approval text in an employee/channel thread as tool elevation. Employee tools remain scoped; admin execution must happen through the ticketed approval path.
- Do not describe fallback DOCX output as the final proper Word form.
- Do not remove admin approval just because one smoke run worked; Andy explicitly wants several clean runs first.
- Do not notify an employee that SOP drafting is available until a post-reload/restart live agent probe confirms the employee-facing tool inventory exposes the `scoped_sop_*` wrappers. `openclaw plugins inspect`, plugin source, plugin manifest, and `openclaw.json` are necessary but not sufficient; use an actual `openclaw agent --agent employee-assistant --json ...`/security-probe style check as the readiness gate.
- When adding a new employee-facing scoped tool, remember the plugin manifest contract and the agent allowlist as separate rollout surfaces. If the gateway logs `plugin must declare contracts.tools for: <tool>`, the source registration alone is not enough.
- After a restart/probe, separate capability readiness from transient gateway load: startup/model/probe activity can cause one health timeout or temporary event-loop degradation. Re-sample after it settles and require `ok: true`, no plugin errors, and Mattermost connected before a beta announcement.
