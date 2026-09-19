---
name: helpdesk
description: Navigating the Helpdesk ticket list - finding tickets by ID, opening them, editing priority/status/notes. Load for any ticket-update task.
type: app-map
apps: [helpdesk]
status: verified
wins: 36
losses: 2
last_verified: 2026-09-18
---
1. Dismiss "What's new" dialog if shown (Maybe later).
2. Click "Helpdesk" workspace tab. Ticket list is paginated (Page 1/2/3...).
3. To jump straight to a known ticket ID: type the ID into the "Ticket ID" field, then click the ➜ (jump) button next to it. This opens desk/t/{id} directly - much faster than paging through and clicking "Open" on a row.
4. To browse: use "Page N" links; each row shows Ticket ID, Subject, Customer name, Status, Priority, and an "Open" button.
5. On a ticket page (desk/t/{id}): shows Customer name (click "Customers" link to jump to CRM, but this does NOT preserve which ticket you came from - you must remember the ticket ID yourself).
6. To change priority: look for an Edit control on the ticket page, set Priority dropdown, then Save. (Exact click sequence not yet confirmed - previous run never successfully reached this step.)
7. Verify by reopening the ticket and checking the Priority column/value.

Traps:
- The "Add internal note" text field is NOT a scratchpad - do not type customer emails/IDs into it to "remember" them. It saves as a permanent note. Track data yourself (in your own working notes), not by typing into unrelated fields.
- Clicking "Customers" from a ticket takes you to the CRM workspace root, not a pre-filtered view - you still need to search by name/email there.
- Going back and forth between Helpdesk and Customers repeatedly per ticket wastes many steps; instead, look up ALL customer tiers first in one pass through Customers, then go back to Helpdesk once and jump to each ticket needing a change.
- Post-action VERIFICATION is a common failure point: after issuing a refund/making a change and navigating away, typing the ticket ID back into the "Ticket ID" field and clicking jump can land on the WRONG ticket, or the field can retain a stale ID from a previous step/be slow to update. In one run this caused ~15 wasted retype/click cycles and paging through 3 pages before landing on the right ticket, even though the actual task actions had already succeeded and been confirmed ("Changes applied.").
  - Mitigation: after typing the ticket ID, visually confirm the field's value matches before clicking jump; don't click jump repeatedly on stale/wrong values. If jump seems to misbehave, fall back to Page N + row "Open" button, which reliably lands on the correct ticket (row shows ID, Subject, Customer, Status to confirm).
  - If the task's actions already produced "Changes applied." confirmations, treat that as done - do not risk extra edits while merely trying to re-verify; a single confirmed re-open is enough.
</content>
</invoke>
