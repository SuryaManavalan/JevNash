---
name: crm
description: Navigating the CRM customer database - search, disambiguate duplicate names, edit customer fields (phone, tier). Load for any customer-record-update task.
type: app-map
apps: [crm]
status: verified
wins: 44
losses: 10
last_verified: 2026-09-18
---
1. Dismiss "What's new" dialog if shown (Maybe later).
2. Click "Customers" workspace.
3. Use the "Find customer" search box (searches by name or email) and click 🔍.
   - Type the ACTUAL {email} value into the box, e.g. "jane@doe.com" - never type the label or a
     placeholder like "Find customer = ?". A failed run typed the literal placeholder text and never
     found the record (see lessons/type-actual-value-not-label.md).
   - When multiple customers share the same name, search by {email} directly instead of name to disambiguate, or check each result's email before opening.
4. Click "View" on the correct row (matches by email) to open the record, URL like crm/c/{id}.
5. Click "Edit" to enter edit mode (crm/c/{id}/edit).
6. Update fields: Phone, Tier (dropdown), etc.
7. Click "Save customer".
8. After save you land back on crm/c/{id}. A confirmation is implied by returning to the record view (no separate banner seen); consider record shown = saved.

Trap: after saving, don't click into unrelated tabs like "Contact" unless needed - task is already done once Save succeeds.
