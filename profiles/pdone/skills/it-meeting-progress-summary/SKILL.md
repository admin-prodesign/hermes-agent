---
name: it-meeting-progress-summary
description: "Prepare the 2nd or 4th Tuesday IT meeting thread summary from the pre-run packet."
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [pd-one, it, meeting, summary]
    related_skills: [it-meeting-briefing]
---

# IT meeting progress summary

This job writes the thread summary for the 13:20 post. It is not the 12:00 pack and not the Friday reminder. The 12:00 pack stays on skill `it-meeting-briefing`. Do not post, send, or edit Mattermost.

## Gate

Use Asia/Taipei. The pre-run script stdout is the only evidence. If that stdout is `not_due`, or today is not the month's 2nd or 4th Tuesday, do not write the pending file. Final response: `not_due`. If the stdout is JSON and `gate` is not `due:YYYY-MM-DD`, do not write the pending file. Final response: `blocked gather`.

## Packet

When the stdout is one JSON packet whose `gate` is `due:YYYY-MM-DD`:

- New tickets, case updates, open tickets, channel counts, channel excerpts, and document headers are already collected. Do not re-probe. Do not search rooms again. Do not open Drive or Docs.
- `Case` `Last Updated` is not activity. A nightly cache stamp is not a case update.
- Count `case_updates.timestamp_it_ticket` rows. `created_on` is only a column check. A zero there is an empty result for that column, not the case-update count. An error there is not the update count either.
- Channel `audit` values are lookback counts, not topics. Do not invent a topic from a count. Topics come only from `search.hits`. If `hit_cap` is true, say the search is incomplete.
- Document writes come only from `documents` header text and changelog entries. An empty folder-name search is not in the packet and is not proof of no change. If the rooms named a manual that is absent from `documents`, say it was not confirmed.
- Leave out personnel, performance, payroll, finance, account-reset steps, MAC addresses, and internal IPs. Do not include server paths, tokens, or service-account addresses. General IT must be able to forward the text.
- Say the window start and end from the packet.

## Message

Traditional Chinese first, then English, with the same facts, the same order, and the same counts. Put a line that contains only `---` between the two languages.

The first line must be exactly `資訊會議進度摘要（YYYY-MM-DD）`.
The second line must be exactly `IT meeting progress summary (YYYY-MM-DD)`.
Use the packet `meeting_date`. Keep the message between 200 and 12000 characters.

Use a Markdown table for every row list: new tickets, case updates, channel topics, document writes, older open tickets, left-out items, and sources. Put a blank line immediately before each table header and a blank line immediately after the last row. Do not place a heading, sentence, or bullet on the same line as a table. Do not put a pipe character inside a cell. Keep each table under 3500 characters. If a table must split, repeat the header and keep the blank lines. One blank-line example is in `references/table-shape.md`.

If `truncated` is true, say the table is partial. Do not state a total the packet does not give.

Sections to cover, in this order, in both languages: new IT tickets, real case updates, channel work, verified document writes, still-open tickets with no new update, items left out, sources checked, and what was not a full transcript.

## File

Atomically write only this file:

`/home/prodesign/.hermes/profiles/pdone/state/it-meeting-progress-summary/pending.json`

`write_file` on that path is the atomic replace. Do not write any other path.

Schema: `{"schema":"pd-one.it-meeting-progress-summary.v1","meeting_date":"YYYY-MM-DD","status":"ready","generated_at":"ISO-8601 Asia/Taipei","message":"..."}`

Do not set `status` to `ready` unless both headings are present, the counts match the body, and every row list is a table with blank lines around it. Do not write the file when the packet is `not_due`, or when a required section `error` means those checks cannot pass. Final response is then `blocked <section>`.

When the file is ready, the final response is one line: `ready YYYY-MM-DD`. Do not paste the summary. A later script posts the file at 13:20. This job does not.
