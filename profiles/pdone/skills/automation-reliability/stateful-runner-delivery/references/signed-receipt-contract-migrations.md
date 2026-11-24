# Signed Receipt Contract Migration Notes

## Producer/consumer alignment

For a signed compiler/render receipt, the consumer must match the producer's exact contract rather than infer compatibility from broad flags:

- envelope: `payload`, `signature`, `public_key_id` only;
- payload: exact artifact kind and bound artifact hash;
- source XLS hash, rendered PDF hash, and golden-comparison hash;
- registered renderer product, binary path/hash, version/build, render mode;
- registered office-environment ID/hash;
- certifier identity equal to the trusted public-key ID;
- positive page count and rendered-PDF byte size;
- explicit visual checks for CJK readability, layout, and Finance blankness.

At the engine boundary, compare the source hash inside each signed receipt with the immutable workflow source hash. Revalidate the full stored receipt before delivery; database QA booleans are not sufficient authorization.

## Legacy rejection fixture

1. Build a complete current receipt fixture and sign its canonical sorted JSON payload with the test-only private key.
2. Clone the receipt.
3. Replace the current qualification flag with the former native-renderer flag and, if needed, change renderer metadata to the former renderer.
4. Recompute the compiler receipt self-hash after mutation. Otherwise the test only proves tamper detection and never reaches the legacy-contract rejection branch.
5. Assert registration fails closed with the renderer/qualification contract error.
6. Assert the untouched current receipt registers and is accepted again by delivery-time revalidation.

Never place private qualification keys in the implementation, fixtures committed for production, runner configuration, or deployment package; inject test keys only during isolated tests.
