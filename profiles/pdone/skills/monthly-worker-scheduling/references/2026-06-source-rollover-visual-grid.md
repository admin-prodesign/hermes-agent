# 2026-06 source rollover visual-grid pitfall

During June worker scheduling, source/helper rollover repaired structured helper columns (`RequestedRestDays`, `ProtectedLeaveDays`) and protected leave handling, but `申請日期-當月統計!E:AH` ended up blank for nearly everyone except a small number of changed rows.

Durable lesson:
- `申請日期-當月統計!E:AH` is a required visual audit grid for worker-requested dates, not just cosmetic output.
- The grid should show `申` on dates requested by workers from canonical `原資料` rows.
- `喪`/protected leave should remain protected/non-rest and should get yellow fill like pre-requested `申`, but it must not cause ordinary requested-date markers to disappear.
- After any source rollover or helper-column repair, run a read-only preflight/preview and confirm that the number of visual `申` markers is plausible across all workers, not just one corrected employee.
- If most `E:AH` markers are blank while structured records still parse, stop further solve/writeback. A successful parse is not proof that requests were captured. `E:AI` only paints `申` from `AO`. If `AO1` is `#REF!`, the parser still renames that header and reads leftover typed cells. Repair the AO spill first, then compare raw target-month dates with AO before any solve. See `references/source-stats-formula-spill-and-group-writeback.md`.

Safe sequence for future repair:
1. Read `原資料` for the target scheduling month and build canonical requested-day sets per matched worker/request row.
2. Build a dry-run diff for `申請日期-當月統計!E:AH` only: intended `申` markers, cells to clear, and protected-leave exceptions.
3. Report candidate counts and sample rows before live write.
4. With approval, write the visual grid, then re-run preflight and solve preview before any schedule writeback.
5. Verify both structured helper fields and visual marker grid are aligned.