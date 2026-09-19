# Brain index

- [[apps/bookshop]] (app-map, verified, 15w/0l) — Simple bookshop catalog site - book title, price, stock status shown directly on listing/detail pages. Load for any book price/stock lookup task.
- [[apps/crm]] (app-map, verified, 44w/10l) — Navigating the CRM customer database - search, disambiguate duplicate names, edit customer fields (phone, tier). Load for any customer-record-update task.
- [[apps/hackernews]] (app-map, candidate, 0w/0l) — Navigating Hacker News front page and story comment pages; use for tasks asking to read/report a story's title, points, or comments.
- [[apps/helpdesk]] (app-map, verified, 37w/2l) — Navigating the Helpdesk ticket list - finding tickets by ID, opening them, editing priority/status/notes. Load for any ticket-update task.
- [[apps/mdn]] (app-map, candidate, 1w/0l) — MDN Web Docs navigation. Covers finding the site search box and reaching reference pages. Load for tasks that search MDN or read API reference pages.
- [[apps/python-docs]] (app-map, candidate, 0w/0l) — Navigating docs.python.org - searching for a module/topic and opening its library page. Use for tasks about finding Python API/module info.
- [[apps/wikipedia]] (app-map, candidate, 0w/0l) — Navigating Wikipedia search to open an article and read infobox facts (height, dates, etc). Load for tasks that search Wikipedia for an article.
- [[lessons/type-actual-value-not-label]] (lesson, verified, 16w/5l) — When typing into ANY input field, the typed text must be the literal resolved task value (e.g. an email, SKU, quantity, customer name), never the field's label, a placeholder like "Field = ?", or an unresolved variable. Applies to any type action, any app.
- [[workflows/inventory-purchase-order]] (workflow, verified, 15w/0l) — How to place purchase orders for low-stock SKUs in a warehouse (CRM Inventory module). Load when task involves restocking/reordering SKUs below reorder point.
- [[workflows/refund-invoice]] (workflow, verified, 21w/0l) — Issue a refund in Billing for a customer's invoice and log it on a Helpdesk ticket (note + Solved). Load for any refund/ticket-resolution task spanning Billing+Helpdesk(+CRM).
- [[workflows/ticket-priority-by-customer-tier]] (workflow, verified, 18w/0l) — Apply a priority policy to tickets based on each ticket's customer's CRM tier (e.g. Enterprise -> Urgent). Load for cross-app helpdesk+CRM policy tasks.
- [[workflows/void-duplicate-invoice]] (workflow, verified, 6w/0l) — Customer billed twice - find their billing account via CRM, then in Billing void the duplicate (higher-numbered) invoice, leave the original and all else untouched.
