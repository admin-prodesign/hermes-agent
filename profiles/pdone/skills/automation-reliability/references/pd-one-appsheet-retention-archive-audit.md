# PD One AppSheet retention/archive audit

Use for read-only audits of AppSheet retention, archive, definition-history, and evidence-cleanup artifacts.

## Audit sequence

1. Search both the active profile and the backup tree for retention/archive scripts, wrappers, manifests, tests, schedule files, and AppSheet-specific references.
2. Separate three planes explicitly:
   - **Definition/evidence retention:** local `loadApp` snapshots, edit logs, reports, exports, receipts.
   - **Runtime/archive execution:** compressor/archiver wrappers, manifests, locks, and actual dated receipts.
   - **Business-data retention:** AppSheet tables/rows/attachments such as `ActivityLog`, category-specific records, and source data. Do not infer this from local artifact cleanup.
3. For the requested app, verify the exact app ID in scripts/docs/receipts and enumerate the canonical latest/state/history paths.
4. Inspect category-specific references and report counts or visibility-floor numbers as historical evidence only unless a retention rule explicitly binds them to cleanup behavior.
5. Compare the active scheduler configuration with backup scheduler snapshots and actual current receipts. A backup schedule entry plus current manifests is not proof that the active `jobs.json` still owns the job.
6. Read the implementation and tests; run only non-mutating unit tests directly by file path when module discovery is ambiguous. Report the exact command and result.
7. Finish with gaps: missing source-row archival, missing category-specific policy, missing retention holds, missing active schedule ownership, or missing fresh run-as visibility proof.

## Known implementation pattern

The PD One legacy AppSheet compressor commonly targets 7-day-old text evidence with size thresholds, gzips to a sibling `.gz`, verifies decompressed SHA-256 and byte count, then removes the original and records a JSONL manifest. A separate fixed artifact-retention helper may delete files after 30 days. Neither operation archives deployed AppSheet business rows unless a separate source-system workflow exists.

## Reporting requirements

Give exact absolute paths, current behavior, tests, schedule entries, receipts, and gaps. Call out paths outside the requested root when they are invoked by a wrapper (for example `/home/prodesign/.hermes/scripts/...`). Keep historical counts such as `5S Action` or `Mold Movement` separate from retention semantics. If active and backup scheduler state differ, report the discrepancy rather than choosing one silently.
