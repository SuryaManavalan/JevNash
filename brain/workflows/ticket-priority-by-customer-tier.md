---
name: ticket-priority-by-customer-tier
description: Apply a priority policy to tickets based on each ticket's customer's CRM tier (e.g. Enterprise -> Urgent). Load for cross-app helpdesk+CRM policy tasks.
type: workflow
apps: [helpdesk, crm]
status: verified
wins: 2
losses: 0
last_verified: 2026-09-18
---
1. For each ticket {T-1, T-2, ...}: jump to it in Helpdesk (Ticket ID field + ➜), click "Customers". This lands on CRM root, NOT a pre-filtered page — type the customer's name/email into "Find customer", click 🔍, then View.
2. Build a full checklist BEFORE editing anything: "Ticket X → Tier Z → Action: Urgent / leave", one line per ticket. Do this lookup pass for ALL tickets first.
3. Then go to Helpdesk once. For each qualifying ticket, use the Ticket ID field + "Go to ticket" to jump directly (works across pagination — don't click through Page 1/2 hunting for rows).
4. On the ticket page: set Priority dropdown to Urgent, click Apply changes/Save, confirm the new value, then move to next ticket.
5. Leave non-qualifying tickets untouched.
6. Verify: reopen each qualifying ticket to confirm Priority updated; non-qualifying tickets are visible as unchanged directly on the queue list.

## Traps
- Looping Helpdesk→Customers→Helpdesk→Customers or re-searching an already-looked-up customer wastes many steps.
- Retyping garbage/partial values into "Find customer" or "Ticket ID" is a sign of being lost — stop and use the checklist.
- Identifying qualifying tickets but never actually opening Priority/Save on them — lookup alone doesn't complete the task.
- Editing only some qualifying tickets — apply and verify each one.
- Ticket queue pagination: prefer Ticket ID + "Go to ticket" over scanning pages.
- "Customers" link only opens CRM root, not a per-ticket lookup — one search+View per unique customer.
- The Ticket ID field retains stray leftover text between navigations (e.g. a fragment of the last-typed value) even after visiting other pages; after finishing edits, always clear it and type the exact target ticket ID fresh before clicking "Go to ticket" during verification — don't trust the field's current contents.
- Once all qualifying tickets are edited and confirmed via "Changes applied" messages, avoid extra churn: re-verifying by repeatedly retyping/clearing the Ticket ID field with no clear target wastes many steps (seen: 1 rescue needed from this in an otherwise successful run).
</content>
</invoke>
