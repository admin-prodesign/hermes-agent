# Approval-scoped index and sync automations

Use this pattern when an approved request creates a recurring index/sync across Mattermost and Google Sheets or similar systems.

## Core sequence

1. **Freeze the authorization envelope**
   - Record the approval/ticket receipt, exact requester identity, source channel, destination document/tab/range, schedule, and permitted side effects.
   - Treat allowed write targets as exact. A prerequisite repair to a shared tool, policy, gateway, credential store, or unrelated source file is a separate write target and needs separate authority.

2. **Build the static artifact first**
   - Audit and normalize the source set.
   - Create/populate the destination with bounded writes, then read back row/cell counts, links, and permissions.
   - Report partial completion honestly; do not call Sites placement, sharing, or automation complete from a Sheet creation receipt alone.

3. **Prefer a deterministic no-agent updater**
   - Use a profile-local script for bounded polling, stable source-ID/link dedupe, validation, append-only writes, and machine receipts.
   - Use an LLM agent only for genuinely semantic classification that cannot be made deterministic.
   - Design stdout: empty for no-op, concise bilingual receipt for changes/failures; write a local JSON receipt for every run.

4. **Preflight before registering or enabling cron**
   - Verify the exact scheduler timezone and convert the requested local schedule explicitly.
   - Run the script in the same non-login environment cron will use.
   - Check credential resolution without printing secrets, source API reachability, destination read access, dry-run candidate count, idempotent no-change behavior, and delivery routing.
   - Do not register an enabled job first and discover prerequisites afterward when a dry-run can prove them beforehand.

5. **Smoke-test and verify**
   - Dry-run with an already-populated destination should produce zero duplicate candidates.
   - Test a bounded fixture or known new item where practical, then read back the exact appended values.
   - Verify cron `enabled/state/next_run_at`, saved output, and delivery/failure path separately; scheduler success is not delivery success.

6. **Fail closed on shared-tool or transport failure**
   - Pause/disable an unverified recurring job immediately to prevent repeated failures or noisy alerts.
   - Preserve the job ID and receipt, report the exact layer that failed, and keep already-completed target writes intact.
   - Do not bypass a broken typed wrapper by broad raw-shell/API access unless that fallback is explicitly within the approved envelope.
   - If the approval/handoff mechanism itself depends on the broken shared tool, do not silently repair outside scope. Record that no repair ticket was created and route through an independent admin path.

## Data-integrity checklist

- Deduplicate by stable source identity (for Mattermost, original root ID/permalink), not by title.
- Preserve intentional multi-product/multi-mold roots as one source row.
- Validate every append row shape and link format before write.
- Use file locks or equivalent concurrency control.
- After an ambiguous write, reconcile by destination readback before retrying.
- Never delete or rewrite existing rows when the approved operation is append-only.

## Google Sites prerequisite

A published Sites URL is not proof of editor access. Before promising placement, verify that the authorized account can see/edit the Site artifact or can open the editor without interactive credential handling. If not, deliver the verified Sheet link separately and label Sites placement as blocked rather than complete.
