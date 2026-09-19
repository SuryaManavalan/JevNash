---
name: ticket-priority-by-customer-tier
description: Apply a priority policy to tickets based on each ticket's customer's CRM tier (e.g. Enterprise -> Urgent). Load for cross-app helpdesk+CRM policy tasks.
type: workflow
apps: [helpdesk, crm]
status: verified
wins: 18
losses: 0
last_verified: 2026-09-18
---
1. For each ticket {T-1, T-2, ...}: jump to it in Helpdesk (Ticket ID field + ➜), click "Customers". This lands on CRM root, NOT pre-filtered — type the customer's name/email into "Find customer", click 🔍, then View.
2. Build a full checklist BEFORE editing: "Ticket X → Tier Z → Action" per ticket. Do the lookup pass for ALL tickets first, in one clean pass — avoid re-searching, retyping garbage, or bouncing Helpdesk↔Customers↔Helpdesk more than once per ticket.
3. Then go to Helpdesk once. For each qualifying ticket, use Ticket ID field + "Go to ticket" to jump directly (works across pagination).
4. On the ticket page: set Priority to Urgent, Apply changes/Save ONCE, confirm "Changes applied", move on immediately to the next qualifying ticket.
5. Leave non-qualifying tickets untouched.
6. Verify only edited tickets: clear Ticket ID, retype exact ID, jump, confirm Priority. Once per ticket.

## Traps
- Don't loop Helpdesk→Customers→Helpdesk; don't re-search an already-looked-up customer.
- Retyping garbage/partial values into search fields (e.g. leftover dialog-button text) is a sign of being lost — stop, use the checklist.
- Lookup alone doesn't complete the task — must actually set Priority and Save for EVERY qualifying ticket, not just the first one found.
- Ticket ID field retains stray text between navigations — always clear and retype fresh.
- After "Changes applied", stop — repeated re-verification/re-Apply wastes steps and can trigger rescues.
- Verify via Ticket ID + Go to ticket, never by paging through Page 1/2/3.
- CRM search sometimes needs Search clicked twice (stale query in URL) — check the URL updated before reading results.
- A "Stay signed in" / session-check dialog can pop up repeatedly mid-lookup — just click it and continue, it's not part of the task data.
- Step budget risk (unconfirmed): a messy lookup phase (wrong-field typing, dialog interruptions, extra Helpdesk/CRM round-trips) can burn enough steps that later qualifying tickets never get edited before the run ends. If N tickets qualify, prioritize applying the edit to each one as soon as its tier is known rather than deferring all edits to the end, especially if the lookup phase already went long.
</content>
</invoke>
