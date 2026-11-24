# Renderer Migration and Current-Form Evidence

Use this reference when an Office workflow is being piloted against business forms that may have changed over time, or when the process owner changes the required rendering environment.

## Current-form evidence window

1. Translate relative recency language into an explicit inclusive date window using the session date, such as `last three months` → `YYYY-MM-DD through YYYY-MM-DD`.
2. Accept a form as current evidence only when its actual use date is source-backed. A filename year, template revision label, file-copy date, or archive modification timestamp alone may not prove business use.
3. Search only requester-authorized sources. If no eligible form is found, ask for a current-thread upload or another approved source rather than falling back to older examples.
4. Retain older samples and receipts as audit artifacts, but label them superseded. Do not let them drive current fields, routes, signatures, stamps, coordinates, or acceptance criteria.
5. Separate the minimum evidence needed for a workflow-only synthetic test from the broader evidence needed for end-to-end delivery acceptance.

## Renderer migration

A process-owner decision to use LibreOffice/OpenOffice instead of Microsoft Excel, or vice versa, is a qualification-contract change—not a simple tool substitution.

1. Record the chosen renderer and explicitly retire/supersede conflicting pending plans or tickets; do not execute both lanes.
2. Verify the document-class component with a real fixture. Seeing `libreoffice` or `soffice` on PATH does not prove Calc can open XLS/XLSX.
3. Require a nonempty exported PDF, expected file signature, page count, raster count, readable CJK text, and visual inspection of every page.
4. Re-render migrated templates and compiled route fixtures, not only the source XLS. A source 1-page A4 PASS does not cover an XLSX that copies cells/merges/`print_area` but drops paper size, fit-to-page, or CJK fonts (typical failure: Letter, 4-page overflow, tofu).
5. Bind qualification to the exact renderer version/environment, input hash, output/render hash, page count, inspection result, certifier, and timestamp.
6. Keep the old qualification fence fail closed until the new contract is deliberately implemented. Never bypass it by changing a boolean or caller-supplied renderer name.
7. After changing the qualification contract, rerun compiler/engine/runner tests and obtain a fresh independent review. A PASS for the old renderer contract does not cover the new one.

## Two-stage pilot boundary

- **Workflow-only stage:** may test intake, revision handling, exact-user approvals, routing, and compile planning after one eligible current form is frozen. Do not claim qualification or automatically deliver a final Office artifact.
- **End-to-end stage:** additionally requires renderer qualification, visual QA, signed/hash-bound receipt revalidation, disabled-by-default configuration readback, exact delivery readback, and explicit authorization for external posts/uploads.

## Reporting

State separately:

- whether current-form evidence exists;
- whether the renderer can actually process the target file class;
- whether code review passes for the current renderer contract;
- whether workflow-only testing may begin;
- whether end-to-end delivery is still blocked.
