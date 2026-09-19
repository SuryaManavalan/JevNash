"""Browser tasks as games. The page itself carries the agent overlays: every candidate element is
boxed and heat-coloured by Jev's probability, a glowing cursor travels to the chosen one, and a
HUD says what the agent is doing, so a viewer of the raw browser always knows what is going on."""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from .. import perception
from ..env import GameEnv
from ..events import bus

SCAN_JS = """
() => {

  const out = []; const seen = new Set(); let i = 0;
  // A large fixed layer over the middle of the viewport is a modal: only its contents are usable.
  let blocker = null;
  for (let n = document.elementFromPoint(innerWidth / 2, innerHeight / 2); n && n !== document.body; n = n.parentElement) {
    const s = getComputedStyle(n), b = n.getBoundingClientRect();
    if (s.position === 'fixed' && !n.closest('#jev-layer') && b.width * b.height > innerWidth * innerHeight * 0.3) blocker = n;
  }
  const sel = 'a[href], button, input, select, textarea, summary, [role=button], [role=link], [role=tab], [onclick]';
  // Real sites hide controls inside web components: walk open shadow roots too.
  const deep = (root, acc) => { for (const el of root.querySelectorAll('*')) { el.removeAttribute('data-jev'); if (el.matches(sel)) acc.push(el);
    if (el.shadowRoot) deep(el.shadowRoot, acc); } return acc; };
  for (const el of deep(document, [])) {
    if (el.closest('#jev-layer')) continue;
    if (blocker && !blocker.contains(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || el.disabled) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') continue;
    const tag = el.tagName.toLowerCase();
    let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label')
                || el.title || el.name || '').trim().replace(/\\s+/g, ' ').slice(0, 70);
    const named = el.getAttribute('aria-label') || el.title;
    if (named && [...text].length <= 2) text = named.slice(0, 70);  // icon-only control: use its accessible name
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const lab = el.labels && el.labels[0] ? el.labels[0].innerText.trim() : '';
      text = (lab || el.placeholder || el.name || el.id || text).slice(0, 70);
    }
    if (!text) continue;
    const row = el.closest('tr, li');
    if (row && tag !== 'input' && tag !== 'select' && tag !== 'textarea')
      text += ' (in row: ' + row.innerText.trim().replace(/\\s+/g, ' ').slice(0, 70) + ')';
    const key = tag === 'a' ? 'a|' + el.href.split('#')[0] : tag + '|' + text + '|' + i;
    if (seen.has(key)) continue; seen.add(key);
    el.setAttribute('data-jev', i);
    out.push({i, tag, text, type: el.type || '', checked: !!el.checked, value: el.value || '',
              options: tag === 'select' ? [...el.options].map(o => o.text) : []});
    i++;
  }
  return out;
}
"""

OVERLAY_JS = """
([marks, chosen, label]) => {
  let layer = document.getElementById('jev-layer');
  if (!layer) {
    layer = document.createElement('div'); layer.id = 'jev-layer';
    layer.innerHTML = `<style>
      #jev-layer{position:absolute;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none;
        font:600 11px ui-monospace,monospace}
      #jev-layer .box{position:absolute;border-radius:5px;box-sizing:border-box;transition:all .3s}
      #jev-layer .tag{position:absolute;top:-15px;left:-2px;padding:1px 5px;border-radius:4px;
        color:#04121a;white-space:nowrap}
      #jev-layer .chosen{animation:jevpulse .7s ease-in-out infinite alternate}
      @keyframes jevpulse{from{box-shadow:0 0 6px 2px #39ffd0,0 0 0 0 #39ffd055}
        to{box-shadow:0 0 26px 8px #39ffd0,0 0 0 9px #39ffd022}}
      #jev-cursor{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
        background:radial-gradient(circle,#fff 0 18%,#39ffd0 30%,#39ffd000 70%);
        box-shadow:0 0 22px 9px #39ffd0aa;transition:left .55s cubic-bezier(.2,.8,.2,1),top .55s cubic-bezier(.2,.8,.2,1)}
      #jev-hud{position:fixed;right:14px;bottom:14px;max-width:440px;padding:9px 13px;border-radius:10px;
        background:#06141dee;color:#c9fff2;border:1px solid #39ffd0;box-shadow:0 0 18px #39ffd066;
        font:600 12px ui-monospace,monospace}
      #jev-frame{position:fixed;inset:0;border:3px solid #39ffd0;box-shadow:inset 0 0 28px #39ffd088}
    </style><div id="jev-frame"></div><div id="jev-boxes"></div>
    <div id="jev-cursor" style="left:40px;top:40px"></div><div id="jev-hud"></div>`;
    document.documentElement.appendChild(layer);
  }
  const boxes = layer.querySelector('#jev-boxes'); boxes.innerHTML = '';
  const sx = scrollX, sy = scrollY;
  for (const m of marks) {
    const el = document.querySelector(`[data-jev="${m.i}"]`); if (!el) continue;
    const r = el.getBoundingClientRect();
    const hot = Math.min(1, m.p * 1.6), hue = 200 - 40 * hot;
    const b = document.createElement('div'); b.className = 'box' + (m.i === chosen ? ' chosen' : '');
    Object.assign(b.style, {left: r.left + sx - 3 + 'px', top: r.top + sy - 3 + 'px',
      width: r.width + 6 + 'px', height: r.height + 6 + 'px',
      border: `${m.i === chosen ? 3 : 1.5}px solid hsla(${hue},100%,60%,${.25 + .75 * hot})`,
      background: `hsla(${hue},100%,55%,${.04 + .22 * hot})`});
    if (m.show) { const t = document.createElement('span'); t.className = 'tag';
      t.style.background = m.i === chosen ? '#39ffd0' : `hsl(${hue},100%,70%)`;
      t.textContent = (m.i === chosen ? '▶ ' : '') + Math.round(m.p * 100) + '%'; b.appendChild(t); }
    boxes.appendChild(b);
  }
  layer.querySelector('#jev-hud').textContent = label;
  const target = document.querySelector(`[data-jev="${chosen}"]`);
  if (target) {
    target.scrollIntoView({block: 'center', behavior: 'instant'});
    const r = target.getBoundingClientRect(), c = layer.querySelector('#jev-cursor');
    c.style.left = r.left + scrollX + Math.min(r.width / 2, 60) + 'px';
    c.style.top = r.top + scrollY + r.height / 2 + 'px';
  }
}
"""

ACTION_RE = re.compile(r'^(click|type|select|enter) \[(\d+)\]\s*(.*)$', re.S)


class BrowserEnv(GameEnv):
    """One browser task. Subclasses define the task text, start URL and success check."""

    max_steps = 12
    vision = False  # True: add a LlamaParse reading of the rendered page to every observation
    harvest = False  # True: IDs, amounts, emails and phones seen on visited pages become typeable
    can_finish = False  # True: the agent decides when it is done
    text_budget = 900

    def __init__(self, seed: int | None = None, headed: bool = False):
        self.rng = random.Random(seed)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=not headed)
        self.page: Page = self.browser.new_page(viewport={"width": 1180, "height": 760})
        self.elements: list[dict] = []
        self.task, self.inputs = "", []
        self.reset()

    # --- task definition (override) ---
    def new_task(self) -> tuple[str, str, list[str]]:
        """Returns (task text, start url, candidate strings that may be typed)."""
        raise NotImplementedError

    def succeeded(self) -> bool:
        raise NotImplementedError

    def _eval(self, js: str, arg=None):
        """page.evaluate that survives the real web: a navigation can destroy the context mid-call."""
        for attempt in range(4):
            try:
                return self.page.evaluate(js, arg) if arg is not None else self.page.evaluate(js)
            except Exception:
                if attempt == 3:
                    raise
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
                self.page.wait_for_timeout(400)

    # --- GameEnv ---
    def reset(self) -> None:
        self.task, url, self.inputs = self.new_task()
        self.steps, self.finished, self.message = 0, False, "Task started."
        self.pool: list[str] = list(self.inputs)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception:  # slow sites: settle for the first bytes and let the page keep loading
            self.page.goto(url, wait_until="commit", timeout=45000)
            self.page.wait_for_timeout(3000)
        self._snap()

    def _snap(self, settle: bool = False) -> None:
        try:
            if settle:
                self.page.wait_for_load_state("load", timeout=5000)
            bus.shot = self.page.screenshot(type="jpeg", quality=55)
            bus.emit("shot", url=self.page.url)
        except Exception:
            pass

    VALUE_RE = re.compile(r"[A-Z]{1,4}-\d{3,6}|\d+\.\d{2}|[\w.]+@[\w.]+\.\w+|\b\d{3}-\d{4}\b|\b\d{1,6}\b")

    def observe(self) -> dict[str, Any]:
        # A modal's text comes first: it is what the user is actually looking at.
        text = self._eval("""() => { const d = document.querySelector('[role=dialog]');
            const m = document.querySelector('main, #content, body');
            return (d ? 'DIALOG: ' + d.innerText + ' | PAGE BEHIND: ' : '') + (m.innerText || '') }""")
        if self.harvest:
            for v in self.VALUE_RE.findall(self.task + " " + text):
                if v in self.pool:
                    self.pool.remove(v)
                self.pool.append(v)  # most recently seen last
            self.pool = self.pool[-150:]
        seen = {}
        if self.vision and perception.available():
            # Hide the agent's own overlays so they are not read back as part of the world.
            self.page.evaluate("() => { const l = document.getElementById('jev-layer'); if (l) l.style.display = 'none' }")
            frame = self.page.screenshot(type="png")
            self.page.evaluate("() => { const l = document.getElementById('jev-layer'); if (l) l.style.display = '' }")
            seen = {"screen_as_seen": perception.parse_bytes(frame, ".png", "screen")[:1500]}
        return {
            **seen,
            "task": self.task,
            "url": self.page.url,
            "page_title": self.page.title(),
            "page_text_excerpt": re.sub(r"\s+", " ", text)[:self.text_budget],
            "form_state": [
                {"field": e["text"], "value": e["value"]} if e["type"] not in ("checkbox", "radio")
                else {"field": e["text"], "checked": e["checked"]}
                for e in self._eval(SCAN_JS)
                if e["tag"] in ("input", "select", "textarea")
            ],
            "steps_left": self.max_steps - self.steps,
            "message": self.message,
        }

    def legal_actions(self) -> list[str]:
        self.elements = self._eval(SCAN_JS)
        actions = []
        for e in self.elements:
            if e["tag"] == "select":
                actions += [f'select [{e["i"]}] {e["text"]} = "{o}"' for o in e["options"]]
            elif e["tag"] == "textarea" or (e["tag"] == "input" and e["type"] in (
                    "text", "search", "email", "tel", "url", "number", "")):
                if e["value"]:  # many search boxes have no button: Enter submits what was typed
                    actions.append(f'enter [{e["i"]}] press Enter in {e["text"]}')
                if self.harvest:  # two-stage: choose the field now, the value in a second Choice
                    actions.append(f'type [{e["i"]}] {e["text"]} = ?')
                else:
                    actions += [f'type [{e["i"]}] {e["text"]} = "{s}"' for s in self.pool if s != e["value"]]
            else:
                state = " (checked)" if e["checked"] else ""
                actions.append(f'click [{e["i"]}] {e["text"]}{state}')
        if self.can_finish:
            actions.append("finish: the whole task is complete, stop here")
        return actions

    def value_candidates(self) -> list[str]:
        return list(reversed(self.pool))  # most recently seen first

    def render(self) -> dict[str, Any]:
        return {"kind": "browser", "url": self.page.url, "task": self.task}

    def show_decision(self, probabilities: dict[str, float], action: str, label: str) -> None:
        by_id: dict[int, float] = {}
        for a, p in probabilities.items():
            m = ACTION_RE.match(a)
            if m:
                by_id[int(m.group(2))] = by_id.get(int(m.group(2)), 0.0) + p
        top = set(sorted(by_id, key=by_id.get, reverse=True)[:6])
        m = ACTION_RE.match(action)
        chosen = int(m.group(2)) if m else -1
        marks = [{"i": i, "p": p, "show": i in top or i == chosen} for i, p in by_id.items()]
        try:
            self.page.evaluate(OVERLAY_JS, [marks, chosen, label])
            self.page.wait_for_timeout(650)  # let the cursor glide so viewers can follow it
            self._snap()
        except Exception:
            pass

    def step(self, action: str) -> dict[str, Any]:
        self.steps += 1
        if action.startswith("finish"):
            self.finished, self.message = True, "Agent declared the task complete."
            return {}
        m = ACTION_RE.match(action)
        info: dict[str, Any] = {}
        try:
            verb, idx, rest = m.group(1), m.group(2), m.group(3)
            loc = self.page.locator(f'[data-jev="{idx}"]').first
            value = rest.rsplit('= "', 1)[-1].rstrip('"') if "= " in rest else ""
            if verb == "click":
                try:
                    loc.click(timeout=2500)
                except Exception:  # covered or off-screen elements: fall back to a DOM click
                    loc.evaluate("el => el.click()")
            elif verb == "type":
                loc.fill(value, timeout=4000)
            elif verb == "enter":
                loc.press("Enter", timeout=4000)
            else:
                loc.select_option(label=value, timeout=4000)
            self.page.wait_for_timeout(350)  # give a navigation time to start before waiting on it
            self.page.wait_for_load_state("domcontentloaded", timeout=8000)
            said = self.page.evaluate("""() => { const t = document.querySelector(
                '.toast, .alert, .notice, .flash, [role=status], [role=alert]'); return t ? t.innerText.trim().slice(0, 140) : '' }""")
            self.message = f"Did: {action}" + (f" -> app replied: {said!r}" if said else "")
        except Exception as e:
            self.message = f"Rejected action: {action!r}"
            info["error"] = f"{self.message} ({type(e).__name__})"
        if self.succeeded():
            self.finished, self.message = True, "Task completed successfully."
        elif self.steps >= self.max_steps:
            self.finished, self.message = True, "Out of steps. Task failed."
        self._snap(settle=True)
        return info

    def done(self) -> bool:
        return self.finished

    def outcome(self) -> float:
        return 1.0 if self.succeeded() else 0.0

    def close(self) -> None:
        self.browser.close()
        self.pw.stop()


class OrderFormEnv(BrowserEnv):
    """Confined web task: a local multi-step order form with a randomised target each episode."""

    max_steps = 10
    SIZES, TOPPINGS = ["Small", "Medium", "Large"], ["Mushrooms", "Olives", "Peppers", "Onions"]
    NAMES = ["Ada", "Grace", "Linus", "Edsger"]

    def new_task(self):
        self.want = {
            "size": self.rng.choice(self.SIZES),
            "topping": self.rng.choice(self.TOPPINGS),
            "name": self.rng.choice(self.NAMES),
        }
        task = (f'Order one {self.want["size"]} item with {self.want["topping"]} only, '
                f'for the name "{self.want["name"]}", then place the order.')
        url = (Path(__file__).parent / "webtasks" / "order.html").as_uri()
        return task, url, self.NAMES

    def succeeded(self) -> bool:
        got = self.page.evaluate("() => window.__order || null")
        return got == {"size": self.want["size"], "toppings": [self.want["topping"]],
                       "name": self.want["name"]}


class WikiRaceEnv(BrowserEnv):
    """Open-web task: reach a target article by clicking links only."""

    max_steps = 8
    RACES = [("Tic-tac-toe", "Mathematics"), ("Espresso", "Italy"), ("Penguin", "Antarctica"),
             ("Guitar", "Spain"), ("Chess", "India"), ("Volcano", "Earth")]

    def new_task(self):
        start, self.target = self.rng.choice(self.RACES)
        task = (f'Reach the encyclopedia article titled "{self.target}" by clicking links. '
                "Prefer links in the article body that lead toward broader, related topics.")
        return task, f"https://en.wikipedia.org/wiki/{start}", []

    def legal_actions(self) -> list[str]:
        # Article-body links only: chrome, footers and edit links are never useful for the race.
        self.page.evaluate("""() => document.querySelectorAll(
            '#mw-panel, nav, footer, .vector-header-container, .mw-editsection, .reflist, .navbox, '
            + '.vector-page-toolbar, .vector-column-start, .catlinks, .mw-jump-link, #p-lang-btn, .sidebar'
          ).forEach(e => e.remove())""")
        return [a for a in super().legal_actions() if a.startswith("click")]

    def succeeded(self) -> bool:
        return self.page.title().startswith(self.target + " - ")


class OpenWebEnv(BrowserEnv):
    """Any browser task on any real site. There is no programmatic success check on the open web, so Jev
    judges completion from the final page. With `workstream=True` the v2 roles run it (Librarian, foreman,
    notes) and the foreman decides when to stop.

    Guardrails for the live internet, enforced here rather than trusted to a model:
      - navigation is confined to an allowlist of domains (default: the start URL's domain)
      - password, payment and e-mail fields are never offered for typing
      - controls that buy, pay, sign in, register, subscribe, delete or post are never offered
    """

    max_steps = 15
    UNSAFE = re.compile(r"\b(buy|pay|checkout|check out|purchase|order now|add to (cart|basket|bag)|sign ?in|log ?in|sign ?up|"
                        r"register|subscribe|donate|delete|remove|post|publish|send|submit|accept all|create account)\b", re.I)
    SECRET_FIELD = re.compile(r"password|passcode|card|cvv|cvc|iban|ssn|e-?mail", re.I)

    def __init__(self, task: str, url: str, inputs: list[str] | None = None, workstream: bool = False,
                 allow: list[str] | None = None, **kw):
        from urllib.parse import urlparse

        from ..clients import JevClient

        self._task, self._url = task, url
        # Strings the agent may type: given explicitly, plus anything quoted in the task.
        self._inputs = list(dict.fromkeys((inputs or []) + re.findall(r'"([^"]+)"', task)))
        self.jev, self.p_done, self._judged = JevClient(), 0.0, True
        host = urlparse(url).hostname or ""
        self.allow = [d.lower() for d in (allow or [".".join(host.split(".")[-2:])])]
        if workstream:
            self.can_finish, self.harvest, self.text_budget, self.max_steps = True, False, 2200, 30
        super().__init__(**kw)

    def new_task(self):
        self.p_done = 0.0
        return self._task, self._url, self._inputs

    def _allowed(self) -> bool:
        from urllib.parse import urlparse

        host = (urlparse(self.page.url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.allow)

    def legal_actions(self) -> list[str]:
        keep = []
        for a in super().legal_actions():
            label = a.split("] ", 1)[-1]
            if a.startswith("type") and self.SECRET_FIELD.search(label):
                continue
            if a.startswith("click") and self.UNSAFE.search(label):
                continue
            keep.append(a)
        return keep

    def step(self, action: str) -> dict[str, Any]:
        self._judged = False
        info = super().step(action)
        if not self._allowed():  # left the allowlist: come straight back and say so
            away = self.page.url
            self.page.go_back(wait_until="domcontentloaded")
            self.message = f"Blocked: {away.split('/')[2]} is outside the allowed sites. Returned to the previous page."
            info["error"] = self.message
        return info

    def judge(self) -> float:
        if not self._judged:
            obs = {k: v for k, v in self.observe().items() if k not in ("message", "steps_left")}
            obs["notes_taken_by_agent"] = getattr(self, "notes", [])
            ans = self.jev.ask(obs, {"done": {
                "type": "noul",
                "instructions": "Has `task` been fully completed, judging by the current page and `notes_taken_by_agent`?",
                "criteria": {"true": "The page shows the end state the task asked for",
                             "false": "More steps are still needed, or the page shows something else"},
            }}, purpose="judge_done")
            self.p_done, self._judged = ans["done"]["noul"], True
            bus.emit("judge", p_done=self.p_done)
        return self.p_done

    def succeeded(self) -> bool:
        return False if self.can_finish else self.judge() >= 0.7

    def report(self) -> dict[str, bool]:
        return {f"Jev judges the task complete (p={self.judge():.2f})": self.judge() >= 0.7}

    def outcome(self) -> float:
        return 1.0 if self.judge() >= 0.7 else 0.0


class CanvasGameEnv(BrowserEnv):
    """Pixel-only game: the board is drawn on a canvas, so the only way to see it is to look.
    Rows are A-C top to bottom, columns 1-3 left to right; the agent is never told that."""

    max_steps = 6
    vision = True

    def new_task(self):
        return ("Win the game shown on screen.",
                (Path(__file__).parent / "webtasks" / "canvas.html").as_uri(), [])

    def succeeded(self) -> bool:
        return self.page.evaluate("() => window.__result || null") == "win"

    def done(self) -> bool:
        return self.finished or bool(self.page.evaluate("() => window.__result || null"))

    def outcome(self) -> float:
        return {"win": 1.0, "draw": 0.5}.get(self.page.evaluate("() => window.__result || null"), 0.0)


class SuiteEnv(BrowserEnv):
    """Enterprise workstreams across the Acme Suite (see jevnash/playground). The agent must say
    when it is finished; the score is the fraction of task checks that hold, zero if it did harm."""

    max_steps = 60
    text_budget = 2200
    harvest = True
    can_finish = True

    def __init__(self, family: str | None = None, chaos: bool = False, **kw):
        from ..playground.suite import Suite

        self.suite, self.family, self.chaos, self.episode_no = Suite(), family, chaos, 0
        super().__init__(**kw)

    def new_task(self):
        from ..playground.tasks import FAMILIES

        names = [self.family] if self.family else list(FAMILIES)
        self.task_family = names[self.episode_no % len(names)]
        self.episode_no += 1
        world = self.suite.reset(self.rng.randint(0, 10**9), self.chaos)
        text, self.checks = FAMILIES[self.task_family](world)
        return text, f"http://127.0.0.1:{self.suite.port}/", []

    def report(self) -> dict[str, bool]:
        return {name: bool(fn(self.suite.world)) for name, fn in self.checks}

    def succeeded(self) -> bool:
        return False  # only the agent's own "finish" or the step cap ends an episode

    def outcome(self) -> float:
        r = self.report()
        if not all(ok for name, ok in r.items() if name.startswith("harm")):
            return 0.0
        work = [ok for name, ok in r.items() if not name.startswith("harm")]
        return sum(work) / len(work)


class PaintEnv(BrowserEnv):
    """Drawing challenge: replicate a reference picture in a given style with an MS-Paint-like app.
    The adapter is the quantisation layer: the canvas is addressed as named cells, the reference is
    described to the planner as a grid of palette colours, and the score is pixel similarity."""

    can_finish = True
    text_budget = 400
    STYLES = {
        "pixel-art": (16, 40, "Pixel art: flat colours only, everything snapped to whole cells, built from filled boxes and single pencil cells. No gradients."),
        "anime": (32, 70, "Anime / cel style: large flat colour regions with clean shapes (ovals, boxes), then thin black or dark outlines drawn with the line tool around the main shapes."),
        "photo-realistic": (32, 120, "Photo-realistic: approximate smooth gradients with several bands of neighbouring shades, soften edges, add highlights and shadows. Fidelity to the reference matters most."),
    }
    SCENES = ["sunset", "house", "portrait"]

    def __init__(self, style: str | None = None, scene: str | None = None, **kw):
        self.only_style, self.only_scene, self.episode_no, self.cells = style, scene, 0, set()
        super().__init__(**kw)

    def new_task(self):
        styles = [self.only_style] if self.only_style else list(self.STYLES)
        self.style = styles[self.episode_no % len(styles)]
        self.scene = self.only_scene or self.SCENES[(self.episode_no // len(styles)) % len(self.SCENES)]
        self.episode_no += 1
        self.grid, self.max_prims, _ = self.STYLES[self.style]
        self.max_steps = self.max_prims * 5 + 10
        self.cells = set()
        url = (Path(__file__).parent / "webtasks" / "paint.html").as_uri() + f"?grid={self.grid}&scene={self.scene}"
        return f"Replicate the reference picture on your canvas in {self.style} style, then finish.", url, []

    def _rows(self, canvas: str) -> list[str]:
        """A picture as text: nearest palette colour per cell, run-length encoded per row."""
        n = self.grid
        rgb, pal = self.page.evaluate(f"() => [thumb('{canvas}', {n}), palette]")
        pal = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in pal.items()}
        rows = []
        for r in range(n):
            names = [min(pal, key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], rgb[(r * n + c) * 3:(r * n + c) * 3 + 3])))
                     for c in range(n)]
            runs, start = [], 0
            for c in range(1, n + 1):
                if c == n or names[c] != names[start]:
                    runs.append(f"{names[start]} {start + 1}-{c}" if c - start > 1 else f"{names[start]} {c}")
                    start = c
            rows.append((chr(65 + r) if r < 26 else "A" + chr(65 + r - 26)) + ": " + ", ".join(runs))
        return rows

    def _regions(self) -> list[str]:
        """Shape-level perception: connected regions of one palette colour, biggest first, each described as the
        stroke that would paint it. Per-row colour runs alone make planners draw stripes."""
        n = self.grid
        rgb, pal = self.page.evaluate(f"() => [thumb('ref', {n}), palette]")
        pal = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in pal.items()}
        name = [[min(pal, key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], rgb[(r * n + c) * 3:(r * n + c) * 3 + 3])))
                 for c in range(n)] for r in range(n)]
        cell = lambda r, c: (chr(65 + r) if r < 26 else "A" + chr(65 + r - 26)) + str(c + 1)
        seen, out = set(), []
        for r0 in range(n):
            for c0 in range(n):
                if (r0, c0) in seen:
                    continue
                colour, stack, comp = name[r0][c0], [(r0, c0)], []
                seen.add((r0, c0))
                while stack:
                    r, c = stack.pop()
                    comp.append((r, c))
                    for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                        if 0 <= rr < n and 0 <= cc < n and (rr, cc) not in seen and name[rr][cc] == colour:
                            seen.add((rr, cc))
                            stack.append((rr, cc))
                rs, cs = [p[0] for p in comp], [p[1] for p in comp]
                top, bot, left, right = min(rs), max(rs), min(cs), max(cs)
                fill = len(comp) / ((bot - top + 1) * (right - left + 1))
                corners = sum((r, c) in set(comp) for r in (top, bot) for c in (left, right))
                box = f'from cell "{cell(top, left)}" to cell "{cell(bot, right)}"'
                if len(comp) <= 2:
                    shape = f'tiny: pencil at cell "{cell(*comp[0])}"'
                elif fill >= 0.85:
                    shape = f"solid box: rect {box}"
                elif 0.55 <= fill < 0.9 and corners == 0 and bot - top >= 2 and right - left >= 2:
                    shape = f"round blob: ellipse {box}"
                else:  # slopes, arcs, L-shapes: one rect per row span, which reads as a clean staircase
                    spans, run = [], None  # consecutive rows with the same extent merge into one box
                    for r in range(top, bot + 2):
                        cols = sorted(c for rr, c in comp if rr == r)
                        ext = (cols[0], cols[-1]) if cols else None
                        if run and ext == run[1]:
                            continue
                        if run:
                            spans.append(f'rect from cell "{cell(run[0], run[1][0])}" to cell "{cell(r - 1, run[1][1])}"')
                        run = (r, ext) if ext else None
                    shape = "irregular (slope/arc), paint row by row: " + "; ".join(spans[:24])
                out.append((len(comp), f'{colour}, {len(comp)} cells - {shape}'))
        return [text for _, text in sorted(out, reverse=True)]

    def _rules(self, limit: int) -> str:
        n = self.grid
        colours = ", ".join(self.page.evaluate("() => Object.keys(palette)"))
        return (f"Style: {self.STYLES[self.style][2]}\n"
                f"Canvas: {n}x{n} cells, rows A.. top to bottom, columns 1..{n} left to right; cell \"C4\" = row C, column 4.\n"
                f"Tools: pencil (one cell), line (two cells), rect = filled box (two corner cells), ellipse = filled oval inside the box "
                f"given by two corner cells, fill = bucket. Colours: {colours}.\n"
                f"Plan limit: at most {limit} subgoals (this overrides the usual limit). Each subgoal is ONE stroke, written exactly as: "
                f"Draw <tool> in colour \"<colour>\" from cell \"<cell>\" to cell \"<cell>\" (pencil/fill: at cell \"<cell>\"). "
                f"Later strokes paint over earlier ones: large background areas first, details last. The line tool is ONLY for thin "
                f"outlines - never fill an area with lines. Round things are ellipses, not lines or boxes. Paint only what is in the "
                f"reference: no invented highlights, borders or decorations.\n")

    def briefing_material(self) -> str:
        return ("DRAWING TASK MATERIAL\n" + self._rules(self.max_prims)
                + "Shapes found in the reference, biggest first (paint them in this order; merge neighbouring regions of "
                "similar colour if you are short of strokes):\n- " + "\n- ".join(self._regions()[:self.max_prims])
                + "\n\nThe same picture cell by cell, for checking (row: colour columns):\n" + "\n".join(self._rows("ref")))

    def repair_material(self) -> str | None:
        """Closed loop: what the canvas still gets wrong, row by row, for a short corrective pass."""
        want, have = self._rows("ref"), self._rows("c")
        wrong = [f"{w}   <- currently {h.split(': ', 1)[1]}" for w, h in zip(want, have) if w != h]
        if self.similarity() >= 0.9 or not wrong:
            return None
        return ("DRAWING REPAIR MATERIAL\nThe first pass is on the canvas. Plan ONLY corrective strokes for the rows below.\n"
                + self._rules(max(8, self.max_prims // 3)) + "Rows that are still wrong (row: what it should be <- what it is):\n"
                + "\n".join(wrong))

    TOOL_WORDS = {"rect": "rect", "rectangle": "rect", "box": "rect", "ellipse": "ellipse", "oval": "ellipse",
                  "circle": "ellipse", "line": "line", "pencil": "pencil", "dot": "pencil", "fill": "fill", "bucket": "fill"}

    def intents(self, subgoal: str) -> list[tuple[str, str]] | None:
        """A stroke is a fixed sequence of intents; the harness binds each one to a control. Planners phrase
        strokes differently, so this looks for the three things that matter instead of one sentence shape."""
        text = subgoal.lower()
        tool = next((self.TOOL_WORDS[w] for w in re.findall(r"[a-z]+", text) if w in self.TOOL_WORDS), None)
        colours = sorted(self.page.evaluate("() => Object.keys(palette)"), key=len, reverse=True)
        colour = next((c for c in colours if re.search(rf"\b{re.escape(c)}\b", text)), None)
        cells = re.findall(r"\b([A-Z]{1,2}\d{1,2})\b", subgoal)
        if not (tool and colour and cells):
            return None
        two_point = tool in ("rect", "ellipse", "line")
        return [("drawing tool", tool), ("colour", colour), ("cell", cells[0])] + (
            [("cell", cells[1] if len(cells) > 1 else cells[0])] if two_point else [])

    def focus(self, subgoal: str) -> None:
        self.cells = set(re.findall(r"\b([A-Z]{1,2}\d{1,2})\b", subgoal))

    def legal_actions(self) -> list[str]:
        keep = []
        for a in super().legal_actions():
            m = re.search(r"\] cell ([A-Z]{1,2}\d{1,2})$", a)
            if not m or not self.cells or m.group(1) in self.cells:  # only the cells the current stroke names
                keep.append(a)
        return keep

    def similarity(self) -> float:
        mine, ref = self.page.evaluate("() => [thumb('c', 32), thumb('ref', 32)]")
        err = sum(abs(a - b) for a, b in zip(mine, ref))
        blank = sum(abs(255 - b) for b in ref)
        return max(0.0, 1 - err / blank)

    def report(self) -> dict[str, bool]:
        s = self.similarity()
        return {f"similarity {s:.2f} >= {t}": s >= t for t in (0.5, 0.7, 0.85)}

    def succeeded(self) -> bool:
        return False

    def outcome(self) -> float:
        return round(self.similarity(), 3)
