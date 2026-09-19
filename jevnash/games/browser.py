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
  document.querySelectorAll('[data-jev]').forEach(e => e.removeAttribute('data-jev'));
  const out = []; const seen = new Set(); let i = 0;
  const sel = 'a[href], button, input, select, textarea, [role=button], [role=link], [onclick]';
  for (const el of document.querySelectorAll(sel)) {
    if (el.closest('#jev-layer')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || el.disabled) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') continue;
    const tag = el.tagName.toLowerCase();
    let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label')
                || el.title || el.name || '').trim().replace(/\\s+/g, ' ').slice(0, 70);
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const lab = el.labels && el.labels[0] ? el.labels[0].innerText.trim() : '';
      text = (lab || el.placeholder || el.name || el.id || text).slice(0, 70);
    }
    if (!text) continue;
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

ACTION_RE = re.compile(r'^(click|type|select) \[(\d+)\]\s*(.*)$', re.S)


class BrowserEnv(GameEnv):
    """One browser task. Subclasses define the task text, start URL and success check."""

    max_steps = 12
    vision = False  # True: add a LlamaParse reading of the rendered page to every observation

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

    # --- GameEnv ---
    def reset(self) -> None:
        self.task, url, self.inputs = self.new_task()
        self.steps, self.finished, self.message = 0, False, "Task started."
        self.page.goto(url, wait_until="domcontentloaded")
        self._snap()

    def _snap(self, settle: bool = False) -> None:
        try:
            if settle:
                self.page.wait_for_load_state("load", timeout=5000)
            bus.shot = self.page.screenshot(type="jpeg", quality=55)
            bus.emit("shot", url=self.page.url)
        except Exception:
            pass

    def observe(self) -> dict[str, Any]:
        text = self.page.evaluate("() => (document.querySelector('main, #content, body').innerText || '')")
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
            "page_text_excerpt": re.sub(r"\s+", " ", text)[:900],
            "form_state": [
                {"field": e["text"], "value": e["value"]} if e["type"] not in ("checkbox", "radio")
                else {"field": e["text"], "checked": e["checked"]}
                for e in self.page.evaluate(SCAN_JS)
                if e["tag"] in ("input", "select", "textarea")
            ],
            "steps_left": self.max_steps - self.steps,
            "message": self.message,
        }

    def legal_actions(self) -> list[str]:
        self.elements = self.page.evaluate(SCAN_JS)
        actions = []
        for e in self.elements:
            if e["tag"] == "select":
                actions += [f'select [{e["i"]}] {e["text"]} = "{o}"' for o in e["options"]]
            elif e["tag"] == "textarea" or (e["tag"] == "input" and e["type"] in (
                    "text", "search", "email", "tel", "url", "number", "")):
                actions += [f'type [{e["i"]}] {e["text"]} = "{s}"' for s in self.inputs]
            else:
                state = " (checked)" if e["checked"] else ""
                actions.append(f'click [{e["i"]}] {e["text"]}{state}')
        return actions

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
            else:
                loc.select_option(label=value, timeout=4000)
            self.page.wait_for_timeout(350)  # give a navigation time to start before waiting on it
            self.page.wait_for_load_state("domcontentloaded", timeout=8000)
            self.message = f"Did: {action}"
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
    """Any browser task on any site. With no programmatic success check available, Jev itself
    judges after every step whether the task is complete."""

    max_steps = 15

    def __init__(self, task: str, url: str, inputs: list[str] | None = None, **kw):
        from ..clients import JevClient

        self._task, self._url = task, url
        # Strings the agent may type: given explicitly, plus anything quoted in the task.
        self._inputs = list(dict.fromkeys((inputs or []) + re.findall(r'"([^"]+)"', task)))
        self.jev, self.p_done = JevClient(), 0.0
        super().__init__(**kw)

    def new_task(self):
        self.p_done = 0.0
        return self._task, self._url, self._inputs

    def step(self, action: str) -> dict[str, Any]:
        self._judged = False
        return super().step(action)

    def succeeded(self) -> bool:
        if not getattr(self, "_judged", True):
            obs = {k: v for k, v in self.observe().items() if k not in ("message", "steps_left")}
            ans = self.jev.ask(obs, {"done": {
                "type": "noul",
                "instructions": "Has `task` been fully completed, judging by the current page?",
                "criteria": {"true": "The page shows the end state the task asked for",
                             "false": "More steps are still needed, or the page shows something else"},
            }}, purpose="judge_done")
            self.p_done, self._judged = ans["done"]["noul"], True
            bus.emit("judge", p_done=self.p_done)
        return self.p_done >= 0.85


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
