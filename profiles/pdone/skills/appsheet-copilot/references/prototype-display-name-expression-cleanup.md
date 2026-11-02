# Prototype Display Name expression cleanup

Use this when an AppSheet prototype/Data Studio app reports many `Display Name` expression errors after cloning/subsetting a larger app.

## Durable pattern

A prototype can inherit localized `DisplayName` formulas from the production app, for example:

```appsheet
=SWITCH(
  ANY(Current User[Language]),
  "zh-tw", "中文名字",
  "Name - Chinese"
)
```

If the prototype does not include the `Current User` table/slice, AppSheet can flag those Display Name expressions even when the rest of the app definition is structurally valid. The safe cleanup is to patch only `DisplayName` properties that contain the exact missing language selector and replace the selector with a constant language token, usually `"en"` for the prototype:

```diff
- ANY(Current User[Language])
+ "en"
```

Do not broadly replace every `Current User[Language]` occurrence unless the requester asks for a wider cleanup. Non-DisplayName references may live in `Show_If`, descriptions, defaults, or compiled metadata and can have different semantics.

## Recommended workflow

1. Load `references/appsheet-definition-json-sync.md` and `references/appsheet-editor-save-streaming-readback.md` before live editor writes.
2. Fresh-load the live app definition via `/api/loadApp/<appId>` using the authenticated editor session/profile already used for AppSheet work.
3. Recursively scan raw app JSON for string properties where key is exactly `DisplayName` and value contains `Current User[Language]`.
4. Dry-run patch a local copy only:
   - replace `ANY(Current User[Language])` with `"en"` inside `DisplayName` values only;
   - assert `before_count == change_count`;
   - assert local remaining `DisplayName` references to `Current User[Language]` is `0`.
5. Save via `/api/saveapp` with `validate: true` and gzipped JSON payload.
6. Immediately read back `/api/loadApp/<appId>` and verify:
   - version advanced;
   - save response success is true;
   - `appErrors.Errors` is empty or expected;
   - remaining raw or compiled `DisplayName` references to `Current User[Language]` is `0`.
7. Report the receipt directory, app id, version before/after, change count, and readback summary. Mention separately if `IsRunnable` remains false for unrelated reasons.

## Session receipt examples / expanded pattern

For prototype app `3d6f2d39-9f45-488a-9f5d-6a931d83bd63`, 202 `DisplayName` expressions were changed from `ANY(Current User[Language])` to `"en"`; save succeeded; version advanced from `26.033027` to `26.033028`; readback showed zero remaining DisplayName language references and `appErrors.Errors: []`.

Follow-up correction: the prototype also had hundreds of DisplayName errors like:

```text
Column name 'ExternalLinkID' in Schema 'ExternalLinks_Schema' has an invalid Display Name '=LOOKUP("ExternalLinkID","Lookup","LookupID","Translation")'. Can't find column "Translation" in table "Lookup"
```

Cause: the prototype `Lookup` table has `en` / `zh-tw` / `Description_en` / `Description_zh-tw`, but no `Translation` or `Description Translation` column. Clear these by patching raw `DisplayName` values only:

- exact `=LOOKUP("SomeKey","Lookup","LookupID","Translation")` → static `SomeKey` (or an approved English label);
- exact dynamic `=LOOKUP(CONTEXT("View"),"Lookup","LookupID","Translation")` → `=CONTEXT("View")`;
- embedded `LOOKUP(...,"Translation")` / `LOOKUP(...,"Description Translation")` inside `CONCATENATE()` → replace just that lookup call with a quoted static label so the remaining expression stays valid.

The reusable workspace script now handles both missing `Current User[Language]` DisplayName selectors and missing `Lookup[Translation]` / `Lookup[Description Translation]` DisplayName lookups:

```text
/home/prodesign/.openclaw/workspace/tools/appsheet-migration/scripts/patch_prototype_datastudio_display_names.py
```

Verified follow-up receipt: 460 additional DisplayName lookup errors were patched; version advanced from `26.033030` to `26.033031`; readback showed `display_name_issue_counts={current_user_language:0, lookup_translation:0}`, no missing Lookup return columns in DisplayName expressions, `appErrors.Errors: []`, and `IsValid: true`. The app still had `IsRunnable: false`, so report that separately unless further requested.

If using or adapting that script, keep credentials redacted in output and avoid printing cookie/key material.

## Save-response AppErrors can reveal more than loadApp

For prototype app `3d6f2d39-9f45-488a-9f5d-6a931d83bd63`, `/api/loadApp` returned `appErrors.Errors: []` while the `/api/saveapp` response still returned validation `AppErrors`. Always inspect the save response after a validated editor save before declaring cleanup complete.

After DisplayName lookup errors are removed, save-response `AppErrors` may expose non-DisplayName prototype blockers:

- invalid column `Description` expressions referencing missing `Lookup[Translation]` / `Lookup[Description Translation]`;
- enum `Valid_If` / `TypeAuxData` ORDERBY sort terms using missing `[Translation]`;
- form views referencing deleted event actions such as `AL_OpenAfterSubmit`, `Case_OpenAfterSubmit`, or `Maintenance_Session_OpenAfterSubmit`;
- orphan format rules with empty `ColumnsToFormat`;
- stale deployed-app `LogoUrl` values.

Use the prototype cleanup script for that wider pattern:

```text
/home/prodesign/.openclaw/workspace/tools/appsheet-migration/scripts/patch_prototype_datastudio_app_errors.py
```

The script is scoped to app-definition fixes: it clears invalid descriptions, removes stale/erroring DisplayNames completely, removes missing event actions from both `ViewDefinition.Events` and `Settings.Events`, fixes the enum `Valid_If`, assigns the orphan format rule to its intended column, clears the stale logo URL, then verifies via both save-response `AppErrors` and loadApp readback (`IsValid`, `IsRunnable`, `appErrors`). It does not edit source table records or share lists; duplicate-key warnings and sign-in allowlist info may require separate data/share-list actions.
