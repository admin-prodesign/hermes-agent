---
name: gog
description: "Operate PD One Google Sheets with safe writes."
metadata:
  hermes:
---
# gog

PD One Google Workspace operations via Gog and typed `pdone_safe_ops` MCP tools.

## When to load detail
Use `skill_view(name="gog", file_path="references/operational-rules.md")` before Sheets/Docs writes, cron credential repair, Apps Script patches, reminder automation claims, note overlays, or grid-trim completion gates.

## Quick routing

| Topic | Reference |
| --- | --- |
| Employee-lane MCP writes vs terminal | `references/operational-rules.md` § Employee-lane Sheets writes |
| Naming, headers, protections, reorder repair | same + `references/company-sheet-naming.md` and linked refs therein |
| Cron / isolated `HOME` / OAuth | `references/pd-one-isolated-profile-gog-credentials.md`, `references/pd-one-gog-oauth-vnc-handoff.md` |
| Reminder automation verification | `references/sheets-reminder-automation-verification.md` |
| Safe bounded writes without execute-code noise | `references/safe-sheets-ops-no-approval-noise.md` |
| Apps Script bound updates | `references/appscript-update-content.md` |
| `.xlsm` vs native Sheets | `references/office-xlsm-to-native-sheets-repair.md` |

