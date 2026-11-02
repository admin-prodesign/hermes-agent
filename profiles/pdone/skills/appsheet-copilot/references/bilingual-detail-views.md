# Bilingual Detail Views for Screenshot Sharing

Use this pattern when employees need screenshots of AppSheet detail records to be readable by both Chinese- and English-speaking employees, regardless of the screenshot taker's current language.

## Pattern

For persisted language-specific translation columns that are normally hidden by user language, keep forms/list contexts language-specific but force both translations visible in Detail views by widening the column `Show_If` expression:

```appsheet
OR(
  CONTEXT("ViewType") = "Detail",
  ANY(Current User[Language]) = "en"
)
```

```appsheet
OR(
  CONTEXT("ViewType") = "Detail",
  ANY(Current User[Language]) = "zh-tw"
)
```

This avoids changing the translated label/virtual-column logic and avoids cluttering forms. Existing column order controls whether the fields appear next to/near each other in detail views.

## Confirmed Pro-Design columns

For Cases:

- `Case[Title_en]`
- `Case[Title_zh-tw]`
- `Case[Description_en]`
- `Case[Description_zh-tw]`

For Activity Log:

- `ActivityLog[Description_en]`
- `ActivityLog[Description_zh-tw]`
- `ActivityLog[TroubleshootingActions_en]`
- `ActivityLog[TroubleshootingActions_zh-tw]`

For Case Updates / related detail records that appear inside Case screenshots:

- `Case_Updates[Update_Summary_en]`
- `Case_Updates[Update_Summary_zh-tw]`
- `Case_Updates[Update_Description_en]`
- `Case_Updates[Update_Description_zh-tw]`

For `Case_Updates`, preserve any existing “hide duplicate translation” form behavior inside the non-detail branch. Example:

```appsheet
OR(
  CONTEXT("ViewType") = "Detail",
  AND(
    [Update_Summary_en] <> [Update Summary],
    ANY(Current User[Language]) = "en"
  )
)
```

## Verification checklist

1. Fresh-sync `/api/loadApp` first and confirm the columns still exist in raw `AppData.DataSchemas[*].Attributes[*].TypeAuxData.Show_If`.
2. Apply only `TypeAuxData.Show_If` edits for the intended translation columns.
3. Save via `/api/saveapp` with validation.
4. Fresh-sync again and verify the exact `Show_If` expressions persisted.
5. Check `Version` vs `StableVersion`; if latest is not stable, promote with `POST https://www.appsheet.com/Manage/SetStableVersion` using the owner/admin editor web session, then fresh-sync and require `StableVersion == Version` before reporting done.
6. If the admin browser profile is unreadable but a durable noVNC/CDP browser is already running, use it as the login handoff path: give Andy the noVNC URL/password privately when possible, have him log into AppSheet owner/admin in that browser, then use the existing CDP/editor session to call `SetStableVersion` and verify. Rotate the VNC password after sharing it in a channel.

## Pitfalls

- Do not replace `Label`, `Description_Translated`, or other current-language virtual formulas for this screenshot requirement; the request is about showing both persisted language columns in detail views.
- Do not broaden language-specific `Show_If` unconditionally, or forms and tables become cluttered for normal users.
- Before reporting a promotion blocker, explicitly try the owner/admin editor profile from `browser-profiles/tailscale-login` when available; the default OpenClaw profile may show `ownerInfo.email = admin@prodesign-group.com` but still have delegated `role = 3` and fail promotion.
- If stable promotion fails with the misleading Enterprise-plan error while `ownerInfo.email` is `admin@prodesign-group.com` but `role` is `3`, treat it as the known role/session promotion blocker; save can still succeed, but production visibility requires promotion from the owner/admin editor session with the higher role.
- If `browser-profiles/tailscale-login/Local State` is not readable by the current Hermes user (for example `root:root 600`), report that the admin-profile promotion attempt is blocked by local file permissions instead of implying AppSheet itself rejected the owner/admin session.
