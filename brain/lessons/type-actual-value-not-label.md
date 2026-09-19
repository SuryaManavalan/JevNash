---
name: type-actual-value-not-label
description: When typing into ANY input field, the typed text must be the literal resolved task value (e.g. an email, SKU, quantity, customer name), never the field's label, a placeholder like "Field = ?", or an unresolved variable. Applies to any type action, any app.
type: lesson
apps: [crm, desk, inventory, billing]
status: verified
wins: 16
losses: 5
last_verified: 2026-09-18
---
Failure pattern observed (x4, all scored 0): the executor typed literal placeholder text —
"Find customer = ?", "SKU = ?", "Quantity = ?", "Invoice number or billing account = ?" — into an
input field instead of the actual data value. This produced garbage/empty search results and full
task failures. Once this happens, runs tend to spiral: repeated "?" searches, then aimless
clicking between workspace tabs (Customers/Billing/Helpdesk/Inventory) hoping to stumble onto the
right page, burning all remaining steps without ever resolving the value.

Rule: before issuing a `type` action, resolve and substitute the real data value for the task
(e.g. the actual {customer_name}, {sku}, {quantity}, {email}, {invoice_number}) into the field
text. Never type the field's own label, a bare "?", or any other unresolved placeholder. If the
value isn't known yet, go look it up first (e.g. read the ticket/inventory list, or a page/record
that shows it) — do not type a guess or placeholder just to make progress, and do not start
bouncing between top-level workspace tabs as a substitute for finding the value.

Verify: after typing, re-read the field's actual content and confirm it equals the intended real
value, not a label or "?". If wrong, clear and retype with the resolved value before submitting.
</content>
