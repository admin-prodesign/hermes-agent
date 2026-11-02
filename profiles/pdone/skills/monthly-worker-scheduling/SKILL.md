---
name: monthly-worker-scheduling
description: "Run monthly worker scheduling and HR MAX export."
metadata:
  hermes:
---


# Monthly Worker Scheduling

## Overview
Compact router for Pro-Design monthly worker scheduling: rest requests, source corrections, solver runs, coverage risks, and HR MAX export. The full operational playbook is preserved in `references/complete-original-skill.md`.

## Scope Boundary
Use only for injection-molding monthly shift/leave assignment. Do not mix with production scheduling, payroll, discipline, evaluations, or unrelated HR records. Mold repair staff rest is `mold-repair-worker-scheduling`, not this solver and not workbook `10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE`.

## Load Detail When Needed
Before running the solver, reading/writing scheduling sheets, preparing HR MAX exports, or diagnosing timeout/writeback issues, load:

```text
skill_view(name="monthly-worker-scheduling", file_path="references/complete-original-skill.md")
```

Important references include `monthly-kickoff-automation.md`, `auto-run-when-consistency-green.md`, `dest-vs-source-roster-sync.md`, `dest-preassigned-days-before-solve.md`, `solver-runtime-capping.md`, `worker-scheduling-writeback-receipts-and-unrelated-sheet-incidents.md`, `source-stats-formula-spill-and-group-writeback.md`, `2026-07-operator-day-writeback-timeout.md`, `quick-schedule-marker-readback.md`, and month-specific notes.

## Non-Negotiables
Load `references/monthly-scheduling-non-negotiables.md` before solve, writeback, HR MAX export, or source maintenance.

# Monthly Worker Scheduling

## Overview
Compact router for Pro-Design monthly worker scheduling: rest requests, source corrections, solver runs, coverage risks, and HR MAX export. The full operational playbook is preserved in `references/complete-original-skill.md`.

## Scope Boundary
Use only for injection-molding monthly shift/leave assignment. Do not mix with production scheduling, payroll, discipline, evaluations, or unrelated HR records. Mold repair staff rest is `mold-repair-worker-scheduling`, not this solver and not workbook `10DU9Yro5tDacrjBlOfuGE9JCcYFkC7ribJKuaxnRWhE`.

## Load Detail When Needed
Before running the solver, reading/writing scheduling sheets, preparing HR MAX exports, or diagnosing timeout/writeback issues, load:

```text
skill_view(name="monthly-worker-scheduling", file_path="references/complete-original-skill.md")
```

Important references include `monthly-kickoff-automation.md`, `auto-run-when-consistency-green.md`, `dest-vs-source-roster-sync.md`, `dest-preassigned-days-before-solve.md`, `solver-runtime-capping.md`, `worker-scheduling-writeback-receipts-and-unrelated-sheet-incidents.md`, `source-stats-formula-spill-and-group-writeback.md`, `2026-07-operator-day-writeback-timeout.md`, `quick-schedule-marker-readback.md`, and month-specific notes.

## Verification Checklist
- [ ] Correct month/source workbook identified.
- [ ] `排班規則 Scheduling Rules` metadata/schema/readback verified; exactly one active/effective `manager_day` 課長 maps by stable WorkerID, and weekend coverage/exclusions are present in the preview receipt.
- [ ] Dest vs request-list roster sync completed: dest-only employed names were added to `申請日期-當月統計` `B:D`; source-only names have an include/exclude decision.
- [ ] Dest date-cell values and notes were read from `日`, `夜`, and `幹部`. Every required rest or work note is in `AP:AT` and read back. See `references/dest-preassigned-days-before-solve.md`.
- [ ] `AO1` is not `#REF!`. AO does not filter on column V or join column W. The status test is an array, not a first-cell `LEFT`. Formula ranges fit the live grid. Each qualifying raw `K:O` day is in that worker's AO list, including rows whose status starts with `- 未決定`. A first date inside the month was not treated as captured. A partial capture failed the whole run group. Write verification was not used as capture proof. Empty parsed lists were checked against raw dates. Excluded names and non-`-` status rows were listed. A header-only spill, a near-empty AO, or a mixed-month row that does not match blocked the solve. "Fully read" was not claimed while visual `申` marks were empty or the last solve used an older parse.
- [ ] Proposed AP:AT table rebuilt from current-month markers; unambiguous green auto-run applied and read back, or ambiguities stopped the run.
- [ ] On the green auto-run path, solve/writeback proceeded without waiting for Andy; non-green blockers were reported instead.
- [ ] Inputs/rest requests validated and coverage risks reported.
- [ ] If a background solve is still running at the end of the turn, a one-shot origin cron exists to report it. No verbal promise without that job.
- [ ] Solver/runtime limits selected intentionally.
- [ ] After a dest row delete, count-mirror pointers and stored write rows were rechecked against live names before resume.
- Any writeback/export has dry-run, live receipt, and readback verification. A group is written only when the write report status is `written`, `failed_updates` is 0, and verification `mismatched_actions` is 0. Do not treat verification `source_summary.write_enabled=false` as a failed write. That field is copied from the solve preview, which never enables write. That receipt does not prove request capture. Do not resume an output dir whose report has no `申` while raw qualifying dates exist for that group. Value verification with open format failures is not complete. Resume the same `output_dir` only after capture is confirmed. See `references/worker-scheduling-writeback-receipts-and-unrelated-sheet-incidents.md`.

## Wake-on-complete cron pattern
See `references/wake-on-complete-cron-pattern.md` (job `8d43c3eba364`).

