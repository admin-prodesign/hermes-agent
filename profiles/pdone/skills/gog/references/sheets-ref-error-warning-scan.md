# Google Sheets `#REF!` warning scan (suggest-only)

Use when Andy/admin wants a deterministic warning before any auto-add-rows / paste-clear repair.

## Job

- Script: `/home/prodesign/.hermes/profiles/pdone/scripts/sheets_ref_error_warning.py`
- Wrapper: `/home/prodesign/.hermes/profiles/pdone/scripts/sheets_ref_error_warning.sh`
- Registry: `/home/prodesign/.hermes/profiles/pdone/config/sheets_ref_warning_targets.json`
- Receipt: `/home/prodesign/.hermes/profiles/pdone/cron/output/sheets_ref_warning_latest.json`
- Mode: **warn only**. Never writes sheet cells.

## Behavior

- Empty stdout when healthy or when the finding fingerprint is unchanged.
- New/changed `#REF!` findings print a bilingual PD One Admin notice and must mention `@andy.lin` once.
- Classifies: `need_more_columns` / `need_more_rows` / `paste_block` / `dead_range` / `formula_ref` / `array_spill`.
- Collapses copied-down twins and ignores empty-formula spill cells.
- Does **not** auto-insert or clear paste. Suggestions stay in the notice until Andy confirms they are repeatable.

## History caveat

`--history` can walk Drive revisions for formulas whose **formula text** contains `#REF!`. The unattended cron does **not** pass `--history` (token export/xlsx revision download is too slow/fragile). The notice tells Andy to open Google Sheets version history for `formula_ref` / `dead_range` cells.

## Cron

Daily `0 1 * * *` UTC (09:00 TPE), `no_agent`, deliver `mattermost:5gmqtwqf7bde3cyihas79xi8ie`.
