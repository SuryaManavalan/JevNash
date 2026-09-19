---
name: inventory-purchase-order
description: How to place purchase orders for low-stock SKUs in a warehouse (CRM Inventory module). Load when task involves restocking/reordering SKUs below reorder point.
type: workflow
apps: [crm]
status: verified
wins: 16
losses: 0
last_verified: 2026-09-19
---
1. Go to Inventory, click warehouse ({warehouse_name}) to filter SKUs.
2. Build a table {sku} -> {pack_size} for EVERY SKU where on-hand < reorder point, in the filtered warehouse. Scroll/page the WHOLE table before finalizing — a missed row is the #1 failure cause. Re-count against any "total SKUs" indicator. A run that only found 3 qualifying SKUs when 5 actually qualified (missed 2, never rechecked) scored partial credit — treat any list built from memory/notes as provisional until cross-checked against the full table.
3. Open "New purchase order" (`inventory/reorder`). Form does NOT reliably reset between orders — always re-check both fields before submitting.
4. One SKU at a time, in strict sequence: type literal {sku}, clear Quantity, type literal {pack_size} (number, not SKU), click "Place order", and confirm SKU+Qty in the confirmation message BEFORE typing the next SKU. Typing a second SKU before clicking "Place order" silently discards the first — always confirm before moving on.
5. Order EXACTLY the SKUs in your table — no more, no less. Re-verify each SKU is a table row right before submitting.
6. Verify: Inventory → warehouse → "Purchase orders placed today" matches table exactly (same count, no extras, none missing). Fewer orders than rows = a missed SKU in step 2 or a skipped submit in step 4, not necessarily a slip. ALWAYS run this verify step before declaring done — do not stop just because the SKUs you personally tracked all got confirmations; the tracked set itself may be incomplete.
7. Stop immediately once verified.

## Traps
- Never type a placeholder like "SKU = ?" — resolve real value first (lessons/type-actual-value-not-label.md).
- Wrong/extra SKU ordered = failure with no undo; prevention (step 5) is the only fix.
- "Unknown SKU or invalid quantity" can be transient: retry the identical value once or twice (clearing fields first) before assuming a typo (watch for 5/S, 0/O, 1/I, B/8 lookalikes). Stop after ~3 attempts.
- Never click "Inventory"/nav mid-form — resets form, can loop with zero orders placed.
- Don't wander to other modules/warehouses after verifying success.
- Declaring "task complete" without ever opening the verify screen risks silently missing SKUs that were never even in your qualification table (unconfirmed root cause, but a repeated failure pattern).
</content>
</invoke>
