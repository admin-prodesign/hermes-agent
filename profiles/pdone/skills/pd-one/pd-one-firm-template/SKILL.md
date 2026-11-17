---
name: pd-one-firm-template
description: "Use when finding or changing the Pro-Design PPT golden."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pptx, template, charts, pro-design]
    related_skills: [pd-one-pptx-template-migration, company-github-cursor, pptx-author]
---

# Pro-Design PPT golden (firm template)

Mutations to the company meeting/report template: new layouts, data-chart templates, master-safe extras. Not user-deck migration (that remains `pd-one-pptx-template-migration`) and not one-off employee decks (`pptx-author`).

## When to Use

- Andy/admin asks to add or restyle **chart templates** or extra conceptual layouts on the company PowerPoint golden.
- Chart types such as bar, stacked bar, line, scatter, or before/after comparison, using company colors/fonts.
- Do **not** use for migrating an attached employee deck onto the template (`pd-one-pptx-template-migration`) or for a one-off report deck (`pptx-author`).
- An employee ask to find the company slide template, or the new KPI briefing template, is a lookup. A screenshot of the Town Square pin plus a request for that file is the same lookup. Do not treat it as a golden mutation.

Product golden: GitHub `admin-prodesign/pro-design-ppt-template`. PD One sealed copy: profile path `.../pdone/templates/` file `firm-template.pptx`. Intent names: `LAYOUTS.md` next to that sealed file. This skill directory also tracks those two current files (`LAYOUTS.md`, `firm-template.pptx`) so the names and the package are in git. Runtime loads still use the sealed profile path.

## Always-on

- **Preview before save.** When asked to add charts or layouts, render and send a visual preview of **each** chart, then stop. Do not write the golden or sealed `firm-template.pptx` until explicit save approval.
- Extra layouts live on the **two existing masters** only (Light white / Dark navy). Prefer Light unless dark/navy is asked. Never add a master.
- Do not invent KPIs. Template/sample series are labeled SAMPLE / 示意.
- Dark-master native charts must restyle legend/axis text to paper or muted-light. Navy or `#5B6574` on the navy canvas fails contrast.
- Layout SOURCE/FOOTNOTE placeholders stay empty. SAMPLE source is gallery-slide-only. User decks use `save_presentation`, which strips empty or SAMPLE SOURCE/FOOTNOTE shapes — never leave those labels with no citation.
- Do not invent accent bars or non-rect `p:ph`. Conceptual decorations stay ordinary shapes.
- `從到 From-to` is two conceptual cards plus an arrow — not a before/after **data** chart. `瀑布 Waterfall` is a shape stack, not an Office chart.
- After approval, add the same layout on **both** masters. Default data charts to **native PowerPoint charts** so employees can edit data. Ship **only the types that were in the approved preview set** (a sql-srv recommendation such as combo stays out until it had its own preview). Andy asking to create a PR and integrate **is** save approval: implement in `admin-prodesign/pro-design-ppt-template` and open an andy-auto PR (see `company-github-cursor`). Merge, Nemo `firm-template.pptx`, and the Town Square pin are **three later gates**. Do not copy builder zip onto Nemo or into the pin until the rebuilt PPTX/POTX have been COM-sealed (desktop PowerPoint Open, Repair if prompted, keep those bytes).
- Delivered decks still use `pd_one_pptx_ops.load_firm_presentation()` / `save_presentation()` (header/footer clone, sanitize, gate).
- Type size: titles at least 28 pt; body at least 14 pt; 10 pt only for footnotes and sources. Shrink or split text that would overflow, and keep content inside the layout safe area.
- Fonts on nemo: renders approximate Aptos and Microsoft JhengHei via host fontconfig aliases (JhengHei→Noto Sans CJK TC, Aptos→close sans) handled by PD Neo Watch on the host. Do not add host fontconfig files.

Chart tokens, series colors, PNG preview recipe, live sql-srv usage scan, and the before/after pairing rule: `references/chart-layouts.md`.

## Employee template lookup

When an employee says a department gave them the company PPT template, accept that as a source claim. Do not answer that their notes fail to prove a company source. Do not say their file is the current sealed golden, and do not say it is a different file, until you compare the two masters. A company mark and the footer line `Pro-Design Group · 良器集團` are consistent with a company-branded template. They are not identity.

When the ask is where the template is, a request for that file, or a screenshot of the Town Square pin, including a KPI briefing template:

1. Do not write `firm-template.pptx`, open a PR, or send the sealed profile path as the download. `MEDIA:` of that path is still that download: the attachment name becomes `firm-template.pptx`, and the employee POTX is missing.
2. Read `state/ppt-template-town-square/state.json` for version and the file-reply post id. Member-search that Town Square channel for `POTX`. The file-reply post lists both employee filenames; the pin root has no files. Give that reply permalink, the version, and both names (PPTX to open, POTX to save as a template).
3. A hash match is not a substitute delivery. `pd_one_pptx_from_template` with `action=inspect` and `mode=clone` can confirm the sealed PPTX matches `pptx_sha256`. Default `mode=apply` fails because it requires `source_path`. Do not stage a clone for the employee: clone rewrites content types and is no longer the published file.
4. Name the KPI layouts from sibling `LAYOUTS.md`: `指標 KPI`, `計分表 Scorecard`, and the data-chart layouts. Light master unless dark is asked.
5. Excel KPI workbooks, including `管理部\三廠KPI比較表`, are scorecards, not the slide template. Say that split. Do not open bonus or payroll workbooks to answer a template-location ask.

## Procedure

1. Confirm the ask is a golden mutation (new chart/layout family), not a lookup and not a one-off deck.
2. If the user wants types that match live company decks, scan sql-srv KPI / 經管會 / 產銷彙整 PPTX **before** previewing (recipe in `references/chart-layouts.md`). Do not invent usage from memory.
3. Preview: one PNG per type, company tokens, bilingual titles, SAMPLE chip, **left chart / right comments / bottom source**, vision-QA CJK and clipping, `MEDIA:` each file. Keep that chrome even when live 經管會 slides are full-bleed Excel paste — the golden is an upgrade, not a photocopy.
4. State that the golden is unchanged and wait for save approval.
5. On approval (including create-a-PR-and-integrate): both masters, native charts unless PNG/shape-locked was requested, only previewed types, update repo `docs/LAYOUTS.md` keyword rows, rebuild `.pptx`/`.potx` from `tools/build_employee_template.py`, open a **new** branch from `main` (do not dump onto an unrelated open PR). Builder recipe: `references/chart-layouts.md`.
6. After merge (or an explicit merge + seal + pin ask): COM-seal the **merged** PPTX/POTX first. If hashes change, commit those bytes on `main`. Tag a GitHub **release** (Town Square `sync_ppt_template_town_square.py --sync` follows `releases/latest`, not every main commit). Only then copy the sealed PPTX onto Nemo `templates/firm-template.pptx` (backup first), refresh sibling `LAYOUTS.md`, and replace the pin file-reply. If native Open fails on both the candidate and the current sealed golden in the same lane, stop as INCONCLUSIVE environment — do not ship builder zip as sealed.

## Pitfalls

- Sending or `MEDIA:`-attaching the sealed `firm-template.pptx` when an employee asked where the template is or asked for that file — they cannot open that path, the upload name is not the published name, and the POTX is omitted. The Town Square file-reply is the employee file.
- Writing the sealed template in the preview turn — the ask named preview-before-save; a golden write cannot be undone by a later “looks good.”
- Using `從到 From-to` for paired before/after bars — employees would get text cards instead of a data chart.
- Horizontal before/after with `invert_yaxis()`: smaller y is visual top; put Before (navy) at the smaller y or the pair reads After then Before.
- Copying live KPI numbers, customer names, or money from sql-srv decks into previews or the Mattermost reply — report chart **types** and layout only; sample series stay SAMPLE / 示意.
- Using `pd_one_smb_unc_content_search` to find PPTX — that wrapper only scans docx/xlsx/txt/csv/xml. Recurse named roots with the sql-srv read helper, then zip-inspect / visual-QA.
- Shipping combo (or any extra type) because sql-srv uses it — the save set is the approved preview PNGs; recommend extras, do not add them unpreviewed.
- Folding chart layouts into an unrelated open golden PR — branch from current `main` so From-to/Cycle floors and COM-seal history stay intact.
- Leaving `validate_pptx.LAYOUT_FLOORS` dark From-to/Cycle paths at the old 23-layout offsets — those IDs are `n_layouts + light_index`; adding layouts shifts **only** the dark copies.
- Wiring Nemo `firm-template.pptx` or replacing Town Square attachments from the builder zip — PowerPoint COM Repair is still required; the product PR is the golden, the sealed copy waits. A merge is not a release: do not `gh release create` or `--sync --live` until sealed bytes exist, because the pin poller treats a new tag as employee-facing.
- Treating native Open failure on the new golden as artifact Repair — if the **current** sealed golden fails Open the same way in that lane, the verdict is INCONCLUSIVE environment; leave Nemo and the pin on the last sealed hash.
