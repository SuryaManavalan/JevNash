"""Acme Suite: four deliberately awkward enterprise web apps sharing one backend.

  /desk       helpdesk    paginated queue, a decoy "Save draft", status only sticks via "Apply changes"
  /crm        CRM         icon-only search, duplicate customer names, details behind tabs
  /billing    billing     refund hidden in an Actions menu + confirm modal, next to a loud "Void" decoy
  /inventory  inventory   unsorted stock table, reorder form on a separate page

The portal greets every session with a cookie banner and a "What's new" modal. State lives in
memory, is rebuilt from a seed, and is inspected by task checkers; the agent only ever sees HTML.
"""

from __future__ import annotations

import html
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

FIRST = ["Maria", "James", "Wei", "Aisha", "Tom", "Elena", "Raj", "Sofia", "Omar", "Lucy"]
LAST = ["Garcia", "Smith", "Chen", "Khan", "Novak", "Rossi", "Patel", "Silva", "Haddad", "Brown"]
TIERS = ["Free", "Team", "Business", "Enterprise"]
SKUS = ["Widget", "Gasket", "Valve", "Bracket", "Sensor", "Cable", "Filter", "Relay", "Hinge", "Motor"]
SUBJECTS = ["Login loop on SSO", "Export is missing rows", "Webhook retries", "Seats question",
            "Cannot change avatar", "API rate limit", "Slow dashboard", "Wrong timezone"]


class World:
    def __init__(self, seed: int):
        r = self.r = random.Random(seed)
        self.customers, self.invoices, self.tickets, self.stock = {}, {}, {}, {}
        self.refunds, self.orders, self.log = {}, [], []
        self.seq = r.randint(4000, 8000)
        names = [f"{f} {l}" for f in FIRST for l in LAST]
        r.shuffle(names)
        for i in range(14):
            name = names[i] if i < 12 else names[i - 12]  # two duplicated names
            cid = f"C-{r.randint(1000, 9999)}"
            slug = name.lower().replace(" ", ".")
            self.customers[cid] = {
                "id": cid, "name": name, "email": f"{slug}{'' if i < 12 else r.randint(2, 9)}@{r.choice(['acme.io', 'globex.com', 'initech.co'])}",
                "phone": f"555-{r.randint(1000, 9999)}", "tier": r.choice(TIERS), "account": f"AC-{r.randint(10000, 99999)}",
            }
        for c in self.customers.values():
            for _ in range(r.randint(1, 3)):
                iid = f"INV-{r.randint(10000, 99999)}"
                self.invoices[iid] = {"id": iid, "account": c["account"], "customer": c["id"], "status": "Paid",
                                      "amount": f"{r.randint(20, 900)}.{r.choice(['00', '50', '99'])}",
                                      "month": r.choice(["Jan", "Feb", "Mar", "Apr"])}
        cids = list(self.customers)
        for i in range(16):
            tid = f"T-{r.randint(100, 999)}"
            self.tickets[tid] = {"id": tid, "customer": r.choice(cids), "subject": r.choice(SUBJECTS), "body": "Please advise.",
                                 "status": r.choice(["Open", "Open", "Pending"]), "priority": r.choice(["Low", "Normal", "High"]),
                                 "notes": []}
        for wh in ["North", "South"]:
            for s in r.sample(SKUS, 7):
                sku = f"{s[:3].upper()}-{r.randint(100, 999)}"
                point = r.randint(10, 60)
                self.stock[sku] = {"sku": sku, "name": s, "warehouse": wh, "on_hand": r.randint(0, 120),
                                   "reorder_point": point, "pack": r.choice([12, 24, 50, 100])}

    def next_id(self, prefix: str) -> str:
        self.seq += self.r.randint(1, 9)
        return f"{prefix}-{self.seq}"


def e(s) -> str:
    return html.escape(str(s))


CSS = """body{font:15px system-ui;margin:0;background:#eef1f5;color:#1c2430}nav{background:#1c2430;padding:10px 18px}
nav a{color:#cfd8e3;margin-right:18px;text-decoration:none}nav b{color:#fff;margin-right:26px}main{padding:22px 28px;max-width:1080px}
table{border-collapse:collapse;width:100%;background:#fff}td,th{border:1px solid #d5dbe3;padding:6px 9px;text-align:left}th{background:#f6f8fa}
.btn,button,input[type=submit]{font:inherit;padding:6px 13px;border-radius:6px;border:1px solid #9aa7b6;background:#fff;cursor:pointer;text-decoration:none;color:#1c2430;display:inline-block}
.primary{background:#2457d6;color:#fff;border-color:#2457d6}.danger{background:#c62828;color:#fff;border-color:#c62828;font-weight:700;padding:9px 20px}
.quiet{border:0;background:none;color:#5b6b7e;font-size:13px}.card{background:#fff;border:1px solid #d5dbe3;border-radius:10px;padding:16px 20px;margin:14px 0}
.tabs a{margin-right:4px;padding:6px 12px;background:#dfe5ec;border-radius:6px 6px 0 0;text-decoration:none;color:#1c2430}.tabs a.on{background:#fff;font-weight:600}
.overlay{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;z-index:50}
.modal{background:#fff;border-radius:12px;padding:24px 28px;width:460px}.cookie{position:fixed;left:0;right:0;bottom:0;background:#fffbe6;border-top:2px solid #e0c200;padding:14px 24px;z-index:40}
.toast{background:#e7f6ec;border:1px solid #6dbb85;padding:10px 14px;border-radius:8px;margin-bottom:14px}label{display:block;margin:9px 0 3px;color:#4a5a6d;font-size:13px}
input[type=text],select,textarea{font:inherit;padding:6px 8px;width:320px;box-sizing:border-box}details{margin-top:10px}"""


def page(title: str, body: str, toast: str = "") -> str:
    nav = ('<nav><b>ACME SUITE</b><a href="/desk">Helpdesk</a><a href="/crm">Customers</a>'
           '<a href="/billing">Billing</a><a href="/inventory">Inventory</a></nav>')
    t = f'<div class="toast">{e(toast)}</div>' if toast else ""
    return f"<!doctype html><meta charset=utf-8><title>{e(title)} · Acme Suite</title><style>{CSS}</style>{nav}<main>{t}{body}</main>"


class Suite:
    def __init__(self) -> None:
        self.world = World(0)
        self.greeted = False
        suite = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _reply(self, body: str, code: int = 200, location: str | None = None):
                self.send_response(303 if location else code)
                if location:
                    self.send_header("Location", location)
                data = body.encode()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                out = suite.route("GET", u.path, q)
                self._reply(*out) if isinstance(out, tuple) else self._reply(out)

            def do_POST(self):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length", 0))
                q = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
                out = suite.route("POST", u.path, q)
                self._reply(*out) if isinstance(out, tuple) else self._reply(out)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reset(self, seed: int) -> World:
        self.world, self.greeted = World(seed), False
        return self.world

    @staticmethod
    def go(location: str):
        return "", 303, location

    # ------------------------------------------------------------------ routing
    def route(self, method: str, path: str, q: dict):
        w = self.world
        parts = [p for p in path.split("/") if p]
        if not parts:
            return self.portal()
        if parts == ["welcome", "dismiss"]:
            self.greeted = True
            return self.go("/")
        app, rest = parts[0], parts[1:]
        try:
            return getattr(self, f"app_{app}")(method, rest, q, w)
        except (KeyError, AttributeError, IndexError):
            return page("Not found", "<h2>404</h2><p>Nothing here.</p>"), 404

    def portal(self):
        body = ('<h1>Good morning</h1><div class="card"><p>Pick a workspace from the bar above.</p>'
                '<p><a class="btn" href="/desk">Open Helpdesk</a> <a class="btn" href="/crm">Open Customers</a> '
                '<a class="btn" href="/billing">Open Billing</a> <a class="btn" href="/inventory">Open Inventory</a></p></div>')
        if not self.greeted:
            body += ('<div class="overlay"><div class="modal" role="dialog"><h2>What\'s new in Acme Suite 9</h2>'
                     '<p>Smarter dashboards, faster exports, and a refreshed look.</p>'
                     '<a class="btn primary" href="/upgrade">Take the tour</a> '
                     '<a class="quiet" href="/welcome/dismiss">Maybe later</a></div></div>'
                     '<div class="cookie">We use cookies. <a class="btn" href="/cookies">Manage preferences</a></div>')
        return page("Home", body)

    def app_upgrade(self, m, rest, q, w):
        return page("Tour", '<h2>Product tour</h2><p>Slide 1 of 14…</p><a class="btn" href="/">Exit tour</a>')

    def app_cookies(self, m, rest, q, w):
        return page("Cookies", '<h2>Cookie preferences</h2><p>47 partners listed.</p><a class="btn" href="/">Back</a>')

    # ------------------------------------------------------------------ helpdesk
    def app_desk(self, m, rest, q, w):
        if not rest:
            pg = int(q.get("page", 1))
            ts = list(w.tickets.values())
            rows = "".join(
                f"<tr><td>{t['id']}</td><td>{e(t['subject'])}</td><td>{e(w.customers[t['customer']]['name'])}</td>"
                f"<td>{t['status']}</td><td>{t['priority']}</td><td><a href='/desk/t/{t['id']}'>Open</a></td></tr>"
                for t in ts[(pg - 1) * 6: pg * 6])
            pages = "".join(f"<a class='btn' href='/desk?page={i}'>{'Page ' + str(i)}</a> " for i in range(1, (len(ts) + 5) // 6 + 1))
            find = ("<form action='/desk/find'><label>Jump to ticket</label><input type=text name=id placeholder='Ticket ID'> "
                    "<button title='Go to ticket'>➜</button></form>")
            return page("Helpdesk", f"<h1>Ticket queue</h1>{find}<table><tr><th>ID</th><th>Subject</th><th>Customer</th><th>Status</th>"
                                    f"<th>Priority</th><th></th></tr>{rows}</table><p>{pages}</p>")
        if rest[0] == "find":
            tid = q.get("id", "").strip().upper()
            return self.go(f"/desk/t/{tid}") if tid in w.tickets else page("Helpdesk", "<h2>No such ticket</h2><a class='btn' href='/desk'>Back to queue</a>")
        t = w.tickets[rest[1]]
        if m == "POST":
            if q.get("do") == "apply":
                t["status"], t["priority"] = q.get("status", t["status"]), q.get("priority", t["priority"])
                if q.get("note", "").strip():
                    t["notes"].append(q["note"].strip())
                w.log.append(("ticket_apply", t["id"]))
                return page("Ticket", self.ticket_body(t, w), "Changes applied.")
            return page("Ticket", self.ticket_body(t, w, q), "Draft saved locally. Not yet applied.")
        return page("Ticket", self.ticket_body(t, w))

    def ticket_body(self, t, w, draft=None):
        c = w.customers[t["customer"]]
        d = draft or {}
        sel = lambda name, opts, cur: f"<select name={name} id={name}>" + "".join(
            f"<option{' selected' if o == d.get(name, cur) else ''}>{o}</option>" for o in opts) + "</select>"
        notes = "".join(f"<li>{e(n)}</li>" for n in t["notes"]) or "<li><i>none</i></li>"
        return (f"<p><a class='quiet' href='/desk'>✕ Close</a></p><h1>{t['id']} · {e(t['subject'])}</h1>"
                f"<div class=card><b>From:</b> {e(c['name'])} &lt;{e(c['email'])}&gt;<p>{e(t['body'])}</p></div>"
                f"<div class=card><h3>Internal notes</h3><ul>{notes}</ul></div>"
                f"<form method=post class=card><label for=status>Status</label>{sel('status', ['Open', 'Pending', 'Solved'], t['status'])}"
                f"<label for=priority>Priority</label>{sel('priority', ['Low', 'Normal', 'High', 'Urgent'], t['priority'])}"
                f"<label for=note>Add internal note</label><textarea name=note id=note rows=2>{e(d.get('note', ''))}</textarea><p>"
                f"<button class=primary name=do value=draft>Save draft</button> <button name=do value=apply>Apply changes</button></p></form>")

    # ------------------------------------------------------------------ crm
    def app_crm(self, m, rest, q, w):
        if not rest:
            term = q.get("q", "").strip().lower()
            hits = [c for c in w.customers.values() if term and (term in c["name"].lower() or term in c["email"].lower())]
            rows = "".join(f"<tr><td>{e(c['name'])}</td><td>{c['tier']}</td><td><a href='/crm/c/{c['id']}'>View</a></td></tr>" for c in hits)
            table = f"<table><tr><th>Name</th><th>Tier</th><th></th></tr>{rows}</table>" if hits else (
                "<p><i>No matches.</i></p>" if term else "<p>Search by name or email to begin. The directory is not browsable.</p>")
            return page("Customers", "<h1>Customers</h1><form><label for=q>Find customer</label><input type=text id=q name=q "
                                     f"value='{e(q.get('q', ''))}' placeholder='Name or email'> <button title='Search'>🔍</button></form><br>{table}")
        c = w.customers[rest[1]]
        tab = rest[2] if len(rest) > 2 else "overview"
        if m == "POST":
            c["phone"], c["tier"] = q.get("phone", c["phone"]).strip(), q.get("tier", c["tier"])
            w.log.append(("crm_update", c["id"]))
            return page("Customer", self.customer_body(c, "edit", w), "Customer saved.")
        return page("Customer", self.customer_body(c, tab, w))

    def customer_body(self, c, tab, w):
        tabs = "".join(f"<a class='{'on' if tab == t else ''}' href='/crm/c/{c['id']}/{t}'>{t.title()}</a>" for t in ["overview", "contact", "edit"])
        if tab == "overview":
            inner = (f"<p><b>Tier:</b> {c['tier']}</p><details><summary>More</summary><p><b>Billing account:</b> {c['account']}</p>"
                     f"<p><b>Customer ID:</b> {c['id']}</p></details>")
        elif tab == "contact":
            inner = f"<p><b>Email:</b> {e(c['email'])}</p><p><b>Phone:</b> {e(c['phone'])}</p>"
        else:
            opts = "".join(f"<option{' selected' if o == c['tier'] else ''}>{o}</option>" for o in TIERS)
            inner = (f"<form method=post action='/crm/c/{c['id']}'><label for=phone>Phone</label><input type=text id=phone name=phone value='{e(c['phone'])}'>"
                     f"<label for=tier>Tier</label><select id=tier name=tier>{opts}</select><p><button class=primary>Save customer</button> "
                     f"<a class=btn href='/crm'>Discard</a></p></form>")
        return f"<h1>{e(c['name'])}</h1><div class=tabs>{tabs}</div><div class=card>{inner}</div>"

    # ------------------------------------------------------------------ billing
    def app_billing(self, m, rest, q, w):
        if not rest:
            term = q.get("q", "").strip().upper()
            hits = [i for i in w.invoices.values() if term and term in (i["id"], i["account"])]
            rows = "".join(f"<tr><td>{i['id']}</td><td>{i['account']}</td><td>{i['month']}</td><td>${i['amount']}</td><td>{i['status']}</td>"
                           f"<td><a href='/billing/i/{i['id']}'>Details</a></td></tr>" for i in hits)
            table = (f"<table><tr><th>Invoice</th><th>Account</th><th>Month</th><th>Amount</th><th>Status</th><th></th></tr>{rows}</table>"
                     if hits else ("<p><i>Nothing found. Search needs an exact invoice number or billing account.</i></p>" if term else ""))
            return page("Billing", "<h1>Billing</h1><form><label for=q>Invoice number or billing account</label>"
                                   f"<input type=text id=q name=q value='{e(q.get('q', ''))}'> <button>Look up</button></form><br>{table}")
        inv = w.invoices[rest[1]]
        view = rest[2] if len(rest) > 2 else ""
        if m == "POST" and view == "refund":
            if q.get("confirm") != "yes":
                return page("Invoice", self.invoice_body(inv, w, "refund"), "Tick the confirmation box to continue.")
            rid = w.next_id("RF")
            w.refunds[rid] = {"id": rid, "invoice": inv["id"], "amount": q.get("amount", "").strip().lstrip("$"), "reason": q.get("reason", "")}
            inv["status"] = "Refunded"
            return page("Invoice", self.invoice_body(inv, w), f"Refund {rid} issued for invoice {inv['id']}.")
        if m == "POST" and view == "void":
            inv["status"] = "Void"
            w.log.append(("void", inv["id"]))
            return page("Invoice", self.invoice_body(inv, w), "Invoice voided.")
        return page("Invoice", self.invoice_body(inv, w, view))

    def invoice_body(self, inv, w, view=""):
        c = w.customers[inv["customer"]]
        refunds = "".join(f"<li>{r['id']}: ${e(r['amount'])} ({e(r['reason'])})</li>" for r in w.refunds.values() if r["invoice"] == inv["id"])
        menu = (f"<div class=card><a class=btn href='/billing/i/{inv['id']}/pdf'>Download PDF</a> <a class=btn href='/billing/i/{inv['id']}/refund'>Refund…</a> "
                f"<a class=btn href='/billing/i/{inv['id']}'>Hide actions</a></div>") if view == "actions" else ""
        modal = ""
        if view == "refund":
            reasons = "".join(f"<option>{o}</option>" for o in ["Select a reason…", "Duplicate charge", "Customer request", "Service outage", "Fraud"])
            modal = (f"<div class=overlay><div class=modal role=dialog><h2>Refund invoice {inv['id']}</h2><form method=post action='/billing/i/{inv['id']}/refund'>"
                     f"<label for=amount>Amount to refund (invoice total ${inv['amount']})</label><input type=text id=amount name=amount>"
                     f"<label for=reason>Reason</label><select id=reason name=reason>{reasons}</select>"
                     "<label><input type=checkbox name=confirm value=yes> I confirm this refund is approved</label>"
                     f"<p><button class=primary>Issue refund</button> <a class=btn href='/billing/i/{inv['id']}'>Cancel</a></p></form></div></div>")
        return (f"<h1>Invoice {inv['id']}</h1><div class=card><p><b>Customer:</b> {e(c['name'])} · <b>Account:</b> {inv['account']}</p>"
                f"<p><b>Amount:</b> ${inv['amount']} · <b>Month:</b> {inv['month']} · <b>Status:</b> {inv['status']}</p>"
                f"<ul>{refunds}</ul></div><form method=post action='/billing/i/{inv['id']}/void' style='display:inline'>"
                f"<button class=danger>VOID INVOICE</button></form> <a class=quiet href='/billing/i/{inv['id']}/actions'>Actions ▾</a>{menu}{modal}")

    # ------------------------------------------------------------------ inventory
    def app_inventory(self, m, rest, q, w):
        if rest and rest[0] == "reorder":
            if m == "POST":
                sku, qty = q.get("sku", "").strip().upper(), q.get("qty", "").strip()
                if sku not in w.stock or not qty.isdigit():
                    return page("Reorder", self.reorder_body(q), "Unknown SKU or invalid quantity.")
                w.orders.append({"sku": sku, "qty": int(qty)})
                return page("Reorder", self.reorder_body({}), f"Purchase order placed: {qty} × {sku}.")
            return page("Reorder", self.reorder_body(q))
        wh = q.get("wh", "")
        items = [s for s in w.stock.values() if not wh or s["warehouse"] == wh]
        rows = "".join(f"<tr><td>{s['sku']}</td><td>{s['name']}</td><td>{s['warehouse']}</td><td>{s['on_hand']}</td>"
                       f"<td>{s['reorder_point']}</td><td>{s['pack']}</td></tr>" for s in items)
        placed = "".join(f"<li>{o['qty']} × {o['sku']}</li>" for o in w.orders) or "<li><i>none yet</i></li>"
        return page("Inventory", "<h1>Stock levels</h1><p><a class=btn href='/inventory?wh=North'>North</a> <a class=btn href='/inventory?wh=South'>South</a> "
                                 "<a class=btn href='/inventory'>All</a> <a class='btn primary' href='/inventory/reorder'>New purchase order</a></p>"
                                 f"<table><tr><th>SKU</th><th>Item</th><th>Warehouse</th><th>On hand</th><th>Reorder point</th><th>Pack size</th></tr>{rows}</table>"
                                 f"<div class=card><h3>Purchase orders placed today</h3><ul>{placed}</ul></div>")

    def reorder_body(self, q):
        return ("<h1>New purchase order</h1><form method=post class=card><label for=sku>SKU</label><input type=text id=sku name=sku "
                f"value='{e(q.get('sku', ''))}'><label for=qty>Quantity</label><input type=text id=qty name=qty value='{e(q.get('qty', ''))}'>"
                "<p><button class=primary>Place order</button> <a class=btn href='/inventory'>Back to stock levels</a></p></form>")
