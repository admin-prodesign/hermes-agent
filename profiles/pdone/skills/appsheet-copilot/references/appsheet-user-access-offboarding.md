# AppSheet user access/offboarding inspection

Use this when asked who should be removed from AppSheet, whether a departed employee is still invited, or whether PD One can "dis-invite" / remove app access.

## Safe read-only sequence

1. Establish the offboarding window with live time if the user says "last month" / "recently".
2. Pull `HR_Employees` for departed employees:
   - `Employment Status = "Not Employed"`
   - nonblank `Separation Date`
   - date window requested by the user.
3. For each departed employee, check both current access surfaces:
   - `HR_Employees` duplicated/deprecated settings fields: `Appsheet Email`, `Appsheet Roles`, `Combined Appsheet Roles`, `Appsheet Views Access`, `Appsheet Navigation Bar`, `Appsheet Menu Items`, `Appsheet Notification Group`, `Team Members`.
   - `HR_Employees_AppSheet_Settings` by `PersonID` for canonical settings rows.
4. Inspect cached `/api/loadApp` app config for app-level exposure:
   - top-level: `IsPublic`, `IsTeamPublic`, `UsePublicOwner`, `Visibility`, `Status`, `UserRoles`, `OwnerId`, `OriginalOwnerId`, version/stable/last-modified.
   - search the raw app JSON for the target email, `PersonID`, employee ID, and name. A missing email here means it is not hard-coded in the app definition, but does **not** prove absence from the live AppSheet Users/share/allowlist pane. Blank `HR_Employees` role fields and a missing `HR_Employees_AppSheet_Settings` row are the same class of non-proof. Do not mark an offboarding task complete without a `loadUsers` readback that shows the email absent.
   - The table probe selector is an AppSheet filter, not a bare id: `FILTER(HR_Employees, [PersonID] = "P-...")` on `env=deployed`. The default prototype env, or a bare employee number, returns 0 rows and is not "person not found."
5. Clearly separate findings:
   - **App definition config** from `/api/loadApp`.
   - **Table-driven access** from `HR_Employees` / `HR_Employees_AppSheet_Settings`.
   - **Live AppSheet Users/allowlist pane**, which may require authenticated editor UI/session inspection.

## Important limitation

The raw `/api/loadApp` app object used for definition sync may not expose the literal AppSheet editor **Users / share / allowlist** pane. Do not claim a user is not invited solely because their email is absent from `latest_raw_app.json`.

If the user asks to inspect the live Users/allowlist pane, request/confirm approval to use the authenticated AppSheet editor session/cookies in **read-only mode**. Do not remove users or change sharing without a separate explicit approval.

## Live Users/share-list inspection and removal

Use authenticated AppSheet editor session cookies only after Andy/admin approval. The known-good cookie source in this environment is usually:

- Cookies: `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/browser/openclaw/user-data/Default/Cookies`
- Local State: `/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/browser/openclaw/user-data/Local State`

Read-only inspection:

```text
GET https://www.appsheet.com/api/loadUsers/<app_id>
```

The response is JSON with a `subscribers` string; parse it as JSON. Expected keys:

- `Subscribers`: app user/share-list entries, with fields like `Email`, `Permissions`, `Version`, `Role`, `HasUsedApp`.
- `AllowListDomains`: domain allowlist entries.

Approved per-app removal:

```text
POST https://www.appsheet.com/manage/RemoveAppSubscriber
form fields:
  appId=<app_id>
  emailToDelete=<email>
headers:
  X-Requested-With: XMLHttpRequest
  Origin: https://www.appsheet.com
  Referer: https://www.appsheet.com/template/AppDef?appName=<app_name>
```

Verification is mandatory: reload `/api/loadUsers/<app_id>` and require the target email to be absent; also report before/after `Subscribers` counts. This endpoint removes the literal AppSheet app subscriber/share-list entry. It does **not** clear table-driven role/access fields in `HR_Employees` or `HR_Employees_AppSheet_Settings`; handle those separately with row API dry-run/approval.

Candidate per-app add/share endpoint discovered from the editor bundle but not yet verified in a successful live add flow:

```text
POST https://www.appsheet.com/manage/SubscribeEmailsWithPermissions
form fields observed:
  appId=<app_id>
  emails=<comma-separated emails>
  bodyTextPrefix=<optional invite/body text>
  sendEmail=<true|false>
  permissionForNewSubscribers=<permission value>
  roleForNewSubscribers=<User/Admin/etc.>
  versionForNewSubscribers=<optional required version>
  recaptchaResponse=<if required>
  userClass=User
  userAgent=<browser user agent>
```

Until a successful add is tested and read back, treat add/share as a separate approved operation: inspect current `/api/loadUsers`, prepare a dry-run payload, execute only with explicit Andy/admin approval, then verify the email appears with intended `Permissions`, `Role`, and `Version`.

## Removal capability distinction

- Row API can remove effective in-app/data-driven access by clearing table fields on `HR_Employees` and/or `HR_Employees_AppSheet_Settings` after dry-run and explicit approval.
- AppSheet team-admin API documented by Google is for team user account deletion / ownership transfer, not ordinary per-app share-list removal; treat it as destructive/permanent and do not use it for simple app offboarding unless specifically approved and scoped.
- Literal per-app invitation/share-list removal is supported via the verified `/manage/RemoveAppSubscriber` editor-session endpoint above, after explicit approval and readback verification.

## Output pattern

For offboarding candidates, report a small table:

- Remove from AppSheet access? (`Yes`, `Probably no AppSheet access`, `Needs live Users-pane check`)
- Employee name
- `PersonID`
- Employee ID
- BU / role if useful
- Separation Date
- Evidence: email/roles/views/settings row presence

End with whether changes were made. For inspection-only asks, explicitly say `No changes were made.`
