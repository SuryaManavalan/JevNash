---
name: void-duplicate-invoice
description: Customer billed twice - find their billing account via CRM, then in Billing void the duplicate (higher-numbered) invoice, leave the original and all else untouched.
type: workflow
apps: [crm, billing]
status: verified
wins: 6
losses: 0
last_verified: 2026-09-18
---
1. Customers workspace > Find customer, type the exact {email}, Search, click View on the matching row (crm/c/{id}).
2. On the customer record, the nav item labeled "Billing" is NOT a sub-tab of the customer page — clicking it navigates AWAY to the top-level Billing workspace (url becomes "billing", losing the customer context).
3. CONFIRMED FAILURE (3 runs): top-level Billing's search box does NOT accept the customer's {email} OR the CRM customer id (e.g. C-2198) OR the customer's {name} — all return "Nothing found". It wants an exact invoice number or a distinct "billing account" number.
   - The billing account number has NOT been located on Overview or Contact tabs across 3 runs.
   - A "More" expandable section exists on the customer record (separate from the Overview/Contact tabs) that has NOT yet been successfully inspected — clicking it so far has caused navigation away before its contents could be read. Try clicking "More" and then carefully reading what appears in place, without immediately clicking further nav items.
   - Do not keep looping Customers ↔ Billing retrying email/customer-id/name — this wastes many steps and has failed on every attempt so far.
4. Once a working query is found, go to top-level "Billing" workspace, clear search field, enter it, click Find/Search.
5. Read the invoice list. Find two invoices with the same amount in the same month.
6. Open the one with the HIGHER invoice number only. Actions ▾ > Void invoice (never Refund).
7. Confirm via the void confirmation message. Do not open or touch the other invoice or any other invoice.

## Traps
- The "Billing" link visible while on a customer record is the top-level Billing workspace nav item, not a per-customer tab — clicking it discards the open customer record.
- Billing's top search box rejects email, CRM customer id, AND customer name — only exact invoice number or an unidentified "billing account" number works — confirmed 3 times, do not retry these.
- Session-timeout / "Stay signed in" popups can interrupt the flow at any step; dismiss as their own dialog, never type their text into a search field.
- If stuck looping Customers ↔ Billing with no valid query, stop and escalate/report rather than repeating.
- The "More" section on a customer record may hide the billing account number but is unconfirmed/unexplored - clicking it has repeatedly led to navigating away instead of revealing content. Try scrolling or expanding in place rather than treating it as a nav link.
- Void must target the higher invoice number of the duplicate pair; the lower one is the original and must stay untouched.
</content>
