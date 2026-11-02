# PD One Audio Transcription + Company Context Workflow

Use this reference when Andy/admin asks whether PD One can process employee voice notes, meeting recordings, customer visit audio, production/mold discussions, or similar uploaded audio files.

## Core value over generic transcription

Do not stop at a plain transcript. PD One's advantage is the post-transcription grounding pass:

1. Transcribe the audio with timestamps where available.
2. Extract candidate entities: customer names, product names, mold/tool names, project codes, machines, departments, people, dates, issues, quantities, and deadlines.
3. Compare ambiguous phrases against permission-allowed Pro-Design context such as glossary entries, company wiki, Drive/Sheets/Docs references, AppSheet records, scheduling/repair sheets, and prior approved operational summaries.
4. Normalize terminology and bilingual names, while marking uncertain matches as `possible` rather than silently guessing.
5. Produce the requested operational output: meeting summary, customer visit report, issue/incident report, SOP draft, action list, or Mattermost-ready update.
6. Separate approved facts from inferred context and unresolved questions.
7. If source-system writeback, announcements, Drive sharing/moves, or external sends are requested, summarize first and wait for explicit approval unless a pre-approved scoped grant applies.

## Recommended report shape

- Source/audio status: filename or attachment receipt if available, duration, language(s), audio quality caveats.
- Recognized company entities:
  - Customers
  - Products
  - Molds/tools
  - Departments/people
  - Records or documents referenced
- Summary
- Decisions made
- Action items: owner, task, deadline, source confidence.
- Open questions / unclear audio
- Suggested follow-up records or messages requiring approval

## Entity-confidence rules

- `confirmed`: directly spoken and matched to an allowed company source or exact glossary/record entry.
- `likely`: audio is ambiguous but there is a strong contextual match; show why.
- `possible`: weak match; include as a question, not a fact.
- `unknown`: do not invent customer/product/mold names.

## Pitfalls

- Attachment ingress can fail or surface the wrong cached audio. Verify the actual media file/receipt before claiming results. If the only available audio is unrelated, say so and ask for resend/upload rather than producing a fake company-context report.
- Generic ASR often mangles customer/product/mold names. Treat raw transcript terms as candidates and run a company-context normalization pass before the final summary.
- Do not disclose unrelated internal records while resolving names. Use only sources within the requester's scope and provide the minimum necessary grounding.
- For Mattermost shared channels, keep replies bilingual English + Traditional Chinese per PD One policy unless the surface/context is exempt.
