# Mattermost XLSX attachment recovery for PD One

Use when an employee says PD One promised or should have attached an XLSX/file but the Mattermost response has no attachment.

## Priority sequence
1. **Recover and deliver the file first** before doing root-cause analysis. The user-facing miss is the missing attachment; fix that immediately if the artifact exists.
2. Search PD One/OpenClaw employee workspaces and artifact directories for the expected output file, especially:
   - `/home/prodesign/.openclaw/workspace-employee/artifacts/`
   - request-specific temporary/workspace folders if present
3. **Identify the recipient unambiguously before any send.** Do not send based on first name only. Cross-check the original Mattermost sender/channel/thread or exact account profile (`username`, `first_name`, `last_name`, display name). If there are multiple plausible employees, resolve the exact user first.
4. Send the recovered file directly to the verified affected employee/channel/thread.
5. Verify the final Mattermost post has real attachment metadata (`file_ids` / file info), not just visible text saying a file was sent.
6. Only after delivery is verified, investigate why the original PD One response omitted the attachment.

## Mattermost auth-metadata pitfall
When a DM-enabled employee uploads an XLSX/XLSM and PD One refuses with “no verifiable Mattermost sender id / user permission data”, do **not** assume the user lacks DM permission or that the attachment failed. Verify three separate layers:

1. Mattermost REST post evidence: original post `user_id`, `channel_id`, `file_ids`, and file info show whether the bot can see the upload.
2. Review-log/auth evidence: `auth_profile_found`, `auth_dm_enabled`, `auth_decision`, `mattermost_post_id`, and `source_session` show whether policy allows the sender.
3. Agent-visible prompt evidence: inspect the employee-assistant session/trajectory (`context.compiled` and `prompt.submitted`) to see whether trusted inbound metadata actually included the sender id the runbook requires.

A known failure mode: OpenClaw may know the sender id internally (session key/review log) and may pass a downloaded attachment manifest to the agent, but the trusted inbound metadata exposed to the model contains only `account_id`, `channel`, `provider`, `surface`, and `chat_type`. The agent then follows the DM authorization runbook and refuses because it cannot read `policy-cache/users/<sender_id>.json`, even though the user is profiled and the attachment is downloadable. Root cause is inbound-context/auth metadata propagation, not Excel processing. Fix by adding/preserving trusted `sender_id` (and preferably `chat_id`/`message_id`) in Mattermost DM inbound prompt construction, plus a regression for a DM-enabled user with an attachment.

## Mattermost media-send pitfall
Before 2026-05-19, PD One/OpenClaw Mattermost media delivery could silently degrade to a text-only post: the send command returned success and the text could imply an attachment, but Mattermost `file_ids` stayed empty.

Two related paths were fixed/hotfixed on 2026-05-19:
- Hermes `tools/send_message_tool.py` commit `c41dad6a1` routes `Platform.MATTERMOST` media through `/api/v4/files`, posts with `file_ids`, and treats missing post `file_ids` as delivery failure.
- Local PD One/OpenClaw install `/home/prodesign/.npm-global/lib/node_modules/openclaw/dist/` was hotfixed so `openclaw message send --channel mattermost --media ...` passes local media read capability into Mattermost upload and throws `Mattermost media upload failed: ...` instead of falling back to text-only posting.

Treat command success as insufficient unless readback verifies the attachment. If OpenClaw is upgraded/reinstalled, re-smoke-test Mattermost `--media` because installed package files may be overwritten.

Durable source tracking for PD One/OpenClaw customizations:
- Prefer installing/building PD One/OpenClaw from the maintained downstream branch instead of relying on generated `dist` hotfixes.
- Current branch: `admin-prodesign/openclaw` branch `pd-one/custom-openclaw-patches`.
- This branch is intentionally **not** a narrow single-issue branch; it preserves all PD One/OpenClaw source customizations that were present in the operational checkout, including but not limited to this Mattermost attachment fix.
- Before updating PD One/OpenClaw, compare the target upstream update against this branch and identify which custom changes are already covered by upstream.
- After updating, make sure any custom changes not covered by upstream are reapplied/ported back in before considering the update complete.
- When creating or refreshing this branch, inspect the working tree first and include all user-intended custom changes. Do not discard or split out unrelated-looking local changes unless the user explicitly asks for a narrow PR-style branch.

Required verification after any Mattermost file send:
- Fetch/read back the created post.
- Confirm `file_ids` is non-empty and points to the uploaded file.
- Confirm the visible filename matches the intended employee-facing filename.
- Delete any smoke-test or misleading text-only posts after verification.

If the post is text-only:
1. Delete the misleading text-only post if it could confuse the employee.
2. Upload/send via the Mattermost file upload API or another lower-level path that returns file metadata.
3. Verify the replacement post has `file_ids` and the uploaded file info.

## Mandatory Office no-corruption validation before delivery
All Hermes/PD One edits to employee-uploaded Office documents must pass an explicit no-corruption/open-clean gate before upload or employee delivery. This is mandatory for XLSX/XLSM/DOCX/PPTX because Pro-Design has repeatedly seen processed files that Excel/Word cannot open cleanly.

Minimum gate (use `scripts/office_no_corruption_gate.py <artifact>` from this skill when available):
1. Verify the output is a valid ZIP/OpenXML package with expected core members (`[Content_Types].xml`, workbook/document/presentation XML, relationships). Fail closed if ZIP validation fails.
2. Reopen the saved artifact with the relevant library (`openpyxl.load_workbook(..., keep_vba=True)` for XLSM/XLSX, `python-docx` for DOCX, PPTX parser for PPTX) and inspect expected sheets/pages/slides/changed cells/content.
3. Run LibreOffice/soffice headless open/export/convert validation when available. Treat conversion/open errors, zero-byte outputs, or generated repair logs as blockers. For DOCX/PPTX, render to PDF/PNG and visually QA employee-facing layout. For XLSX/XLSM, prefer LibreOffice headless open/recalc/export to catch repair-level XML issues.
4. For macro-enabled XLSM, preserve VBA (`keep_vba=True`) and do not claim VBA was installed/edited unless the VBA project was actually and safely updated. If the environment cannot validate Excel macro behavior, say so and include paste-ready VBA/instructions instead.
5. If any validation layer cannot run because dependencies are unavailable, either install/use the standard fallback or explicitly report the limitation before delivery. Do not silently send an unchecked Office file.
6. Only after validation passes, upload the file and read back Mattermost `file_ids` plus visible filename/size.

## Recovery replay pattern for Excel/XLSM edit requests
When PD One refused or failed an employee-uploaded Excel/XLSM edit request but the Mattermost file is visible:

1. **Recover/deliver before root-cause work**: fetch the original post and file info via Mattermost REST, verify exact `username`/display name/channel/thread, then download the attachment.
2. For `.xlsm`, preserve macros with `openpyxl.load_workbook(..., keep_vba=True)`. If the task requires adding or changing VBA but the headless environment cannot safely recompile the VBA project, do the best safe workbook edit and add an instruction sheet with paste-ready VBA instead of claiming a true macro/button was installed.
3. Inspect workbook sheets/target rows before editing. For Chinese workbooks, preserve original sheet names and add visible instructions in the workbook rather than relying only on the Mattermost message.
4. Save a clearly named recovered artifact (for example `*_PDOne修改版.xlsm`) and reopen it with `keep_vba=True` to verify sheet names, changed cells/formulas, file size, and that the workbook is readable.
5. Upload with Mattermost file API, reply in the original thread/root when possible, then read back the created post and each `file_id` info. Treat upload or send success as unverified until the visible filename and non-empty `file_ids` match.
6. If the recovery is tied to an open `review_log` row, close that original row after verified delivery: set `follow_up_needed=no`, `review_status=closed`, and record the corrective reply/attachment post id plus filename in `notes`/`reply_summary`. Do not rely only on the scanner-created `attachment_sent` row; that row audits the new bot post but does not automatically close the original no-reply/failure row.
7. In the employee-facing recovery reply, explain briefly that the system-side metadata/attachment handling failed and that the attached file is the recovered version; do not expose internal paths, policy-cache details, or stack traces.

## Example from session
Eric Lee / Mattermost `@ericlee242` (李祐豪) reported that PD One should have produced an XLSX but did not attach it. The artifact existed at:

```text
/home/prodesign/.openclaw/workspace-employee/artifacts/mold_in_mold_label_progress_template.xlsx
```

The correct recovery was to verify the exact recipient first, then send it to Eric Lee and verify Mattermost returned a post with real attachment metadata and a file id. A first-name-only send caused a wrong-recipient DM to Eric Liu; delete/mitigate any wrong-recipient post immediately, then resend to the verified user. The initial OpenClaw media-send path produced text-only posts; replace through Mattermost file upload API and verify `file_ids`.

A later Eric Lee XLSM recovery showed a separate failure mode: Mattermost REST and thread attachment manifest had the XLSM and the DM session key had Eric's id, but the trusted inbound metadata visible in `context.compiled` only included `account_id`, `channel`, `provider`, `surface`, and `chat_type`. PD One obeyed the DM authorization runbook and refused because no trusted `sender_id` was present. For this class, inspect both `context.compiled` and `prompt.submitted`: attachment manifests can be present while trusted identity is missing. The recovery path was to download `模內貼_開發進度表_v4.xlsm`, edit with `openpyxl`/`keep_vba=True`, add a workbook instruction sheet with paste-ready VBA for the true button behavior, upload `模內貼_開發進度表_v4_PDOne修改版.xlsm` to the original thread, and verify Mattermost returned non-empty `file_ids` with the expected filename.