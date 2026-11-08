# Deterministic approval-to-artifact workflows

Use this reference when a Mattermost approval flow collects structured departmental data, produces a signed Office artifact, and treats verified same-thread delivery as the electronic completion boundary.

## State and configuration

1. Use one Mattermost root post ID as the external idempotency key.
2. Model intake, applicant attestation, manager attestation, `ready_to_start`, explicit approval start, departmental stages, artifact readiness, delivery planning, verification, rejection, and manual-review states separately.
3. Freeze route, exact user assignments, semantic schemas, source file metadata, template revision/mapping, and any uncertain fulfillment linkage at the explicit start transition. Persist canonical JSON plus SHA-256.
4. Store immutable source post/file identity and hash. Compile from a working copy; never overwrite or silently mutate the submitted workbook.
5. If a business mapping is unresolved, represent it as configuration and fail closed rather than hardcoding an assumption. For example, do not silently assume an applicant header signature fulfills a numbered route step.

## Semantic submissions and decisions

- Do not approve an arbitrary caller-supplied digest. Persist canonical structured values, schema version, validation result, raw Mattermost `create_at` milliseconds, and an internally calculated content hash.
- Validate required and allowed fields, blank values, and N/A rules. N/A needs an allowlisted field and a nonblank reason.
- Bind each decision to exact stage, submission revision, content hash, exact approver user ID, post ID, and raw `create_at`.
- Make the observed-post path the **only** countable decision API. Do not expose a convenience `decide_stage()` that can insert an approval without durable observation evidence. Persist a `decision_pending` observation first, then insert the approval and flip that exact evidence row to counted in the same transaction. Regression-test that every counted approval joins to one counted evidence row and that no public bypass exists.
- Retain unauthorized, stale, out-of-order, duplicate, edited, deleted, and late decision posts as non-counted evidence. Persist the source observation before allowing a decision to count; a crash must never leave counted approval state with no durable observed-post row. A terminal non-counted observation must not become countable when the same post/payload is replayed later; require a fresh Mattermost post ID after the workflow reaches a valid state. If previously counted evidence is edited or deleted, supersede it and enter a fail-closed manual-review state—even when the workflow was already marked complete. Clear/revoke the completion marker and invalidate derived artifacts while preserving the prior delivery receipt as historical evidence.
- Enforce the full chronology chain, not only approval-after-submission: root/open time ≤ intake, intake or preceding counted approval ≤ next submission, decision ≥ active submission, and a revision must be strictly later than the prior revision. Store and compare raw Mattermost epoch milliseconds.
- Any accepted stage revision must supersede affected submissions and approvals, invalidate every artifact bound to the old approval snapshot, and fail or reconcile open delivery work. Revalidate the current approval digest again when delivery is planned; registration-time validation alone is not enough.
- Back software ownership checks with relational integrity. Use composite foreign keys or equivalent triggers so an approval cannot reference another workflow/stage's submission and an outbox receipt cannot reference another workflow's artifact; include direct-SQL cross-link rejection tests.
- Persist comments for change requests and rejections. Rejection is terminal and distinct from changes requested.

## Artifact qualification

Before delivery planning, register one immutable artifact record containing:

- output file name, SHA-256, and byte size;
- source file SHA-256;
- template revision and mapping version;
- workflow approval-snapshot SHA-256;
- generator version;
- structural-QA receipt;
- protected-blank-area verification;
- real Office render/golden-file QA receipt.

A structurally migrated XLSX is not production-qualified merely because it reopens in OpenPyXL. Require a hash-bound render receipt from the qualified Office environment before production compilation or delivery. Test-only overrides must be explicit and must not produce a production-qualified artifact.

Treat Office QA as a cryptographic trust boundary, not a caller boolean. A robust production path verifies two separately signed receipts:

1. **Template qualification receipt** — exact template hash, native Microsoft Excel environment, rendered PDF/golden-comparison hashes, page count, structural checks, protected blank-area check, certifier identity, and certification time.
2. **Signed-output qualification receipt** — the same classes of evidence bound to the exact final signed artifact hash after signatures are inserted.

Keep the production private signing key outside code, repositories, tests, runner configuration, and chat. Code should contain only an approved public key or trust-store identifier. Public RFC/test-vector keys are test fixtures, never production trust roots; inject a test-only trust store instead of compiling a known test key into the production verifier. Until the approved production public key is installed, the production trust store should be empty and qualification should fail closed—not fall back to a bundled test key.

Do not trust `structural_qa_passed=true`, `render_qa_passed=true`, `production_qualified=true`, or a self-authored JSON object on its own. A mutable manifest is not a security boundary. Re-verify the signed qualification envelope, its canonical self-hash, signer/key ID, exact template hash, native-Excel environment, and internally consistent flags every time a template is verified or compiled. At artifact registration, independently verify the compiler receipt self-hash, source/template/workflow hashes, exact route and signature evidence, output name/hash/size, template qualification signature, and final-output qualification signature.

For controlled forms, require the exact signature target set for the selected route. Reject missing targets, extra targets, and signatures in physical-only areas such as Finance. Keep output changes confined to allowlisted signature cells; compare non-target logical workbook state before and after compilation.

## Idempotent outbox and exact completion receipt

Use a persistent outbox with states such as `planned`, `claimed`, `verification_pending`, `verified`, and `failed`.

1. Claim atomically with a worker ID, lease token, and expiry before sending. Reject an already-expired lease at claim time, and require the same unexpired lease for claimed-state transitions and readback verification.
2. Distinguish **definitely unsent** from **possibly sent**. Only a planned/claimed operation that proves `send_attempted=false` may become retryable `failed`. Once the post send may have been attempted, persist a known post ID or `verification_pending`; never let an operator error, readback mismatch, evidence edit, or stage invalidation convert that ambiguity into an ordinary retry.
3. On worker loss, an expired claimed lease may be taken over only for reconciliation. Move it to `verification_pending` under a new reconciliation lease; do not authorize a resend merely because the prior lease expired. A contradictory readback remains pending and non-retryable until exact-thread reconciliation succeeds or a separately reviewed resolution proves no side effect occurred.
4. Reconcile by searching/reading the exact originating thread and expected artifact identity.
5. Mark complete only when readback matches all required evidence:
   - expected channel ID;
   - originating root post ID;
   - expected bot sender user ID;
   - delivery post ID;
   - non-empty file ID;
   - exact file name;
   - exact byte size;
   - downloaded/read-back SHA-256.
6. Store observed evidence fields on the receipt. An unrelated post with the same filename/hash must not complete the workflow.

Electronic completion means verified artifact delivery only. Do not imply physical stamping, ERP entry, scan return, or archive completion unless those are explicitly in scope and separately evidenced.

## Polling and persistence

- Persist poll cursors and worker leases transactionally; do not rely on in-memory watermarks.
- Never advance a channel cursor past a post that failed deterministic processing merely because the loop caught the exception. Either stop and retain the cursor before that post, or atomically persist a bounded retry/dead-letter record before advancing. A returned `ok` run with an errors list is not safe if failed events have been skipped.
- Define stage ownership once. If the state engine synthesizes intake/applicant-attestation stages, the runner must pass only the route-specific department assignments; reject duplicate/extra stage definitions rather than silently reconciling them.
- Snapshot reads used for receipts should run in one read transaction so workflow, stages, approvals, artifacts, outbox rows, and events are mutually consistent.
- Version the database schema. Check the complete existing table/column/version shape **before** running `CREATE TABLE IF NOT EXISTS` or any migration-like initialization against a nonempty database. Fail closed and require an approved migration or fresh pilot database rather than partially mutating an unsupported shape.

## XLSX safety and determinism

- Validate OOXML ZIP paths, entry limits, expanded size, compression ratio, required parts, external links, macros/embedded objects, and prohibited DTD/entity declarations. Bound and validate the raw classic ZIP end-of-central-directory and central-directory metadata before constructing `ZipFile`; reject ZIP64/duplicate/case-colliding names when unsupported. Regression-test the pre-scan against a known-good XLSX so escaped source literals such as `b"PK\\x05\\x06"` cannot accidentally replace the actual ZIP signature bytes `b"PK\x05\x06"`.
- Normalize ZIP timestamps and the workbook core `created`/`modified` metadata before hashing; otherwise identical inputs may produce different physical hashes.
- Preserve controlled labels, merged ranges, row/column geometry, print settings, and protected blank areas. Do not auto-fit, insert rows/columns, alter merges, or shrink content merely to force signatures into boxes.
- Physical package hashes and logical workbook hashes serve different purposes; record both. Treat fixtures and receipts produced before a compiler/evidence-schema change as stale diagnostics: regenerate them and rerun qualification before use.

## Review and verification discipline

- Passing unit tests does not prove specification compliance. Run an independent spec review that traces each completion and side-effect claim to persisted evidence.
- Freeze the exact review revision before dispatching reviewers: record a commit or bounded file-hash manifest for implementation, schema, and tests. Do not keep editing reviewed targets while a read-only review is running. Accept a review verdict only when its receipt identifies that exact revision and the same test sources still exist; otherwise re-dispatch against the final revision.
- If a delegated reviewer or builder times out, inspect any partial artifacts it left, but treat them as untrusted until read back, tested, and reviewed.
- After every final patch, rerun the affected suite. Do not quote stale pass counts from before the last change.
- Minimum regression areas: route completeness, no electronic physical-only stage, intake/start gates, exact identities, semantic validation, revision invalidation, rejection, edited/deleted evidence, artifact provenance, QA gates, claim/double-send protection, ambiguous-send reconciliation, exact delivery receipt, schema compatibility, OOXML tampering, deterministic output, and protected blank areas.
