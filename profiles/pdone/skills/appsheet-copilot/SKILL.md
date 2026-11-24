---
name: appsheet-copilot
description: "Build, debug, and optimize AppSheet apps."
metadata:
  hermes:
---
# AppSheet Copilot

## Overview
Compact router for AppSheet design, debugging, live-data pulls, and Pro-Design operations. Detailed procedures live under `references/` (start with `references/complete-original-skill.md`).

## Load Detail When Needed
Before exact API commands, editor writes, bots, security filters, exports, incident triage, or live side effects:

```text
skill_view(name="appsheet-copilot", file_path="references/complete-original-skill.md")
```

Use narrower references first when the task clearly matches (performance steward, ActivityLog cache rollouts, definition sync, data pulls, editor pitfalls). Index: `references/routing-rules-compact-index.md` and the topic files it points to.

## Routing Rules
Load `references/routing-rules-compact-index.md` before schema-sensitive advice, editor writes, performance work, offboarding, or live side effects. Natural-language ActivityLog/Case record ops: load `appsheet-record-ops` first.

## Output Shape
For concrete advice, lead with the drop-in expression/config, then placement, brief rationale, test cases, and assumptions. For debugging, give symptom, likely root cause, fix, verification, and one hardening step.

## Prompt-Footprint Policy
Patch this stub only for routing-critical rules. Put long examples, command sequences, incident signatures, and domain references under `references/`.
