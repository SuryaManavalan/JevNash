---
name: inventory-purchase-order
description: How to place purchase orders for low-stock SKUs in a warehouse (CRM Inventory module). Load when task involves restocking/reordering SKUs below reorder point.
type: workflow
apps: [crm]
status: verified
wins: 15
losses: 0
last_verified: 2026-09-18
---
1. Go to Inventory, click warehouse ({warehouse_name}) to filter SKUs.
2. Build a table {sku} -> {pack_size} for EVERY SKU where on-hand < reorder point, reading only the filtered warehouse's table. Scroll/page through the WHOLE table before finalizing — missed rows are the #1 cause of failure (a 4th or 5th qualifying SKU has been skipped entirely, unrecorded, in two separate runs). Re-count against any "total SKUs" indicator.
3. Open "New purchase order" (`inventory/reorder`). Form does NOT reset between orders (fields stay filled after submit in some runs, reset in others — always re-check both fields before submitting).
4. One SKU at a time, in strict sequence, for EACH row in your table: type literal {sku}, clear Quantity, type literal {pack_size} (a number, not the SKU string), click "Place order", and confirm SKU+Qty match in the confirmation message BEFORE typing the next SKU into the field.
5. Order EXACTLY the SKUs in your table — no more, no less. Re-verify each SKU is a row in the table right before clicking "Place order".
6. Verify: Inventory → warehouse → "Purchase orders placed today" matches table exactly (same count, no extras, none missing). Fewer orders than qualifying rows = a missed SKU in step 2 or a skipped submit in step 4 (go back and check), not necessarily an ordering slip.
7. Stop immediately once verified — no extra clicks.

## Traps
- Never type a placeholder like "SKU = ?" — resolve real value first (lessons/type-actual-value-not-label.md).
- Wrong SKU = double failure (missed SKU + unwanted extra order).
- An extra/unlisted SKU ordered fails "nothing else ordered" even if all correct SKUs were also ordered — there's no undo, so prevention (step 5) is the only fix.
- Recurring failure mode: undercounting in step 2 — one or more genuinely qualifying SKUs never make it into the table and are never ordered, even though every SKU that IS listed gets ordered correctly. Treat step 2 as highest-risk; don't trust a first pass.
- Confirmed failure mode: typing the FIRST SKU into the field, then typing the SECOND SKU into the same field WITHOUT clicking "Place order" in between silently discards/overwrites the first entry — the first SKU's order never gets placed at all, even though every later SKU submits fine. Always click "Place order" and see the confirmation before moving to the next SKU's fields.
- "Unknown SKU or invalid quantity" error can be transient, not a typo: one run got this error for a correct, verified-exact SKU string, then the SAME string succeeded on a later retry with no changes. Before assuming the SKU is wrong (and re-checking for lookalike chars 5/S, 0/O, 1/I, B/8), try re-submitting the identical value once or twice with fields fully cleared first. Stop retrying after ~2-3 attempts to avoid an infinite loop; don't substitute a "corrected" guess without real evidence the original was wrong.
- Never click "Inventory"/nav mid-form — resets the form, can trigger a nav loop with zero orders placed.
- Don't wander to other modules/warehouses after verifying success — once matched, stop.
</content>
</invoke>
