# stateful-runner-delivery — Required Delivery Protocol

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
