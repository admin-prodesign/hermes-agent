---
name: automation-source-key-integrity
description: "Diagnose and safely recover automations that fail closed on duplicate or missing stable keys in spreadsheets or source tables."
metadata:
  hermes:
---

# Automation Source-Key Integrity

## Overview

Use this skill when a poller, synchronizer, writer, or queue processor refuses to run because its source table contains duplicate, missing, malformed, or reused stable identifiers — or when an Admin card names a source-key watchdog cron failure. The goal is to repair source identity without merging valid business records, bypassing fail-closed guards, or replaying production work unsafely. Classify a Hermes engine-failure card separately from a designed invariant page before any row work.

For a concrete Project List recovery example, read `references/project-list-duplicate-id-recovery.md`.

## Detail
See `references/source-key-detail.md` (core rules, recovery, pitfalls, checklist).
