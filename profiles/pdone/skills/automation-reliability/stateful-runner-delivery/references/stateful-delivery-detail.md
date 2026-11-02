## Trigger Conditions

Load this skill when the task includes any of the following:

- a runner method that uploads/posts/sends an artifact;
- an outbox, delivery receipt, idempotency key, marker, lease, or worker claim;
- completion that depends on destination/channel/thread/sender/file readback;
- a timeout or connection error after a request may already have committed;
- a requirement to avoid duplicate sends or blind retries;
- reconciliation of an existing `planned`, `claimed`, `verification_pending`, `verified`, or `failed` record.

## Required Delivery Protocol

### 1. Qualify the artifact before side effects

- Read the exact local bytes once.
- Require the expected artifact type and extension.
- Match the local filename, positive byte size, and SHA-256 to exactly one durable registered artifact row.
- Require the artifact to be the correct kind, non-invalidated, and fully qualified by every required structural, security, finance-blank, and render-QA gate.
- At the delivery boundary, reparse and cryptographically revalidate the stored immutable compiler/render receipt and current source/approval provenance against the fixed trusted-key store. Cached qualification booleans are an index, not authorization to send; never accept caller-supplied trust material for replay.
- Reject before planning or network calls when the path is unregistered, stale, changed, empty, ambiguous, or no longer validates under current immutable evidence.

### 2. Persist intent before sending

- Plan the outbox row before upload/post.
- Bind it to the stable workflow/root identity, artifact ID, immutable file name/hash/size, and a validated idempotency key.
- On replay, inspect the existing row before invoking a planning transition; a completed workflow may otherwise reject a harmless replay.
- If the key is already bound to different evidence, fail closed.

### 3. Use a deterministic marker

Derive a marker from stable workflow identity plus the validated idempotency key. Put it in a typed/structured post property and, when useful, a human-readable message. Structured marker properties are authoritative. A text fallback must match one exact bounded token—not a substring—and duplicate occurrences in one post are malformed. Before uploading or posting, search the destination thread for the exact marker:

- zero matches: the send may proceed after claiming;
- one exact match: reconcile/read back it instead of sending;
- multiple matches, malformed marker properties, or duplicate text tokens: preserve ambiguity and stop;
- search failure or malformed response: enter verification-pending and stop.

A preflight that cannot prove absence is not permission to send.

### 4. Fence claims and transitions

- Claim with a unique lease token, explicit owner, and future expiry.
- Pass the owning token to every engine transition that mutates delivery state.
- An active claim held by another worker is not retryable.
- An expired claim may be reclaimed only for readback/reconciliation, never to authorize a resend.
- Do not use a new worker's token to finish another worker's pending/active claim unless the engine provides an explicit safe takeover transition.

### 5. Verify the file before and after posting

After upload, independently read back file metadata and download the bytes. Require the returned file ID, name, positive size, and downloaded hash to match the registered artifact before posting. Then post exactly one attachment with the marker.

Immediately after the post call returns—or raises after it may have dispatched—transition the claimed receipt to `verification_pending`. Do not mark success directly from the create response.

### 6. Verify canonical destination evidence

Fetch the canonical post, or locate it by the deterministic marker when the create response was lost. Require all of:

- exact destination channel;
- exact originating root/thread;
- exact bot/sender identity;
- exact canonical post ID;
- exactly one attachment and non-empty file ID;
- exact filename;
- exact positive byte size;
- downloaded SHA-256 matching the planned artifact.

Only after every field matches should the engine transition the receipt to `verified` and the workflow to completed. Persist mismatch evidence when the engine supports it; otherwise remain verification-pending.

### 7. Model ambiguity conservatively

Classify outcomes by whether the remote side may have committed:

| Situation | State/action |
|---|---|
| Local artifact invalid/unregistered | Reject before outbox/network |
| Definite failure before any send attempt | `failed`, then explicit retry may be considered |
| Upload/post may have committed | `verification_pending`; reconcile only |
| Readback missing/unavailable/malformed | `verification_pending`; no blind retry |
| Readback mismatches channel/root/sender/post/file/name/size/hash | `verification_pending` with mismatch evidence |
| Exact canonical readback | `verified` / completed |
| Replay after verification | Return the same receipt; no second side effect |

Never convert a potentially committed operation into a retryable definite failure merely because the response was lost.

## Intake Governance and Cursor Safety

For bounded pilots, do not let a mutable configuration file become an authorization source by itself. Keep submissions disabled by default, require the canonical configuration JSON to match a code-registered reviewed SHA-256 before intake can be enabled, and require each source attachment hash to appear in a reviewed allowlist with governed source evidence. Persist the reviewed config digest and governed evidence in immutable workflow-creation evidence and include them in the approval-start frozen configuration.

Validate governed source evidence in the state engine as well as the runner when alternate callers can invoke the engine. Shape-only checks are not enough: enforce the exact source system/root/folder/file policy and approved date window, including timezone requirements.

A channel poller must treat unrelated or unknown thread replies as bounded non-workflow input rather than fatal work. Catch the engine's actual not-found exception (not merely a transition error), record/ignore it under policy, and advance the cursor. Otherwise one reply to an unknown root can poison the poll window and indefinitely block every later valid post. Add a regression that places an unknown-thread reply before valid work and proves the poller continues.

## Signed Artifact Receipt Contract Migrations

When the artifact producer changes renderer or qualification semantics, update the engine and runner as one trust-boundary contract. Compare the producer's exact receipt fields and registered constants first, then require the new renderer identity, binary/environment hashes, signing-key binding, and qualification flags at registration and again at delivery-time revalidation. Bind source-workbook, qualified-template, signed-output, rendered-PDF, and golden-comparison hashes independently; do not trust a cached `production_qualified` boolean. Require positive page/PDF metadata and explicit visual checks such as CJK readability, layout, and Finance blankness. Add a regression that constructs a validly self-hashed legacy receipt and proves it fails closed, rather than only testing malformed JSON or a broken self-hash.

See `references/signed-receipt-contract-migrations.md` for the concise producer/consumer checklist and fixture recipe.

## Testing Strategy

The minimum regression matrix is:

1. normal qualified delivery: one upload, one post, exact verification;
2. idempotent replay: same receipt, zero second uploads/posts;
3. post-commit response loss: marker reconciliation, zero blind retry;
4. mismatched readback: pending state and durable mismatch reason;
5. pre-send marker already present: reconcile without upload/post;
6. marker search unavailable or ambiguous: pending without send;
7. invalidated/unregistered/local-hash-changed artifact: reject before network;
8. active lease held by another worker: no send;
9. expired lease: readback takeover only;
10. missing/malformed file metadata or canonical post: pending, not completed;
11. signed-receipt or provenance tampering after registration: reject before upload/post;
12. exact marker boundary: a longer substring does not match, while duplicate or malformed exact markers fail closed.

Make side-effect assertions phase-aware. A mismatch in upload response or file-info readback occurs before posting, so expect zero delivery posts. A mismatch injected into canonical post readback occurs after the remote post already exists, so expect exactly one post, `verification_pending`, and zero resends on replay. Do not write a test whose expected side-effect count contradicts where the fault was injected.

Run the narrow suite first, then the exact project regression command. Report real command output, compile/lint results, files changed, and whether any application state was mutated during verification.

When adding a bounded maintenance CLI mode or projecting runner state into external metadata such as a channel header/status line, load `references/maintenance-modes-and-test-isolation.md`. It covers dependency-minimal branch ordering, exact preservation of non-owned metadata, one-write/readback reconciliation, production-log isolation in tests, and pruning-backup allowlists.

## Separate Code PASS from Release GO

A green mocked runner suite proves the frozen runner behavior, not that a releasable artifact, native qualification, production trust key, active safe execution surface, deployment, or live destination receipt exists. Scope review verdicts explicitly—for example, `PASS — runner code` alongside `FAIL — release` and `NO-GO — submissions disabled` when downstream gates remain open.

Independent verdicts are revision-bound. Any code or test edit after review starts invalidates the verdict. A reviewer timeout is not a PASS even when its checks were green; preserve the transcript and use a narrow, read-only verdict-only pass rather than repeating broad discovery. See `references/bounded-independent-review.md` for the reusable freeze, timebox, timeout-recovery, and versioned-receipt pattern.

When policy requires a typed safe wrapper, distinguish four states: source built, fresh-process verification passed, capability exposed in the active tool surface, and real execution verified. A registry entry or compiled script is not proof of active exposure. Do not bypass a missing typed tool with raw shell access; route a narrow capability-promotion/admin handoff and keep any reload/restart separately approved.

See `references/release-gating-and-safe-execution.md` for the full gate model, verdict vocabulary, safe-wrapper exposure pattern, and receipt checklist.

## Common Pitfalls

- Calling `plan` on a completed workflow before checking for an existing verified outbox row.
- Trusting a successful upload/post response without canonical readback.
- Searching for a marker only after posting; absence must be checked before the first side effect too.
- Treating an exception as proof that the remote request did not commit.
- Retrying a `verification_pending` receipt because the first run did not receive a response.
- Validating only the file hash while omitting channel, root, sender, post ID, filename, or size.
- Reclaiming a lease to resend instead of restricting takeover to reconciliation.
- Testing only the happy path with a fake client that cannot simulate post-commit response loss.
- Trusting cached `qualified=true` flags at send time without revalidating the stored signed receipt and current immutable provenance.
- Using substring marker matching or accepting multiple exact markers as a successful reconciliation.
- Expecting zero remote posts in a test that injects the mismatch only during post-readback; that fault occurs after one remote commit, so the safety property is zero resends, not zero initial posts.
- Reporting green mocked tests as a release GO while artifact qualification, trust, active tool exposure, deployment, or live-readback gates remain open.
- Treating a registry entry or fresh-process source test as proof that the active agent process can invoke the capability.
- Catching only transition errors for unknown roots; the engine's not-found exception can escape, prevent cursor advancement, and stall all later channel work.
- Validating reviewed source evidence only in the runner while leaving a directly callable engine able to freeze arbitrary evidence.
- Enabling intake from a mutable config boolean without binding the entire canonical config to a reviewed digest.

## Verification Checklist

- [ ] Artifact registration and qualification were checked against current local bytes.
- [ ] Outbox intent was persisted before network side effects.
- [ ] Idempotency key and marker are deterministic and validated.
- [ ] Pre-send marker reconciliation occurs before upload/post.
- [ ] Owner/token/expiry fencing is enforced by existing engine APIs.
- [ ] Upload metadata and downloaded bytes were read back.
- [ ] Post response loss is treated as ambiguous.
- [ ] Canonical channel/root/sender/post/file/name/size/hash evidence is required.
- [ ] Pending/mismatch paths cannot blind-retry.
- [ ] Replay does not duplicate side effects.
- [ ] Exact regression suite is green.

See `references/delivery-state-and-reconciliation.md` for the reusable state sequence, pseudocode shape, failure matrix, and adversarial test checklist.
