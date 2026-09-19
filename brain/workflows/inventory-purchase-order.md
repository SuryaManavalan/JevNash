---
name: inventory-purchase-order
description: How to place purchase orders for low-stock SKUs in a warehouse (CRM Inventory module). Load when task involves restocking/reordering SKUs below reorder point.
type: workflow
apps: [crm]
status: verified
wins: 3
losses: 0
last_verified: 2026-09-18
---
1. Go to Inventory, click warehouse ({warehouse_name}) to filter SKUs.
2. Build a table {sku} -> {pack_size} for every SKU where on-hand < reorder point, BEFORE ordering anything. Double-check SKU codes character-by-character (easy to mix up similar-looking codes).
3. Open "New purchase order" (`inventory/reorder`). Form does NOT reset between orders.
4. One SKU at a time: type literal {sku} (from table, not memory), clear Quantity and type literal {pack_size}, click "Place order", read confirmation shows correct SKU+Qty (redo if mismatched). Then move to next SKU.
5. Skip SKUs with on-hand >= reorder point; order every qualifying SKU, no more no less.
6. Verify: Inventory → warehouse → "Purchase orders placed today" matches table exactly. Then stop immediately — no extra clicks.

## Traps
- Never type a placeholder like "SKU = ?" — resolve real value first (lessons/type-actual-value-not-label.md).
- Wrong SKU = double failure (missed SKU + unwanted extra order). Re-check against table before typing.
- Never click "Inventory"/nav mid-form — it resets the form and can trigger a nav loop with zero orders placed.
- Don't wander to other modules/warehouses after verifying success — once "Purchase orders placed today" matches, stop; extra clicking between warehouses (e.g. North/South) wastes steps and risks accidental actions but doesn't fail the task if nothing is ordered. Confirmed again in a 4th run: after successful verification, agent still wandered ~10 extra clicks between North/South/Inventory before finishing — task still scored 1.0, but tighten stop condition to save steps.
</content>
