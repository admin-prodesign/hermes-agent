# AppSheet EnumList row API write caveat

Use this when a requested AppSheet data/config update involves a multi-value `EnumList` field, especially role/access fields such as `Lookup[Viewable Roles]`.

## Observed behavior

- AppSheet row API `Edit` may reject multi-value `EnumList` payloads even when equivalent multi-token values are already present in existing rows.
- This can appear during live access/visibility cleanup where the desired value is a list of role tokens such as `Team_RnD`, `Team_QA`, `Team_Sales`, `Team_Factory`, `Team_Molding_Staff`, or `Team_SeniorStaff`.
- Treat rejection as a write-path limitation or table-specific formatting issue, not as proof that the existing role tokens are invalid.

## Safe workflow

1. Read the current schema and row from the synced `/api/loadApp` definition and/or deployed/prototype row API.
2. Verify the exact column type and valid values from raw schema/editor JSON before proposing access changes.
3. Try only a known-safe, reversible dry run or documented payload shape first.
4. If AppSheet rejects a multi-value row API edit, stop before coercing or narrowing access.
5. Prefer one of these routes for live role/visibility updates:
   - AppSheet UI/editor update by an authorized admin.
   - A tested `/api/saveapp` editor-definition update when the field lives in the app definition rather than table data.
   - A table-specific helper that has already proved the exact `EnumList` serialization for that column.
6. After any successful change, re-read the row and verify the persisted role list exactly matches the intended access scope.
7. For Reference Docs/SIP/SOP visibility work, check each relevant `Lookup` row separately. Doc-type rows such as `RefDoc_SIP`/`RefDoc_SOP`, the row-level view slice `RefDocs_MyViewable`, and broad menu/view rows such as `Reference_Documents_All` control different surfaces; one being admin-only does not necessarily mean all SIP/SOP documents are inaccessible.

## Reporting pattern

When blocked, say plainly:

- which row/field was intended to change,
- the desired role tokens,
- that the row API rejected multi-value `EnumList` writes,
- and that the remaining safe path is UI/editor or a tested table-specific serialization workaround.

Do not claim the visibility update is done until a fresh read shows the intended multi-role value persisted.
