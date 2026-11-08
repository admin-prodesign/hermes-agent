# Release Gating Beyond Runner Unit Tests

A delivery runner can be code-correct while the release remains NO-GO. Keep these states separate in reviews and receipts.

## Independent gates

1. **Code gate** — syntax, unit, and adversarial delivery tests pass.
2. **Artifact gate** — an exact registered artifact exists and still matches filename, positive size, and SHA-256.
3. **Qualification gate** — structural/security/render requirements pass for that exact artifact and template hash.
4. **Trust gate** — required certification signature verifies against an approved public-key trust store; test keys and caller-supplied keys are not production trust.
5. **Execution-surface gate** — the active agent can invoke the approved bounded runner/QA capability through a typed safe tool; source code or a registry entry alone does not prove the tool is exposed or active.
6. **Deployment gate** — service/scheduler binding, health, alerting, rollback, and limited-pilot receipts exist.
7. **Live delivery gate** — canonical destination readback proves the actual channel/root/sender/post/file/name/size/hash receipt.

A PASS at an earlier gate never substitutes for a later gate. In particular, green mocked runner tests do not prove that a production-qualified artifact exists or that a live send occurred.

## Review verdict vocabulary

Report verdicts with their scope:

- `PASS — runner code`: no code-level Critical/Important findings in the frozen revision.
- `FAIL — release`: one or more artifact, qualification, trust, execution-surface, deployment, or live-delivery gates remain open.
- `NO-GO`: employee/live submissions stay disabled.

Do not collapse these into a single ambiguous `PASS` or `FAIL`.

## Safe execution surface

When policy forbids raw shell/execute access for the active channel:

- use the typed bounded safe wrapper when it is exposed;
- if the capability exists in a registry but is absent from the live tool surface, treat that as an exposure/activation gap, not proof that the underlying operation is impossible;
- request a narrow admin handoff for wrapper registration/source-hash discovery and bounded tests;
- keep gateway/process reload as a separate explicitly approved action;
- do not bypass the policy with an ad hoc script just because the script exists and compiles.

Report `built`, `verified in a fresh process`, `exposed in the active tool surface`, and `executed successfully` as separate states.

## Receipt checklist

- [ ] Frozen source/test hashes recorded.
- [ ] Exact test commands/results recorded.
- [ ] Artifact identity and qualification receipt recorded separately.
- [ ] Trust key ID and signature verification recorded without exposing private material.
- [ ] Active typed capability exposure verified.
- [ ] Deployment/service/scheduler receipts recorded.
- [ ] Live destination readback recorded, or explicitly marked not performed.
- [ ] Employee/live submissions remain disabled while any required gate is open.
