---
name: mattermost-playbooks
description: Post bilingual onboarding notes from safe HR fields only.
version: 1.0.0
author: Andy, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Mattermost, Onboarding, HR]
    category: productivity
---

# Mattermost Playbooks

Post a Mattermost onboarding thread from the safe employee columns only. Private columns stay out of mixed rooms. This skill does not grant access to withheld columns.

## When to Use

- A new employee record was confirmed and the room needs an onboarding thread.
- The reply must be bilingual and limited to the safe columns.

## Prerequisites

- Mattermost delivery is already connected.
- Use `read_file` on `references/employee-onboarding-thread-start.md` before drafting.

## How to Run

1. `read_file` the onboarding reference.
2. Fill its output template from the safe probe columns.
3. Send that text as the thread. Do not append extra columns.

## Quick Reference

The reference file is the output contract. Copy it. Do not turn it back into a loose field list.

## Procedure

1. Confirm the record exists.
2. Read the reference template with `read_file`.
3. Fill every placeholder you actually have. Leave unknown placeholders blank.
4. Post the English block and the Traditional Chinese block with the same facts.

## Pitfalls

- Do not paste a raw probe payload into the channel.
- Do not invent values for blank placeholders.
- A mixed room cannot receive withheld columns. The send path replaces the whole message when it would.

## Verification

- The posted thread matches the template sections and adds no extra facts.
- Both languages contain the same filled placeholders.
