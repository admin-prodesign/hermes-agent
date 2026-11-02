# Department-group editor plus admin-only sheet protection

Use this whenever PD One **creates** a company Google Sheet, or when Andy asks to apply the same ACL/protection model to an existing one.

Andy standing rule (2026-09-23): the matching department Google Group must have **file-level Editor**, but tabs that are not meant for humans to type in get **sheet protection** so only admin identities can edit. Catalog add/remove/pause still happens **through PD One**, not by colleagues editing cells in the Google UI.

## Two layers (do not mix them up)

1. **Drive file ACL** — who can **open** the spreadsheet and who Google treats as an Editor.
2. **Sheet protection** (`protectedRanges`) — who can **change cells** in the Google UI even if they are file Editors.

Department members need layer 1 as `writer` so they can open the link, Portal snapshots stay in-family, and PD One can later add/remove rows on their behalf. Layer 2 blocks accidental UI edits on automation catalogs.

## File ACL (every new company Sheet)

Immediately after create, before claiming the Sheet is complete:

1. Resolve the owning department Google Group from `config/portal_department_taxonomy.json` `google_groups` (Facilities = `facilities@prodesign-group.com`).
2. `gog drive permissions <spreadsheetId> --account admin@prodesign-group.com --json --no-input`.
3. If that group is missing or weaker than `writer`, grant:

```bash
gog drive share <spreadsheetId> \
  --to=user --email=<group@prodesign-group.com> --role=writer \
  --account admin@prodesign-group.com --json --no-input
```

   gog v0.20+ has no `--type group`; a group email is the recipient. **Do not** pass `--notify` unless Andy asked to email the group.
4. Read permissions back. Require `emailAddress=<group>`, `type=group`, `role=writer`. `type=user` or `reader`/`commenter` is a failed grant — do not claim the department can open/edit.
5. Do **not** add `type=user` writers because a person asked to edit. Do **not** raise the parent folder from `reader` to `writer` just to match the file (folder writer would expose sibling files). File-level writer is enough to open the link.
6. Leave existing `cxo@` / owner / Andy-assistant ACLs unchanged unless Andy asked.

This file-level group Editor grant is standing create-time work, same family as work-manual Doc sharing. It is **not** a later follow-up.

## Sheet protection (tabs not meant for human UI edits)

Apply when the tab is a PD One / runner / snapshot **source of truth** (recurring-task catalogs, reminder trackers, generated sync tabs). Skip when the tab is intentionally human-filled (operators type daily values, selectors, or a work-manual-style log).

1. Read live metadata first:

```bash
gog sheets metadata <spreadsheetId> --account admin@prodesign-group.com --json --no-input
```

   Inspect `sheets[].protectedRanges`. An empty `range` with only `sheetId` is **whole-tab** protection.
2. If a whole-tab protection already exists, **do not** add a second one (`addProtectedRange` fails on duplicate whole-sheet protection). Read `editors.users` / `editors.groups`, `warningOnly`, and `requestingUserCanEdit`.
3. Required shape for PD One-owned catalogs:
   - whole tab (range = `{sheetId}` only);
   - `warningOnly` absent or `false` (hard block, not a warning);
   - `editors.users` includes `admin@prodesign-group.com` (keep Andy's existing admin-side editors such as `andylinassistant@gmail.com` if already present);
   - department Google Group is **not** in `editors.groups`;
   - `requestingUserCanEdit` is `true` for the Gog account so runners/`sheets_safe_ops.py` still write.
4. If protection is missing, add it via Sheets API `spreadsheets.batchUpdate` `addProtectedRange` (gog has no first-class protect command as of v0.37). Description example: `PD One source tab; edit through PD One, not the Google UI`.
5. Do **not** delete a human-created whole-tab protection to replace it. Verify it already matches the required shape; only add when none exists.
6. A protected tab is **not** a PD One API write block when `requestingUserCanEdit` is true. Runners keep using `admin@prodesign-group.com`.

## Human change path

Tell the department: open/view is fine; add, pause, retire, or retarget a row by asking **PD One** in the owning Mattermost channel. Do not tell people to type into a protected catalog.

## Worked example (Facilities recurring tasks)

- Spreadsheet `1w1JAybCT8lfh9kt5jGzCJVdYTqt71qBBPtCl1cNWBos` (`良器-廠務-定期任務 Facilities Recurring Tasks`).
- Parent folder `1z_48kI2gh6tDA5QNa85DFeXWZHdWCh01` stays `facilities@` **reader**.
- File ACL: `facilities@` `type=group` `role=writer`.
- Tab `定期任務 Recurring Tasks` whole-sheet protection; editors `admin@prodesign-group.com` and `andylinassistant@gmail.com`; `requestingUserCanEdit=true` for admin Gog.

## Verification receipt

Report both layers:

- Drive: group email, `type=group`, `role=writer`.
- Protection: tab title, whole-sheet vs range, editor emails, `warningOnly`, `requestingUserCanEdit`.
- Folder ACL left unchanged (cite reader vs writer).
