# Sheet + chat maintenance automation pattern

Use this pattern for workflows that read a human-owned Google Sheet, monitor chat threads, append progress/history, and optionally DM responsible people.

## Architecture split

- Keep sheet-local stable ID assignment inside the Sheet when possible, e.g. bound Apps Script with `LockService` and document properties.
- Keep chat API calls, summarization/filtering, dedup state, DM queues, and reply correlation in the backend automation.
- Use a visible stable ID column for human-readable cross-reference, not row numbers. Row numbers are only transient write targets after looking up the stable ID.

## Sheet write safety gates

Before any live write:

1. Read live headers and verify critical columns by exact header, not just by remembered letters. Example for the Project List: `F=處理人`, `G=改善歷程`, `I=對話連結`.
2. Refuse writes if duplicate stable IDs exist.
3. Resolve the row by stable ID and require exactly one match.
4. Compose the full new cell value by appending to the existing human text; do not overwrite history blindly.
5. Check whether the exact proposed entry is already present before appending so state loss/retries do not duplicate history.
6. Write the single target range, then read it back and verify the appended entry exists.

## Dedup and concurrency

- Track source chat post IDs/timestamps only after the sheet write succeeds.
- Use a process-level lock in the CLI/script for both scheduled and manual runs. If the CLI already takes that lock, do not also wrap the same service command in external `flock` on the same file; nested nonblocking locks can make a healthy oneshot fail as “already active.”
- Log proposals in dry-run mode and completed writes in live mode.
- Before enabling a recurring chat-thread monitor on existing threads, seed a baseline state that marks currently visible/historical posts as seen without writing sheet history. Then run a normal dry-run and verify it reports zero or only genuinely new proposals; otherwise the first timer run may flood logs or append stale history.
- Prefer one-issue live pilots before broad writes.

## Apps Script ID assignment

For visible sheet IDs like `PL-2026-0001`:

- Use `LockService.getDocumentLock()` around assignment.
- Do not overwrite existing IDs.
- Define what makes a row meaningfully populated; skip blank/formula-only trailing rows.
- On every run, scan existing IDs for the current year and set `nextNumber = max(documentPropertyNextNumber, maxExisting + 1)`. This prevents duplicate IDs if document properties are reset or the script is reinstalled.
- A time-driven trigger is often more reliable than `onEdit` alone because it catches pasted/imported/formula-populated rows.
- Before promising the backfill is complete, verify the helper column can actually be created: protected whole-tab/header-row ranges can block adding the far-right ID column or writing the header even when the automation account can read the sheet. If blocked, report it as a permission/protected-range action item for a sheet owner, not as a completed install.

## Chat follow-up behavior

- Build responsible-person queues from a reviewed mapping file; do not guess user IDs.
- When mapping names to chat users, implement a discovery/report command that is safe and non-sending. For Chinese names, search both the full name and likely given-name substring because profile search may index surname/given fields separately. Auto-enable only exact display-name matches; ambiguous candidates stay disabled/unresolved for review.
- Multi-owner rows should have explicit behavior (`ask_all`, owner priority, or admin review).
- Prompt one item at a time per person.
- Correlate replies to a pending prompt and sender ID before writing back.
- Keep workday/holiday logic explicit and timezone-labeled.
- Do not wait indefinitely for organic chat activity before finishing implementation. Add explicit non-sending validation paths: synthetic/unit tests for reply correlation, dry-run prompt previews, a `--person`/`--limit` pilot selector, and an `--ignore-workday` preview gate for controlled tests outside the normal schedule. Keep live sends behind a separate `--send` flag and live sheet writes behind `--write`.

## `gog sheets update` note

For the current `gog` CLI, single-cell or range writes should use `--values-json '<2D array>'`; do not invent `--values-file` unless `gog sheets update --help` confirms it exists in the installed version.
