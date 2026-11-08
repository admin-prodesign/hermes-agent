# Maintenance modes, owned metadata, and test isolation

Use this reference when extending a stateful runner with a bounded status/repair path or a small external metadata projection such as a channel header, topic, dashboard badge, or status line.

## Keep maintenance modes dependency-minimal

A `--status-only`, `--header-only`, repair, or reconciliation mode must validate only what that mode consumes. Construct the API client and load the runner state, then branch into the maintenance path **before** unrelated approver-roster, routing-policy, artifact-conversion, or business-workflow validation.

Regression pattern: invoke the real CLI entry point while replacing an unrelated policy loader with a function that raises. The maintenance command must still succeed. A helper-only unit test does not prove the branch order in `main()`.

## Treat projected metadata as an owned segment

- Reserve and document one exact machine-owned line/pattern.
- Count only explicit active states; do not treat missing/unknown state as active.
- Preserve all unrelated manual bytes, including leading/trailing whitespace and blank lines.
- Remove duplicate machine-owned lines, append one current line, and reject the result before writing if it exceeds the destination limit.
- Skip the write when the exact projected value is unchanged.

For a potentially committed metadata write, use one write attempt followed by exact readback. If the response is lost but readback matches, record reconciled success. If readback is unavailable or mismatched, retain retry/reconciliation state and do not let the auxiliary projection block the primary workflow.

## Isolate tests from production persistence

Importing a production module can leave its log/state paths active even when the network client is fake. Before calling runner functions, monkeypatch every persistent writer (`log_event`, state save, receipts, queues) to a no-op or temporary path. Verify the production artifact before and after the test run (hash, size, or line count) and fail the test harness if it changed.

Minimum metadata-projection matrix:

1. active-state counting and completed/unknown exclusion;
2. exact preservation of manual whitespace/blank lines;
3. duplicate owned-line cleanup;
4. destination length limit;
5. unchanged no-write path;
6. exactly one write plus expected readbacks;
7. definite write failure plus mismatched readback;
8. post-commit response loss plus successful reconciliation;
9. readback exception;
10. maintenance CLI independence from unrelated policy/config loaders.

## Protect new files in pruning backup mirrors

When a backup sync copies an allowlist and prunes everything else, committing a new test/reference is not sufficient: the next sync can delete it. Add the new durable path to the backup allowlist before or with the first commit. After the scheduled/manual sync, verify the file still exists in the mirror and on the remote branch. In dirty shared worktrees, stage only reviewed paths and inspect the cached diff before committing.
