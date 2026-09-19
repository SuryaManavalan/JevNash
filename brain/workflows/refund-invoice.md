---
name: refund-invoice
description: Issue a refund in Billing for a customer's invoice and log it on a Helpdesk ticket (note + Solved). Load for any refund/ticket-resolution task spanning Billing+Helpdesk(+CRM).
type: workflow
apps: [billing, helpdesk, crm]
status: verified
wins: 21
losses: 0
last_verified: 2026-09-19
---
1. Open the ticket first (Helpdesk > "Ticket ID" field > jump ➜) and confirm the URL/header shows {ticket_id} before editing - stale field values can send you to the wrong ticket.
   - TRAP: the "Ticket ID" field only accepts real ticket IDs. Typing a {refund_id} or {invoice_number} into it to "find" the ticket fails ("No such ticket") - always re-type the actual {ticket_id}.
2. Try a direct "Billing" link/tab on the ticket page (faster than CRM > Customers > search > View > Billing).
   - TRAP: Billing's search box only accepts an exact invoice number or billing account number - never email or ticket ID.
3. In Billing, paste the exact {invoice_number}/{account_number}, click Look up (retype - field may hold a stale value).
4. Open the invoice, Actions ▾ > Refund (never VOID INVOICE). Reason = "Customer request" (or {reason}).
   - TRAP: "Amount to refund" is NOT pre-filled with the invoice total even though the total is shown nearby - type it explicitly.
   - Check the confirm checkbox (unchecked by default) before "Issue refund". Record {refund_id} from the confirmation.
5. Back in Helpdesk, jump to {ticket_id} again, verify header matches. Add internal note containing ONLY {refund_id}, set Status = Solved, click Update/Apply once.
   - TRAP: after clicking Update, the app may reply "Changes applied." even though the on-screen note/status fields render as empty/reverted - this is a stale display, not a real failure. Do NOT retype the note or re-click Update repeatedly on this basis; each extra submit risks duplicate notes and wastes steps.
   - If genuinely unsure, do exactly ONE fresh reopen of the ticket to confirm note + Status, then stop.
6. Once "Changes applied." has been seen (or reopen confirms note+Solved), the task is done - do not re-verify the invoice too (its refund confirmation already proved success).

Traps recap:
- Ticket ID field rejects refund/invoice IDs - use only the actual ticket ID.
- Fields can retain stale values - retype before submitting (Ticket ID, invoice/account number).
- Internal note is permanent - only put the required {refund_id} there.
- Refund confirm checkbox defaults unchecked.
- "Amount to refund" not auto-filled - type invoice total explicitly.
- "Changes applied." is proof of success even if the form then shows empty/stale fields - trust the confirmation message, not the re-rendered form. Avoid repeated retype+update loops; they cost steps without adding certainty.
</content>
</invoke>
