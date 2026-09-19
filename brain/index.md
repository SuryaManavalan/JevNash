# Brain index

- [[apps/crm]] (app-map, verified, 5w/2l) — Navigating the CRM customer database - search, disambiguate duplicate names, edit customer fields (phone, tier). Load for any customer-record-update task.
- [[apps/helpdesk]] (app-map, verified, 3w/2l) — Navigating the Helpdesk ticket list - finding tickets by ID, opening them, editing priority. Load for any ticket-update task.
- [[lessons/type-actual-value-not-label]] (lesson, verified, 9w/2l) — When typing into ANY input field, the typed text must be the literal resolved task value (e.g. an email, SKU, quantity, customer name), never the field's label, a placeholder like "Field = ?", or an unresolved variable. Applies to any type action, any app.
- [[workflows/inventory-purchase-order]] (workflow, verified, 3w/0l) — How to place purchase orders for low-stock SKUs in a warehouse (CRM Inventory module). Load when task involves restocking/reordering SKUs below reorder point.
- [[workflows/refund-invoice]] (workflow, verified, 3w/0l) — Issue a refund in Billing for a customer's invoice and log it on a Helpdesk ticket (note + Solved). Load for any refund/ticket-resolution task spanning Billing+Helpdesk(+CRM).
- [[workflows/ticket-priority-by-customer-tier]] (workflow, verified, 2w/0l) — Apply a priority policy to tickets based on each ticket's customer's CRM tier (e.g. Enterprise -> Urgent). Load for cross-app helpdesk+CRM policy tasks.
