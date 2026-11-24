# Remote embedding offload verification

Use this procedure when embeddings or other inference are migrated from a busy host to a remote machine. The goal is to prove that work moved, quantify source-host relief, detect destination-host saturation, and verify failover behavior. A lower CPU graph on the source is not sufficient by itself.

## 1. Define matched comparison windows

Anchor the post-migration window to the first verified remote-mode event, deployment receipt, or endpoint-switch journal entry. Compare it with an equally long immediately preceding window.

For each window, calculate from historical host metrics when available:

- average, median, p95, and maximum CPU busy percentage;
- average and p95 15-minute load;
- average, p95, maximum, and threshold-crossing count for CPU PSI `avg300`;
- IO and memory PSI, so an apparent CPU improvement does not hide new storage/reclaim contention;
- count of samples above the monitor's actual alert thresholds.

Prefer `sadf`/`sar` data and calculate metrics programmatically rather than eyeballing alert messages. Report percentage-point deltas and threshold-crossing counts. If destination-host history is unavailable, say so explicitly and report only the live destination sample plus endpoint history.

## 2. Prove the source host really stopped doing inference

Verify all of the following:

- no local model runner is loaded;
- the former inference listener is absent or intentionally inactive;
- no established client connections still target the former local endpoint;
- the client/API container itself is not consuming the old inference-level CPU;
- current high load, if any, is attributed with a short `pidstat`/process/container sample rather than assumed to be embeddings.

A source host can still have a high 15-minute load after migration because load averages decay slowly or because unrelated IO/process bursts occurred. Use live PSI and process attribution before calling the migration ineffective.

## 3. Trace the actual remote path end to end

Do not stop at the client configuration label `remote`. Verify the live route:

1. Identify the local proxy/tunnel listener and owning process.
2. Trace any relay hop without exposing private keys, tokens, or unnecessary addresses.
3. Verify that the final destination is the intended host and model service.
4. Run a bounded embedding probe and validate the expected vector dimensions/model identity.
5. Confirm active connections traverse the remote listener.

When multiple network planes exist (for example, a default tailnet plus a dedicated relay tailnet), a peer appearing offline in one status view does not prove the production route is down. Trace the listener and established tunnel actually used by the client.

## 4. Inspect destination-host load

On the destination, collect a bounded live sample:

- logical CPU count and load averages;
- several CPU-usage samples rather than one instantaneous value;
- top process CPU/RSS;
- model-runner identity and loaded model;
- endpoint latency or timeout behavior under load.

State both sides of the result: `source offload succeeded` and, separately, `destination capacity/reliability is healthy or constrained`. A migration can succeed operationally while moving saturation to the destination.

## 5. Audit endpoint and failover reliability

From the endpoint watchdog journal/state, count over the same comparison window:

- successful and failed remote probes;
- remote/local switches;
- service-level failures;
- current mode and consecutive failure/success counters;
- whether the fallback endpoint itself passes a probe.

Transport errors must be normalized into ordinary failed probes so counters and failover state still advance. Cover at least timeout, connection refusal/reset, DNS/connect errors, and remote disconnect/EOF. Catching only URL/timeout exceptions can allow an uncaught remote disconnect to crash the watchdog before state is saved or fallback is attempted.

After changing failover logic, smoke-test three paths with bounded fixtures or controlled probes:

1. healthy remote remains remote;
2. repeated remote failure reaches the configured threshold and selects healthy fallback;
3. remote recovery reaches the restore threshold and returns to remote.

Verify mode, counters, endpoint response dimensions, recreated client services if applicable, and the final journal receipt.

## 6. Update monitoring for the new topology

Migration often leaves an older watchdog checking the retired local model port. Audit every related health/federation monitor and classify each check as:

- active production endpoint;
- intentional fallback endpoint;
- retired/stale endpoint.

An intentionally disabled local inference service must not generate a production-down alert when remote mode is healthy. Keep a separate fallback-readiness probe if needed, but label it as fallback readiness rather than active endpoint availability.

## Reporting shape

Report four independent conclusions:

1. **Source-host CPU result** — matched-window metrics and current process proof.
2. **Destination-host load** — live CPU/model evidence and historical-data limitation.
3. **Endpoint reliability** — probe successes/failures, switches, and current mode.
4. **Remaining risks** — destination saturation, failover bugs, stale monitors, or unrelated IO pressure.

Always state whether any services/configuration were changed. Preserve exact internal receipts in the operations log, but keep credentials, private addresses, and raw transcript/log bodies out of the user-facing report.
