## Trigger Conditions

Load this skill when the task includes any of the following:

- a runner method that uploads/posts/sends an artifact;
- an outbox, delivery receipt, idempotency key, marker, lease, or worker claim;
- completion that depends on destination/channel/thread/sender/file readback;
- a timeout or connection error after a request may already have committed;
- a requirement to avoid duplicate sends or blind retries;
- reconciliation of an existing `planned`, `claimed`, `verification_pending`, `verified`, or `failed` record.

## Required Delivery Protocol
See `references/required-delivery-protocol.md`.

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
