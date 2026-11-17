---
name: office-artifact-release-review
description: "Independently review generated or compiled Office artifacts for release blockers, determinism, package safety, provenance, and qualification gates."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [office, xlsx, ooxml, artifact-review, release-review, determinism, provenance, qa]
    related_skills: [visual-office-qa, xlsx, automation-reliability]
---

# Office Artifact Release Review

## Overview

A class-level review method for generated, edited, migrated, or compiled Office artifacts—especially XLSX/OOXML packages—when the user asks for an independent PASS/FAIL release verdict. The review covers both implementation correctness and the boundary between code readiness and production activation. It is not a substitute for native Office render certification, delivery readback, or operational deployment receipts.

## When to Use

- Reviewing an XLSX compiler or Office-document generator after remediation.
- Checking a claim of byte determinism, reproducibility, or stable artifact hashes.
- Auditing source/approval/provenance bindings and protected signature regions.
- Reviewing fail-closed native-Office qualification or signed render receipts.
- Separating stale fixtures, cached receipts, and helper-contract failures from current-source defects.
- Issuing an independent release PASS/FAIL with Critical, Important, and Minor findings.

## Required Review Sequence

1. **Freeze the approval set.** Identify the implementation, directly relevant tests, governing specification/runbook, and claimed artifacts. Prefer commit IDs or per-file SHA-256 hashes; if the permitted read-only surface cannot provide hashes, state the path/size/line-count anchor and limitation rather than inventing a revision ID.
2. **Map verification side effects.** Confirm the test harness uses temporary outputs and cannot write operational state, approval ledgers, queues, source systems, or delivery channels. A test that uses a fake API client may still write through real log/state paths.
3. **Inspect the change at both semantic layers.** For an XLSX compiler, review workbook mutations separately from ZIP-package serialization. Do not treat byte equality alone as proof of semantic correctness.
4. **Check determinism.** Require fixed workbook core properties and normalized ZIP entry order/metadata (timestamps, comments, extras, permissions, compression settings). Do not assume setting `Workbook.properties.modified` before save is sufficient: some writers, including openpyxl, can replace serialized `docProps/core.xml` modification time during `save()`. Inspect the actual serialized core part after save. If the compiler canonicalizes it, require exactly one expected `created` and `modified` element and fail closed on missing/duplicate/malformed values. Preserve every other OOXML part name/byte unless the normalization is explicitly reviewed, then reopen the generated package and verify its structure. The byte-determinism regression must cross a wall-clock boundary (or inject two different clocks), not merely run twice within the same second.
5. **Check package safety before unbounded parsing.** Require a bounded central-directory pre-scan before `ZipFile.infolist()` or equivalent allocation. Enforce bounded entry count, per-entry and aggregate expanded sizes, compression-ratio limits, duplicate/case-collision/path checks, required OOXML parts, macro/external-link rejection, XML DTD/entity rejection, and CRC/readback validation.
6. **Check semantic invariants.** Reopen the output and verify authorized signature cells, forbidden/Finance regions, formulas and links, merges, dimensions, print setup, non-target logical state, output byte size, and output SHA-256. Verify source-file hash, route, approval evidence, and receipt digests bind to the same workflow.
7. **Check qualification and trust.** Production qualification must be cryptographically bound to the exact artifact/template hash and include renderer identity, registered Office environment, certifier identity, render/golden hashes, certification time, and page count. An empty or unregistered production trust store must fail closed. Treat explicit unqualified-template switches as test-only and require a downstream production fence that rejects their outputs.
8. **Run independent checks.** Rerun the fixed component compile/lint command and targeted tests. Treat controller reports, stale fixtures, and cached receipts as leads only; compare schema/generator version and required fields before assigning a failure to current code.
9. **Classify the verdict.** Report Critical, Important, and Minor findings separately, including exact evidence and limitations. For a user-facing PASS/FAIL request, PASS means the reviewed code has no Critical or Important defect; it does not mean production activation is GO when external native-Office QA or deployment gates are still pending.
10. **Re-hash/re-read before finalizing.** Confirm the reviewed implementation and tests did not change during verification. Disclose any verification-created artifact or operational-state mutation as a review-isolation defect.

## Independent Re-review Pattern for Deterministic XLSX Compilers

When reviewing a corrected determinism fix, use two independent fixed checks rather than relying on a prior report:

1. Run the registered compiler unit/compile check against the frozen implementation and directly relevant tests.
2. Run the registered XLSX compiler smoke path in its isolated temporary workdir. Treat a successful smoke receipt as evidence for the complete path only when the wrapper performs ZIP validation and workbook readback; do not treat a cached artifact or a path from a cleaned temporary workdir as current evidence.
3. Inspect the changed serialization path at both points: freeze writer-owned core properties before `openpyxl` save, then normalize `docProps/core.xml` after save and before package validation. Require deterministic ZIP ordering, timestamps, compression, flags, attributes, comments, and extras.
4. For a core-property normalizer, verify the exact-one guard independently in source and tests: missing, duplicate, self-closing, or structurally non-matching `created`/`modified` elements must raise rather than silently produce a receipt. Distinguish this structural guard from lexical timestamp or namespace validation; if the latter is part of the acceptance criterion, record the missing coverage as a finding instead of claiming it was exercised.
5. Confirm the compiler's order is: normalize → bounded OOXML validation/CRC readback → workbook reopen/semantic readback → output hash/receipt. A successful unit test alone does not prove this orchestration order.
6. Report the result as two boundaries: **compiler code PASS/FAIL** and **production GO/NO-GO**. Native Excel qualification, production trust binding, delivery readback, and deployment gates can keep production NO-GO without invalidating a clean compiler code review.

## Current-Form and Renderer-Change Discipline

When the workflow owner limits evidence to a recent operating window, convert that request into explicit dates and treat older forms as superseded audit evidence only. Do not infer current fields, routes, signatures, stamps, or coordinates from older revisions merely because they are available. Require source-backed use dates; filename dates and archive timestamps alone may be insufficient. If authorized searches find no eligible form, request a current-thread upload or another approved source instead of silently widening the window.

When the owner changes the renderer—for example, from Microsoft Excel/COM to local LibreOffice Calc—treat it as a qualification-contract migration. Verify the target document-class component with a real fixture, keep the prior fence fail closed until the new contract is implemented, bind receipts to the exact renderer environment and artifact hashes, then rerun all affected tests and independent review. A code-review PASS for the old renderer contract does not transfer to the new one.

Split pilot readiness into two boundaries:

- workflow-only testing may begin after an eligible current form is frozen, but must not claim qualification or automatically deliver the final Office artifact;
- end-to-end delivery additionally requires renderer qualification, full visual QA, signed/hash-bound receipt verification, configuration readback, and explicit authorization for external posts/uploads.

See `references/renderer-migration-and-current-form-evidence.md` for the detailed evidence and migration checklist.

## Common Pitfalls

- Calling a stale smoke-fixture contract failure a compiler regression without inspecting the current required receipt schema.
- Treating a pre-remediation output or cached receipt as evidence for the remediated source.
- Accepting a manifest boolean as native-Office qualification without re-verifying the signed receipt and exact hash.
- Proving reproducibility only through logical workbook hashes while leaving ZIP timestamps/core properties nondeterministic.
- Setting in-memory core properties before save but never checking the serialized `docProps/core.xml`; the writer may overwrite `modified` with wall-clock time during serialization.
- Running two determinism compilations so quickly that both land in the same clock second, allowing a time-dependent defect to pass intermittently.
- Canonicalizing core XML with a permissive replacement that silently accepts missing or duplicate timestamp elements instead of failing closed.
- Running a native-Office render check against a different template/output hash than the one under review.
- Calling a code review PASS a production GO when native Excel/COM render, historical mapping, delivery readback, or scheduler receipts are absent.
- Treating a source-XLS visual PASS, `finance_blank=true`, or an unqualified compile receipt as proof that a migrated/compiled XLSX prints correctly. Re-render the exact XLSX and compare page count, paper size, and CJK glyphs to the source.

## Verdict Template

- **Verdict:** PASS or FAIL; state whether this is code review only or overall production release.
- **Revision anchor:** commit/hash, or explicit path/size/line-count limitation.
- **Checks run:** exact command/tool receipt and result.
- **Critical:** none or listed with evidence.
- **Important:** none or listed with evidence.
- **Minor/limitations:** coverage gaps and external release gates.
- **Files modified:** normally none for an independent review.

## Supporting Detail

See `references/deterministic-ooxml-compiler-review.md` for the reusable XLSX/OOXML evidence matrix, stale-fixture handling, and deterministic ZIP/core-property checklist.

## Verification Checklist

- [ ] Approval set and revision anchor frozen.
- [ ] Test side effects mapped and isolated.
- [ ] Core-property and ZIP metadata determinism inspected on the serialized package.
- [ ] Determinism test crosses a clock boundary or injects different clocks, and any core-XML normalization fails closed on missing/duplicate timestamp elements.
- [ ] Bounded OOXML package pre-scan and safety gates verified.
- [ ] Semantic readback and non-target invariants verified.
- [ ] Source/approval/Finance/provenance hashes bound.
- [ ] Native-Office signed qualification fail-closed.
- [ ] Current tests rerun independently.
- [ ] Stale artifacts/helper failures separated from source findings.
- [ ] Final verdict distinguishes code PASS from production GO.
