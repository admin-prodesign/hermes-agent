# ActivityLog adoption monitor

## When to Use

Use when asked to watch whether staff are creating a newly required ActivityLog category often enough for it to become a habit.

## Do not count records alone

A count of the new category is not compliance. Name the required trigger, then find a visible proxy event that proves the trigger happened.

For a production-start or work-order-change gate, use `Sub-Category = "MoldMovement_MoldStart"` (開機) on the same equipment and `Shift Date` as the proxy. Say in every digest that an ERP work-order change with no 開機 record is invisible. Do not invent a work-order feed.

## Compare, then flag incompleteness separately

1. Query deployed `ActivityLog` for the previous Taipei `Shift Date`, limited to the new category and the proxy sub-category. Stay inside the owner/server visibility window.
2. Count proxy events and new records per equipment on that shift date. List machines where proxy events exceed new records.
3. Separately list new records that are incomplete: no attachment keys, blank machine, or a blank context field the live form can already store.
4. Dry-run one previous shift date before scheduling. The digest is human-readable text, not raw JSON.

## Delivery and window

Deliver the digest to the requester. Do not message the staff group unless they ask for that follow-up.

Time-box the window. After the end date, emit one final line that the window ended, then stay silent on later ticks.
