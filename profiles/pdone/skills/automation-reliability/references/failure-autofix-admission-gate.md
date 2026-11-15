# Failure-autofix LLM admission gate

Use when restoring or changing `pd-one-failure-autofix` / `pd-neo-failure-autofix` auto-repair.

## Rule

The LLM is not the first responder. A repeating unresolvable class must not open a new model session every tick.

## Shared gate

- Module: `/home/prodesign/.hermes/scripts/failure_autofix_admission_gate.py`
- State: `~/.hermes/state/failure-autofix-admission/state.json`
- Receipts: `~/.hermes/state/failure-autofix-admission/decisions.jsonl`
- Tests: `/home/prodesign/.hermes/scripts/tests/test_failure_autofix_admission_gate.py`

Callers:

- webhook route `script: failure_autofix_first_pass.py` on both autofix routes
- `pd_one_failure_alert_queue_worker.py`
- `pd_neo_failure_alert_queue_worker.py`

## Policy

- Signature = source + incident kind + class + normalized summary (`#N`, timestamps, hex ids stripped).
- Transient (`URLError`, timeout, no route, 5xx): 3 hits in 30m, then one LLM, then 12h cooldown.
- Unsafe (auth/permission/schema/readback): one LLM immediately, then cooldown/latch.
- After unresolvable / needs-approval / blocked: 24h latch.
- Global cap: 4 LLM repairs/hour across both rails.
- LLM path is thin direct xAI (no Hermes tools). Do not re-enable the Hermes agent tool path without Andy approval.

## Producer behavior

PD One bridge treats webhook `ignored` + `reason=script` as accepted so a suppressed event is not re-queued into the Codex worker.

## Verification

```bash
python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_admission_gate.py
python3 -m py_compile /home/prodesign/.hermes/scripts/failure_autofix_admission_gate.py
```

Do not re-enable the routes without the script field and Codex pin present.

## Signature normalize

- `summary` / `title`: strip ISO timestamps, `#N`, epoch-like ints, and hex ids (`[a-f0-9]{8,}`).
- `condition_key`: same hex-id strip as summaries (via `_normalize_condition`), so `pd-one-supervisor-audit:<hex>` collapses across ticks.

## Post-LLM verdict latch (queue vs webhook)

- Queue workers (`pd_one_failure_alert_queue_worker.py`, `pd_neo_failure_alert_queue_worker.py`) call `record_verdict` after the repair agent returns so blocked/unresolvable latches 24h.
- Webhook routes run `failure_autofix_admission_gate.py` as a **pre-agent** route `script` (`webhook_transform` / `decide`), and `failure_autofix_webhook_post_hook.py` as **post-agent** `post_script` (invoked from `WebhookAdapter.send` when `deliver=log`, including silence markers). The post hook parses `SUPERVISOR_OUTCOME_JSON` when present and calls `record_verdict`.
- Manual latch still available: `python3 failure_autofix_admission_gate.py --verdict needs_input --file alert.json`.
- Tests: `python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_admission_gate.py` and `python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_webhook_post_hook.py`.


## First-pass redesign (2026-09-17)

Andy-approved script-first redesign for `pd-one-failure-autofix` / `pd-neo-failure-autofix` (same stack on Nemo).

### Order of operations

1. **Cheap admission** (`no_agent_noise`, `below_severity`, `last_fix_still_green`, latch) — never calls a model.
2. **Allowlist executor** (`failure_autofix_allowlist.py` → `hermes_guarded_autorepair.py`) — zero model; one repair + one verify.
3. If verify fails: stop, emit one concrete offer, latch — **no retry storm / no LLM burn**.
4. If still actionable and admission allows: **thin direct xAI** (`failure_autofix_thin_llm.py`, same pattern as `mm_ephemeral_translate_nemo`) — short system + failure packet only; **fail closed** (no Hermes tool schemas / no utility-agent backup).
5. Webhook route script always returns `__hermes_ignore__` after first-pass so the Hermes agent path is not used.

### Modules

- `failure_autofix_first_pass.py` — orchestrator; webhook `script` for both routes
- `failure_autofix_allowlist.py` — source/command match against `profiles/pdone/autorepair/targets.json`
- `failure_autofix_thin_llm.py` — direct `api.x.ai` chat completions
- `failure_autofix_admission_gate.py` — signature/latch/cooldown + cheap rejects + `record_verdict`
- Queue workers call `run_first_pass` instead of `run_hermes`

### Caps

- At most one LLM attempt per signature per 12h cooldown; latched recurrence pages Andy/surfaces (6h page cooldown) and does not re-burn.
- Global cap remains 4 LLM reservations/hour.

### Verification

```bash
python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_admission_gate.py
python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_webhook_post_hook.py
python3 /home/prodesign/.hermes/scripts/tests/test_failure_autofix_first_pass.py
```

Do not turn high-frequency watchers into agent polls; keep them emitting events into this rail.
