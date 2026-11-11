---
name: it-meeting-briefing
description: "Use when the semi-monthly IT meeting brief is due."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, it, meeting, appsheet, mattermost]
    related_skills: [it-documentation-stewardship, mattermost-channel-history-reports, appsheet-record-ops, pd-one-infographic-generator]
---

# IT meeting briefing

## When to Use

- The 12:00 pack on a 2nd or 4th Tuesday IT meeting day.
- A test run of that pack before the meeting.
- A request to summarize IT tickets, case updates, IT channels, and Drive/Docs changes since the last IT meeting.

The Friday reminder in `scripts/it_meeting_reminder.py` is a different job. Do not treat that reminder as this brief.

## T-10 reminder-thread summary

This delivery is not the 12:00 pack and not the Friday reminder.

- On a 2nd or 4th Tuesday, post one bilingual progress summary into the latest IT meeting reminder root at 13:20 Asia/Taipei.
- Write the summary to `state/it-meeting-progress-summary/pending.json` before 13:20. The post script is the only sender. Do not post early and do not create a new channel root.
- The post script retries until 13:28, then fails closed. A repeated non-meeting gate token must not wake a new summary.
- Write every row list as a Markdown table. Put a blank line immediately before the header and immediately after the last row. A table flush against a heading or sentence stays literal pipes in Mattermost.

## Always-on

- Meeting time is 13:30 Taipei on the month's 2nd and 4th Tuesday. The brief is due at 12:00 Taipei that same day.
- Window starts after the previous meeting (prior 2nd or 4th Tuesday, 13:30 Taipei) and ends at the brief moment.
- Read all three rooms, not only the origin room:
  - IT `jp47xmyu8prytmqrhimaw9hy7e`
  - IT Work `itbmu3ycsjb3tfuscmw69b9iny`
  - AI Discussion and IT Requests `imj7bt6w4tdk5rsbttiga44agc`
- Leave out personnel, performance, payroll, finance, account-reset steps, MAC addresses, and internal IPs. General IT must be able to forward the pack.
- Channel reply, infographic, and detailed report are all bilingual. Put Traditional Chinese first, then English, with the same facts, the same order, and the same counts. English headings on a Chinese body are not enough. A four-number card is not enough.
- The infographic is the one-page executive summary of the deck. A reader must see the window, the new tickets and their status, the real case-update count, the main channel decisions, the verified manual writes, and what was left out, without opening the deck.
- The sealed company template is `/home/prodesign/.hermes/profiles/pdone/templates/firm-template.pptx`. Confirm it with a file stat or with `pd_one_pptx_from_template` inspect. Do not use `pd_one_pptx_inspect` or `pd_one_local_file_search` on `templates/`. Those allowlists exclude that folder. A refusal is not "file missing" and it is not "every reader refuses the file."
- `pd_one_pptx_from_template` can open that folder. Clone copies the sealed package. Apply restyles an existing deck. Neither mode writes new slides from this brief.
- A company-template deck is for any active profiled employee, not Andy only. Do not refuse the fill because the room is not Admin. Do not ask the room to approve a shell. The fill must be a typed tool that calls `load_firm_presentation()` and `save_presentation()` with no shell. Until that tool exists, say the writer is missing. Do not say the file is invisible, and do not send the requester to Admin.
- Create the 12:00 job from the requesting admin sender. Do not require the Admin channel for that cron.
- Deliver a summary infographic and a detailed PDF. Do not call a paragraph PDF a company-template deck.

## Steps

1. Confirm the window from the meeting cadence. A test run uses the same window as the next meeting day.
2. Probe deployed AppSheet `Case` with `Type = "IT Ticket"` and `Created On` on or after the window start. Those rows are new tickets.
3. Probe `Case_Updates` with `Created On` on or after the window start. Keep only updates whose parent `Case` is an IT Ticket. A zero result is a real empty set when the same date form works on `Case`.
4. Do not treat `Case[Last Updated]` as activity. A nightly cache stamp can touch old tickets with no new `Case_Updates` row and with a `Latest_CaseUpdateID` before the window.
5. Count active posts with channel post audit. Then member-search each room with distinctive terms, not one broad word that hits the cap. Group by `originalPostId`. Discard the current request and bot progress posts. State the cap when search is incomplete.
6. For Drive changes, do not stop at a parent-folder name search. That search is one folder, one name fragment, and one MIME type. Confirm canonical writes from the live Doc changelog and header date. Check the IT manual and any other manual the three rooms asked PD One to edit.
7. Split the pack into: new tickets, real case updates, channel work, verified Drive/Docs writes, still-open tickets with no new update, and items left out.
8. Build the infographic as the one-page executive summary. Every label is a Chinese line and an English line. Read every label before send. Counts must match the report. No MAC, IP, personnel, or finance on the card. Do not let a date badge cover a sentence.
9. Build the detailed report with the same bilingual pairs, and build the company-template deck with the typed writer. Any active profiled employee may request that deck. Do not call a paragraph PDF a company-template deck. If the typed writer is missing, say that. Do not send the requester to Admin. Attach the file with `MEDIA:/absolute/path`. A path in prose is not delivery.
10. List sources checked. Say what was not a full transcript and what Drive search did not cover.

## Pitfalls

- A `Last Updated` filter is a cache refresh, not proof of work since the last meeting.
- An empty direct-child Drive search is not proof that no Sheet or Doc changed. Subfolders and other department files are outside that query.
- Keyword search of a busy room stops at the hit cap. One query dominated by one thread is not the room summary.
- Channel post audit returns counts only. Do not invent thread topics from the count.
- Do not tell the requester the company PPTX cannot be seen. A `pd_one_pptx_inspect` or local-file-search refusal of `templates/` is an allowlist miss, not a missing file. The missing piece is a typed fill that calls `load_firm_presentation()` without a shell.
