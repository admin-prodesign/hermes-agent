# Controlled sub-agent delegation for PD One

Use this when Andy/admin asks whether PD One should use multi-agent/sub-agent workflows, or when a PD One task is large enough to delegate.

## Recommendation

Prefer a **controlled sub-agent system**, not a free-running autonomous multi-agent swarm.

PD One remains the only conversation owner and permission-bearing orchestrator. Sub-agents are short-lived workers that receive least-privilege task packets and return evidence for PD One to verify before any user-visible success claim.

## Orchestrator responsibilities

PD One must keep these responsibilities in the parent context:

- Resolve exact Mattermost sender-id authorization from the Hermes permission bridge.
- Apply channel/group mention and bilingual rules.
- Decide whether delegation is appropriate.
- Build least-privilege worker context.
- Choose minimal toolsets per worker.
- Enforce approval gates for sends, writes, Drive ACLs, source-system changes, policy/config changes, restarts, and broad log/history searches.
- Independently verify receipts before final reportback.

## Worker classes

Initial safe worker classes:

1. **Research/document synthesis** — read and summarize bounded sources; no authority to send or write production data.
2. **Code/config inspection** — inspect code/config/tests and propose or implement bounded changes; PD One verifies tests and git state.
3. **Operational evidence** — collect deterministic status/log/cache/test evidence; return exact commands, paths, outputs, IDs.
4. **Drafting/bilingual communication** — draft messages/SOPs/announcements; PD One checks policy and sends only after approval.
5. **Reviewer** — spec/security/privacy/quality review; returns PASS or REQUEST_CHANGES with evidence.

## Delegation decision rule

Delegate when the task is research-heavy, parallelizable, benefits from independent review, or has a clear input/output boundary.

Do not delegate when the requester is unknown/unprofiled, the task needs live user clarification, a single deterministic tool call is enough, or the step is an approval decision that PD One must own.

## Standard worker packet

Every worker should receive a self-contained packet:

```text
ROLE: [research/code/evidence/drafting/reviewer]
TASK: [specific objective]
REQUESTER AUTHZ SUMMARY: [allowedForScopedWork, roles, safeScopes, approval gates]
TASK SCOPE: [what is allowed]
OUT OF SCOPE: [what must not be touched]
DATA BOUNDARY: [what data may be read/summarized]
TOOLSETS: [exact allowed toolsets]
REQUIRED OUTPUT: [format, receipts, files, tests]
ESCALATION: Return NEEDS_ORCHESTRATOR if broader access, approval, or user clarification is needed.
```

## Verification pattern

Never trust a sub-agent self-report for side effects. PD One verifies:

- file writes by reading/statting files,
- tests by running them,
- external posts by readback/status IDs,
- git work by `git status`/commit IDs,
- policy/cache work by exact-sender lookup and fail-closed unknown-user checks.

## Rollout order

1. Create reusable worker templates.
2. Add a packet-builder script for least-privilege context.
3. Add smoke tests for admin/employee/unknown/raw-data-redaction/minimal-toolset cases.
4. Pilot read-only delegation first.
5. Add write-capable workflows only after approval and verification patterns are proven.
