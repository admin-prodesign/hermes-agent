# Deterministic OOXML Compiler Review Reference

Reusable evidence matrix for an independent review of a remediated XLSX/OOXML compiler.

## 1. Revision and evidence boundary

| Review item | Acceptable evidence | Do not accept |
|---|---|---|
| Source revision | Commit/hash, or an explicit path plus readback size/line-count limitation | A controller's claim that the worktree is current |
| Tests | Fresh run against the frozen source/test files | A copied test report from another worktree |
| Artifacts | Receipt schema and generator version match the current source contract | Old outputs, cached receipts, or fixtures generated before the remediation |
| Helper failures | Current source and fixture required fields compared first | Assigning a missing newly-required field to the compiler without comparison |

If no hash-capable tool is available, disclose that exact file hashes were not independently obtained; do not manufacture a revision identifier.

## 2. Determinism checks

A robust compiler normally needs both of these layers:

### Workbook and serialized core-properties layer

- Freeze writer-owned core properties such as `created`, `modified`, and `lastModifiedBy`.
- Treat this only as intent until the saved package is inspected. Writers may replace `modified` with wall-clock time while serializing `docProps/core.xml` even when the in-memory property was frozen.
- Compare the actual serialized core part from outputs produced across different clock seconds. If normalization rewrites core XML, require exactly one `created` and one `modified` element, change only their values, and fail closed on missing, duplicate, malformed, or unexpected structure.
- Ensure the workbook writer does not inject random IDs or environment-specific identity fields elsewhere.
- Preserve formulas, links, styles, merges, dimensions, print area, page setup, and non-target logical state.

### ZIP layer

- Sort entries by package path.
- Use a fixed valid timestamp at or after 1980.
- Fix compression method and level.
- Clear variable member comments, extra fields, and filesystem permission attributes unless a required OOXML feature needs them.
- Preserve each member's filename and uncompressed part bytes except explicitly reviewed serialized core-property canonicalization.
- Confirm that the resulting package remains a normal non-ZIP64 XLSX when the bounded size policy requires that.
- Validate the rewritten output and reopen it before calculating the receipt hash.

A byte-equality regression test is necessary, but pair it with semantic readback. Force the two builds across a wall-clock boundary (for example, a >1-second delay when the writer stores second-resolution times) or inject different clocks; two immediate builds can pass accidentally. Two identical files can still encode the wrong workbook.

## 3. Package safety order

For an input that may be attacker-controlled, inspect bounded raw ZIP metadata before constructing an unbounded archive member list:

1. Bound the EOCD search window and reject malformed/multi-disk/ZIP64 packages when policy disallows ZIP64.
2. Read only the bounded central directory.
3. Bound entry count and central-directory size.
4. Reject duplicate names and case-folded collisions.
5. Reject unsafe absolute, parent-traversal, or backslash paths.
6. Bound per-entry compressed/uncompressed sizes and aggregate expanded size.
7. Check central-directory offsets and entry bounds.
8. Only then construct `ZipFile` and revalidate the parsed metadata.
9. Reject macros, external links, ActiveX/embeddings, unsafe XML DTD/entities, and corrupt CRC members.

A post-`infolist()` count check alone is not a pre-allocation defense.

## 4. Provenance and trust matrix

| Boundary | Required invariant |
|---|---|
| Source attachment | Source SHA-256 is immutable and matches the prequalification manifest and workflow receipt |
| Route | Approval target set exactly equals the route allowlist; no Finance electronic target |
| Approval evidence | Canonical status, exact IDs, Mattermost timestamps, revision hashes, and compiler approval snapshot digest are bound before output write |
| Procurement | Header Applicant and Step-1 evidence are identical when that fulfillment link is selected |
| Finance | `X22:X23` is blank and unobstructed before signing, after signing, and in the final receipt |
| Template | Filename, sheet, dimensions, merges, print area, logical hash, and revision marker match the manifest |
| Native QA | Signed receipt binds exact template/output hash, Microsoft Excel renderer, registered environment, certifier, render/golden hashes, time, and page count |
| Production registration | Downstream state verifies the receipt again and rejects `production_qualified=false`, stale approval digests, invalidated artifacts, or mismatched output hashes |

An empty production trust store should reject qualification. Tests may inject a test-only key, but the production private key must not be present in source, fixtures, or runner configuration.

## 5. Test-only bypass review

An `allow_unqualified_test_template`-style switch can be acceptable only when all of the following are true:

- The default is false.
- The production runner does not set it.
- The downstream artifact-registration path independently rejects unqualified output.
- Receipts preserve the qualification state instead of falsely marking test output as production-qualified.
- The switch is clearly named and documented as test-only.

If the compiler is deployed as a standalone production CLI, remove the switch or gate it on an unmistakable non-production mode; do not rely solely on operator discipline.

## 6. Verdict separation

Use two separate statements when needed:

- **Compiler code verdict:** PASS when no Critical or Important defect remains in the reviewed revision.
- **Production release decision:** GO/NO-GO based on all external gates, including native Excel render certification, historical template validation, deployment/scheduler receipts, and same-thread delivery readback.

A compiler can receive a code-review PASS while the product remains NO-GO because native Office qualification has not yet been completed. That is not contradictory; it is an evidence-boundary distinction.
