---
name: refund-invoice
description: Issue a refund in Billing for a customer's invoice and log it on a Helpdesk ticket (note + Solved). Load for any refund/ticket-resolution task spanning Billing+Helpdesk(+CRM).
type: workflow
apps: [billing, helpdesk, crm]
status: verified
wins: 3
losses: 0
last_verified: 2026-09-18
---
1. Open the ticket first (Helpdesk > "Ticket ID" field > jump ➜, url desk/t/{ticket_id}) and note the customer name/email shown.
2. Some ticket pages have a direct "Billing" link/tab that goes straight to the Billing workspace (faster than Helpdesk→Customers→search→View→Billing). Try it before doing a full CRM lookup.
3. If you must use CRM: go to Customers, search by {customer_email} (exact match), click View, find the invoice/billing account number on the customer record itself.
   - TRAP (caused full failure in one run): Billing's search box does NOT accept email or ticket ID - only an exact invoice number or billing account number works.
4. Go to Billing workspace, paste the exact {invoice_number}/{account_number} into "Invoice number or billing account", click Look up.
   - TRAP: the search field can retain a stale value (refund ID, ticket ID, etc.) from a previous action - always confirm/retype the exact value before clicking Look up.
5. Open the matching invoice, click Actions ▾ > Refund (never VOID INVOICE). Set refund to FULL amount, reason = "Customer request" (or {reason} if specified).
   - TRAP (caused partial failure in one run): a "full amount" toggle/preset may not actually populate the amount field with the true invoice total - after selecting it, visually confirm the amount field shows the exact invoice total ($ amount matches what's shown on the invoice) before submitting; if not, type it manually.
   - Check the confirm checkbox if present, submit. Record the resulting {refund_id} shown in the confirmation.
6. Go back to Helpdesk, jump to {ticket_id} again (via Ticket ID field, not by re-searching).
7. Add an internal note containing ONLY the {refund_id} (no other stray data).
8. Set the Status dropdown to Solved and Save/Apply changes.
9. Verify: reopen the ticket, confirm the note contains {refund_id} and Status = Solved. Re-open the invoice to confirm refund amount EXACTLY equals invoice total and reason matches.

Traps:
- Do not loop Customers <-> Billing <-> Helpdesk repeatedly; get the invoice/account number in one visit, then go straight to Billing.
- Billing search requires the exact invoice/account number - never an email or ticket ID.
- Search/input fields can retain stale values from a prior step - always verify/retype before submitting a lookup.
- "Add internal note" is permanent, not a scratchpad; only put the required {refund_id} there.
- "Full amount" preset can silently mismatch the real invoice total - always visually verify the amount field before submitting.
</content>
