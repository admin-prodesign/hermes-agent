# 2026-06-11: `Case[Related Case_Updates]` definition dry-run candidate

Use this as session evidence for the class-level pattern in `references/case-updates-cache-performance.md`.

## Trigger

Performance Analyzer sync data showed repeated AppSheet sync failures and high table/VC timing around `Case`, `Case_Updates`, and the reverse-reference virtual column:

- Sync scan: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/scans/perf-scan-20260611T051838Z.json`
- Raw rows: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/scans/perf-raw-20260611T051838Z.json`
- Prompt packet: `/home/prodesign/.hermes/profiles/pdone/logs/appsheet-performance-steward/scans/perf-prompt-packet-20260611T051838Z.txt`

Observed signals from the parsed report:

- `Case_Updates` table p90 around 140s in the early scan and still around 91s in a later scan.
- `Case[Related Case_Updates]` VC p90 around 42s / max around 107s in the early scan and still p90 around 22s / max 90s later.
- Failure messages included AppSheet cache-lock / “very large/slow loading table or cross-table cycle” exceptions for `Case`, `Case_Updates`, and column-set expressions.

## Current definition snapshot

Current expensive VC:

```appsheet
Case[Related Case_Updates]
=REF_ROWS("Case_Updates", "CaseID")
```

Existing physical cache support:

```text
Case[Case_Updates_Cached]
Case[Latest_CaseUpdateID]
Case[Case_Updates_en]
Case[Case_Updates_zh-tw]
```

Existing parent-sync action assignment on `Case_UpdateFromLatestCaseUpdate`:

```appsheet
Case_Updates_Cached =
IF(
  OR(
    ISBLANK([Latest_CaseUpdateID]),
    IN([Latest_CaseUpdateID], [Case_Updates_Cached])
  ),
  [Case_Updates_Cached],
  LIST([Latest_CaseUpdateID]) + [Case_Updates_Cached]
)
```

## Proposed dry-run patch

Only patch the VC formula:

```diff
Case[Related Case_Updates]
- =REF_ROWS("Case_Updates", "CaseID")
+ =[Case_Updates_Cached]
```

Do not patch unrelated bottlenecks, bots, security filters, `Maintenance_Session_Items`, or `ActivityLog_Session_Items` in the same save. Keep this isolated for a clean before/after analyzer comparison.

## Validation checklist

Before any live/promotion claim:

1. Patch a local definition payload only.
2. Submit `/api/saveapp` validation without stable promotion.
3. Require `Success=true`, `IsValid=true`, and `IsRunnable=true`.
4. Confirm no new warnings/errors about `Related Case_Updates`, `Case_Updates_Cached`, type mismatch, EnumList/List coercion, or Ref compatibility.
5. Reload `/api/loadApp` and verify the formula persisted.
6. If direct assignment fails type validation, try `=LIST() + [Case_Updates_Cached]` and validate again.
7. After approval and execution, compare fresh analyzer data against the same table/VC metrics.

## User-facing answer pattern

When asked for the proposed change, lead with the exact diff and the evidence. Keep caveats concise: the only expected risk is AppSheet type compatibility between a `List` VC and a physical `EnumList` ref cache, which is why the first step must be dry-run validation.
