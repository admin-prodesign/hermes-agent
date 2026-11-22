# Legacy Case product disambiguation

Use with `references/legacy-case-imports.md` when old Google Sheet `案子` rows are being imported into AppSheet `Case` / `Case_Updates` and legacy product text contains `PD-###` mold/family codes.

## Durable lessons from the dry run

- Legacy `相關產品-統計 All Products` often names a product family/mold, not a single ERP SKU, e.g. `18LH-1桶|PD-217`.
- In `ERP_Data_Combined`, one mold such as `APD-217` can expand to many Product rows by color, material, printing, customer, PCR/special variants, etc. Do **not** pick one SKU arbitrarily.
- Importing all candidate Product SKUs is usually too noisy. Prefer importing high-confidence `Molds` and only importing `Products` where the product row is uniquely and confidently identified.
- For this legacy Case import, user-confirmed person overrides are: `ANDY LIN`, `副總`, and `林耘正` all map to `HR_Employees[PersonID] = DVNSMLZW` unless Andy explicitly overrides it later.

## Read-only product disambiguation workflow

1. Pull product/mold reference rows read-only from the prototype app, usually from `ERP_Data_Combined`:
   - keep rows where `[Type] = "Product"` or `[Type] = "Mold"`.
   - relevant columns include `品       號`, `產品名稱`, `模具編號`, `Friendly Name`, `Type`, and `品質狀態`.
2. Parse legacy product tokens matching `PD-###` and normalize to mold code `APD-###`.
3. For each token:
   - collect Product rows where `ERP_Data_Combined[模具編號] = APD-###`.
   - normalize legacy label and product names for whitespace/full-width punctuation and known wording variants such as `射咀` vs `射嘴`.
   - if exactly one Product row matches the normalized label, mark it `auto_resolved_unique` and add that `品       號` to `Case[Products]`.
   - if multiple Product rows match the same family, mark it `family_ambiguous`; keep `Case[Products]` blank for that token unless Andy reviews the SKU choice.
   - if the mold exists but product names do not match confidently, mark it `mold_products_no_name_match`.
   - if no Product rows exist for the mold, mark it `unresolved_no_products_for_mold`.
   - if no `PD-###` token exists, mark it `free_text_unparsed`.
4. Produce review artifacts:
   - candidate-level CSV/JSON with legacy case, PD code, APD code, legacy label, decision, confidence, recommended product(s), and candidate products.
   - grouped review CSV by `PD-###` + legacy label with case counts and candidate counts so Andy can review common families first.
   - updated dry-run payloads only; no AppSheet writes until explicit approval.
5. Re-run the legacy payload validator after applying product/person overrides.

## Recommended live import policy

- Always import high-confidence `Molds` when resolved.
- Import only `auto_resolved_unique` `Products` unless Andy explicitly approves a manual mapping table.
- Leave `family_ambiguous`, `mold_products_no_name_match`, `unresolved_no_products_for_mold`, and `free_text_unparsed` product tokens blank in `Case[Products]` for the first import.
- Preserve the raw legacy product text in existing description/link/context fields or in review artifacts so future cleanup remains possible.

## Review output interpretation

- High `candidate_count` is not a failure; it usually means the old Sheet recorded a product family rather than a SKU.
- Top ambiguous groups are useful for a manual review pass, but they should not block importing the historical cases if `Molds` are already present.
- Treat product-resolution warnings as data-quality review items, not schema blockers, when the payload validator passes.
