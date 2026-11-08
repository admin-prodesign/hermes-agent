# Delivery State and Reconciliation Reference

## Durable state sequence

```text
registered + qualified artifact
    -> planned outbox intent
    -> claimed (owner, lease token, expiry)
    -> verification_pending (remote side may have committed)
    -> verified
```

A definite failure before any send attempt may enter `failed` and require an explicit retry transition. Any failure after upload/post dispatch is ambiguous until canonical readback proves what happened.

## Pseudocode shape

```text
artifact = validate_registered_artifact(local_bytes)
revalidate_stored_signed_receipt_and_current_provenance(artifact, fixed_trust_store)
existing = find_outbox_by_idempotency_key(root, key)
if existing is verified:
    return existing_receipt_without_side_effects
if existing is pending with an active lease:
    return pending_without_blind_retry
if existing is pending with an expired lease:
    claim = reacquire_for_reconciliation_only(existing)
    return search_marker_and_canonical_readback(claim)  # never upload/post

receipt = plan(root, artifact_id, key)
claim = claim(receipt, owner, unique_token, future_expiry)

matches = search_thread_for_structured_or_exact_bounded_marker(root, marker)
if search_failed or malformed_marker or multiple_matches:
    mark_pending(claim, post_id=None)
    return pending
if one_match:
    mark_pending(claim, post_id=match.id)
    return canonical_readback_and_verify(match)

upload = upload_once(channel, local_bytes)
read_back_file(upload.file_id)
try:
    post = create_post_with_file(root, marker, upload.file_id)
except response_loss_or_transport_error:
    mark_pending(claim, post_id=known_or_none)
    return search_marker_and_reconcile()

mark_pending(claim, post_id=post.id)
canonical = get_post(post.id)
return canonical_readback_and_verify(canonical)
```

The concrete engine/API names may differ, but the ordering is invariant: durable intent → claim → preflight reconciliation → one send → pending → canonical readback → verified.

## Failure matrix

| Evidence | Durable result | Automatic retry? |
|---|---|---|
| Unregistered/stale/invalidated/local-changed artifact | Reject before planning/network | No |
| Pre-send search unavailable or ambiguous | `verification_pending` | No |
| Active lease belongs to another worker | Preserve claim/pending | No |
| Expired claim | Reclaim for readback only | No resend |
| Upload/post may have committed | `verification_pending` | Reconcile only |
| Missing canonical post/file readback | `verification_pending` | No |
| Wrong channel/root/sender/post/file/name/size/hash | `verification_pending` plus mismatch evidence | No |
| Exact canonical readback | `verified` / completed | Replay returns receipt |

## Adversarial test checklist

- happy path performs exactly one upload and one post;
- replay with the same key performs zero new side effects;
- a post-commit timeout finds the marker and verifies without retry;
- tampering with the stored signed receipt or current provenance after registration is rejected before network access;
- a mismatched channel or file in canonical post readback leaves exactly one already-created post pending and performs zero resends;
- upload-response or file-info mismatch occurs before posting and therefore leaves zero delivery posts;
- a pre-existing exact marker prevents upload/post, while a longer substring does not count as a marker;
- malformed properties, duplicate exact tokens, multiple matching posts, or unavailable thread search fail closed before sending;
- an expired pending/claimed lease can be taken over only for reconciliation and cannot reach the upload/post branch;
- missing file metadata, wrong file count, or hash/size disagreement never completes;
- artifact invalidation or local mutation is rejected before the network client is called.
