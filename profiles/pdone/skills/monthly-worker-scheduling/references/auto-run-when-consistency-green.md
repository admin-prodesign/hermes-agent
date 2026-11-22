# Auto-run when consistency checks are green

Andy standing instruction (2026-08-24), Injection Molding monthly worker-scheduling playbook:

When the playbook is run, assume all rest-day requests have already been submitted. Do not wait for more Google Forms / `原資料` submissions, and do not ask Anna to confirm that intake is complete.

## Required consistency checks before any auto-fill or auto-solve

Treat the run as **green** only when all of the following are source-backed:

1. Target month and following-month required rest counts plus target-month hours are already recorded from in-scope evidence (kickoff thread, same-cycle management thread, Tracker, or local receipt). Do not re-ask Anna for numbers that already exist.
2. Live `申請日期-當月統計` labels still match `A3=Month`, `A5=Shift`, `A9=Required Rest Days`.
3. After dry-run `source_setup`, the intended live controls are `A2=target year`, `A4=target month`, `A10=target required rest`. A stale prior month is not green.
4. Active `原資料` request dates used for the month belong to the target month, or mixed-month rows are explicitly classified. Run the overwrite scan; any unresolved replacement/duplicate request is not green.
5. Dest vs request-list roster sync (`references/dest-vs-source-roster-sync.md`) has run: every named dest employee with a real class is on `申請日期-當月統計` `B:D`, dest-only employed operators were auto-added, and only source-only names still need include/exclude. Visual-only `幹部` are not auto-promoted into solver groups.
6. Destination `V` / `喪` / `特` / `訓` notes that would change AP:AT meaning are readable and unambiguous. Unreadable notes, vacation-vs-hard-rest doubt, or manager-judgment ambiguity is not green.
7. `排班規則 Scheduling Rules` has exactly one active effective `manager_day` 課長 mapping.
8. Following-month rest count is present. The lookahead month is never a write target.

## What to fill automatically when green

Without waiting for Andy’s go-ahead:

1. Live `source_setup` for the target year/month/required-rest controls, then read back `A2:A10`.
2. Write target-month destination hours cells only (for example September `160H`). Do not write the following-month hours onto target-month tabs.
3. Rebuild `申請日期-當月統計!AP:AT` from the default current-month marker map: `V` → `AP` unless a readable note says vacation/flex (`AR`); `喪` → `AQ`; `特` → `AR`; `訓` → `AT`. Clear stale prior-month AP/AQ/AR/AT values that lack current-month evidence. Do not infer `AS` from blanks.
4. Bounded `sync_source_rollover` plus `E:AI` visual-grid / preflight checks.
5. Independent `solve_preview` for `day`, `night`, `manager_day`, and `manager_night` at the normal 180s cap, including the following-month feasibility horizon.
6. If a group is `FEASIBLE` or `OPTIMAL`, write that group with `write_generated_schedule_from_report`. Resume `partial` on the same `output_dir`. Never write `UNKNOWN` or `INFEASIBLE`. Never write the following-month witness.

Post a compact bilingual receipt after each material step. Do not pause for a go-ahead when the run is still green.

## What still stops the auto-run

Stop and report the exact blocker when the run is not green, or when:

- a source-only roster include/exclude decision is required (dest-only employed names are auto-added to `申請日期-當月統計` `B:D`);
- raw-request history would be corrected;
- AP:AT meaning is ambiguous;
- solver status is `UNKNOWN` / `INFEASIBLE`;
- HR MAX export/upload, pre-print `未`→`特`, or `原資料!AD` closeout is reached.

Those later closeout steps are not part of the automatic generated-schedule run.
