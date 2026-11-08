# AppSheet Editor Versioning for Pro-Design Apps

Use this reference before manually editing `Version` in an AppSheet app definition or when a user asks for a “major version”.

## Version scheme

Pro-Design AppSheet editor versions follow a date-based convention, not semantic versioning:

```text
YY.MMDDNN
```

- `YY` = two-digit UTC year.
- `MMDD` = UTC month/day.
- `NN` = same-day sequence.
- Major/manual milestone versions use `00`, e.g. `26.061800` for 2026-06-18.
- Minor/incremental same-day saves then continue as `01`, `02`, etc.

Do **not** invent semantic-major values such as `27.000001` for a major AppSheet change. A bad high major value can become hard to undo because AppSheet enforces monotonic version progression.

## Required workflow

1. Before saving any manual `Version` edit, read the live app with `/api/loadApp/<appId>` and inspect the existing `Version` / `StableVersion` pattern.
2. Compute the intended major version using UTC date:

   ```bash
   date -u +%y.%m%d00
   ```

3. If the current latest version is already above the intended date-based value, do **not** force a lower `Version`; AppSheet may reject it with a conflict. Report the situation and ask/decide on a recovery path before further saves.
4. When creating a major change with views/tables/actions, set the date-based major version on the same current payload that includes the intended object changes; avoid stacked asynchronous saves with different version values.
5. After any timeout, reload `/api/loadApp/<appId>` before retrying. A timed-out `/api/saveapp` can still commit and advance the version.

## Conflict signature

If AppSheet returns a message like:

```text
You are trying to save version 26.061801 of the app, but someone has already created version 27.000004.
Perhaps you have the app editor open in a different browser tab? Discard your changes and refresh the app editor.
```

then a higher version already exists. Treat the lower date-based correction as blocked unless an AppSheet-supported rollback/recovery path is explicitly chosen. Do not keep retrying the same lower version.

## Reporting

When reporting version work, include:

```text
Version:       <latest editor version>
StableVersion: <stable version>
IsValid:       <true/false>
IsRunnable:    <true/false>
```

Also state clearly whether stable promotion was performed or not.