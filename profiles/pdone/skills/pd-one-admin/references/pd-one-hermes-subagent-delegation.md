# PD One Hermes Sub-Agent Delegation

Use this reference when Andy/admin asks whether PD One should use sub-agents, how to use Hermes `delegate_task`, or how to simplify PD One multi-agent plumbing.

## Core lesson

Prefer Hermes-native `delegate_task` before building new multi-agent infrastructure. `delegate_task` already spawns short-lived child agents with isolated fresh context, restricted toolsets, and their own terminal sessions; only the final summary returns to PD One.

PD One should remain the single permission-bearing orchestrator:

- resolve exact Mattermost sender id and scope before delegation;
- decide whether delegation is needed;
- pass a complete, least-privilege context packet;
- restrict toolsets explicitly;
- verify worker receipts before final response;
- own external sends, approvals, writes, config/policy changes, Drive ACLs, and restarts.

## Always cross-check Hermes docs first

For Hermes plumbing/config/delegation/tooling work, load `hermes-agent` and check the relevant Hermes docs before designing new wrappers. The user explicitly wants built-in Hermes methods used where possible and dislikes reinventing machinery that `delegate_task`, `execute_code`, cron, or toolsets already cover.

## What to pass to `delegate_task`

Single worker shape:

```python
delegate_task(
    goal="Specific objective",
    context="Everything the worker needs; it knows nothing from the parent chat",
    toolsets=["terminal", "file"]
)
```

Parallel shape:

```python
delegate_task(tasks=[
    {"goal": "Research A", "context": "Scope and required output", "toolsets": ["web"]},
    {"goal": "Review code B", "context": "Paths, constraints, tests", "toolsets": ["terminal", "file"]},
])
```

Include in context:

- requester authorization summary and relevant scopes only;
- exact task objective, paths, source IDs, known errors, and expected output;
- allowed files/data/toolsets and whether edits are permitted;
- forbidden actions: identity guessing, raw private/policy disclosure, external sends, config/policy/source-system/Drive ACL changes, gateway restarts;
- escalation rule: return `NEEDS_ORCHESTRATOR` for broader access, approval, or user clarification;
- required receipts: paths, commands, test results, diffs, URLs/IDs, unresolved risks.

## Skills and `delegate_task`

`delegate_task` does not take a `skills=[...]` argument. Subagents do not inherit the parent’s loaded skill contents. If a worker must use a skill:

1. include the `skills` toolset;
2. name the required skills explicitly in the context;
3. for high-risk rules, paste the relevant skill excerpt into context instead of relying on discovery.

Example:

```python
delegate_task(
    goal="Review this implementation plan for Hermes-native simplification",
    context="Load and follow: subagent-driven-development, writing-plans, hermes-agent. Check for overengineering and missing verification.",
    toolsets=["file", "skills"]
)
```

## Delegate only when useful

Good uses:

- parallel independent workstreams;
- research/synthesis that would flood context;
- fresh-context code/debug/security review;
- bounded implementation subtasks;
- independent quality/spec review.

Avoid delegation for:

- single deterministic tool calls;
- mechanical loops better handled by `execute_code`;
- tasks needing user clarification;
- durable long-running work that should use cron or background terminal;
- unknown/inactive/out-of-scope requesters;
- high-impact side effects PD One must perform and verify directly.

## Simplified rollout pattern

Start manually:

1. PD One authorizes and scopes the request.
2. PD One calls `delegate_task` with complete context and restricted toolsets.
3. Worker returns findings/receipts only.
4. PD One verifies receipts and gives the final answer.

## Receipt verification

- Read each claimed artifact path before you report the lane done. A child summary can name a path that was never written.
- Match every script id, sheet id, and file id in the artifact to the id in the task. A registered sibling project is not the requested target. A child will read a registered sibling when the requested id is absent from the registry.
- If the user asked to consume a named model meter, report the child model in the receipt. A child can run a different model than the parent turn.
- "Do all" means the lanes already named. Do not add an unnamed source folder, a wiki write, or a live patch.
- A decision pack recommends. It does not execute, approve, or reject a ticket.
- An in-progress ticket with no kanban mapping is stuck. Recommend reconcile. Do not recommend a second approve.

Only add wrapper scripts, template files, or tests after 5-10 real delegated tasks show repeated boilerplate or recurring mistakes. This avoids overengineering while preserving exact-sender authorization, least privilege, isolated worker context, side-effect gating, and PD One verification.
