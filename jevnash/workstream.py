"""Long-task control. Three roles around Jev's per-tick choice:

  Librarian (smart LLM + brain tools)  once per task: searches the brain, returns briefing + outline
  Foreman   (cheap LLM, no tools)      every few ticks: reads the live screen, keeps the notes,
                                       names the next subgoal, and is the only one who may say "finished"
  Jev                                  every tick: picks the UI action for the current subgoal

Envs that hand the planner complete material up front (e.g. a drawing) run a static plan instead of
a foreman: the Librarian's outline is the plan and Jev tracks progress through it.
"""

from __future__ import annotations

import re

from .budget import budget
from .events import bus

FOREMAN = """You are the foreman of a web-task agent. A fast policy clicks one UI control per step toward the
subgoal you give it; it cannot plan, and it forgets every page once it leaves it. Look at the task, the outline,
the notes, what has been done, and the CURRENT screen, then return ONE JSON object and nothing else:
{"notes": [new facts from this screen the task will need later: ids, names, emails, amounts, statuses, which
           rows qualify and which do not. Facts only - no to-dos, no advice. [] if nothing new],
 "values": [exact strings from the screen or task that may have to be typed into a field later],
 "subgoal": "the ONE next concrete outcome, reachable in 1-4 UI actions. Put in \\"quotes\\" ONLY the exact text that
             must be typed into a field (never button names or option labels). Never a loop, never a mental step.",
 "finished": true only when EVERY part of the task has been done AND the results list shows each was saved}
`changes_confirmed_by_app` lists every change the app has acknowledged (applied, saved, issued, placed...). That is
proof: verification subgoals are forbidden. Never re-open, re-list or re-check a record whose change is confirmed.
The moment every change the task requires is in that list (and records that must stay untouched were not edited),
set finished=true. Trust what the app replied over intentions. If the last subgoal is not achieved yet, give it again,
reworded for the current screen. If the data you need is not in the screen text, look at `controls_on_screen`: expanders ("More", "Details"), tabs
and menus hide things. If the agent is going in circles, choose a different route."""

VERIFY = re.compile(r"^\W*(verify|confirm|check|review|ensure|validate|make sure)\b|\bverify\b|double.check|re-?open", re.I)
TODO = re.compile(r"^\W*(need|still|must|should|todo|to do|remember|policy|next)\b", re.I)


class Workstream:
    def __init__(self, harness, env):
        self.h, self.env = harness, env
        self.static = hasattr(env, "briefing_material")
        self.plan: list[str] = []
        self.step = 0
        self.briefing, self.pages = "", []
        self.notes: list[str] = []
        self.subgoal: str | None = None
        self.on_subgoal = self.ticks = self.rescues = self.foreman_calls = 0
        self.finished = False
        self.read_urls: set[str] = set()
        self.repairs = 0
        self.version = 0

    # ---- start ---------------------------------------------------------------------------------
    def start(self) -> None:
        obs = self.env.observe()
        bus.emit("thinking", who="librarian")
        material = self.env.briefing_material() if self.static else ""
        # A fixed plan is only as good as its planner, so static envs always use the tier that was asked for.
        b = self.h.librarian.brief(obs.get("task", ""), obs, material, tier=self.h.librarian.tier if self.static else None)
        if self.static and not b.get("plan"):  # a fixed-plan task cannot start without a plan: ask once more
            b = self.h.librarian.brief(obs.get("task", ""), obs, material, tier=self.h.librarian.tier)
        if hasattr(self.env, "intents") and b.get("plan"):
            bad = [p for p in b["plan"] if not self.env.intents(str(p))]
            if len(bad) > 0.3 * len(b["plan"]):  # the adapter cannot execute this plan: show the planner why, once
                bus.emit("replan", reason=f"{len(bad)} of {len(b['plan'])} subgoals not executable")
                b = self.h.librarian.brief(obs.get("task", ""), obs, material + "\n\nFORMAT ERROR in your previous plan: these "
                                           f"subgoals could not be executed: {bad[:4]}. Every subgoal must name one tool, one colour "
                                           "and explicit cells, exactly in the required sentence form.", tier=self.h.librarian.tier)
        self.plan, self.briefing, self.pages = b.get("plan", []), b.get("briefing", ""), b.get("pages_used", [])
        if self.static and self.plan:
            self.subgoal = self.plan[0]
        self.publish()

    def publish(self, rescued: bool = False) -> None:
        bus.emit("plan", plan=self.plan if self.static else [self.subgoal or "…"], step=self.step if self.static else 0,
                 briefing=self.briefing, pages=self.pages, rescued=rescued, notes=self.notes)

    # ---- per tick ------------------------------------------------------------------------------
    def context(self, obs: dict, history: list[dict]) -> dict:
        if not self.static and self.subgoal is None:
            self.foreman(obs, history)
        if self.static and hasattr(self.env, "plan_progress"):
            # The adapter can count finished plan units itself: exact, and one less question for Jev.
            self.finished = self.env.plan_progress() >= len(self.plan)
            self.step = min(self.env.plan_progress(), len(self.plan) - 1)
            self.subgoal = self.plan[self.step]
        if hasattr(self.env, "focus") and self.subgoal:  # before the menu is enumerated for this tick
            self.env.focus(self.subgoal)
        ws = {"current_subgoal": self.subgoal, "briefing": self.briefing, "notes": self.notes}
        if self.static and hasattr(self.env, "plan_progress"):
            ws |= {"plan_position": f"subgoal {self.step + 1} of {len(self.plan)}", "counted": True}
        elif self.static:
            lo = max(0, self.step - 1)  # a window of the plan: cheaper and less distracting than all of it
            ws |= {"plan": self.plan[lo:self.step + 4], "plan_position": f"subgoal {self.step + 1} of {len(self.plan)}",
                   "done_subgoals": self.plan[lo:self.step]}
        return ws

    def shape(self, actions: list[str]) -> list[str]:
        """Finishing is never Jev's call in foreman mode, and only at the last subgoal of a static plan."""
        if hasattr(self.env, "pool"):  # quoted values in the subgoal become typeable - unless they name a control
            labels = {a.split("] ", 1)[-1].split(" (in row")[0].strip().lower() for a in actions}
            self.env.pool = [v for v in self.env.pool if v.lower() not in labels]
            for v in re.findall(r'"([^"]{1,60})"', self.subgoal or ""):
                if v.lower() in labels:
                    continue
                if v in self.env.pool:
                    self.env.pool.remove(v)
                self.env.pool.append(v)
        may_finish = self.static and self.step >= len(self.plan) - 1 and (
            not hasattr(self.env, "plan_progress") or self.env.plan_progress() >= len(self.plan))
        return [a for a in actions if may_finish or not a.startswith("finish")] or actions

    def repair(self) -> bool:
        """After a fixed plan has run, an adapter that can measure the residual gets up to two corrective passes."""
        if self.repairs >= 2 or not hasattr(self.env, "repair_material") or not budget.allows_llm("escalate"):
            return False
        material = self.env.repair_material()
        if not material:
            return False
        self.repairs += 1
        obs = self.env.observe()
        bus.emit("thinking", who="librarian")
        b = self.h.librarian.brief(obs.get("task", ""), obs, material, tier=self.h.librarian.tier)
        extra = [p for p in b.get("plan", []) if self.env.intents(str(p))]
        if not extra:
            return False
        self.plan += extra
        self.subgoal, self.finished = self.plan[self.step], False
        self.publish(rescued=True)
        return True

    def macro(self, actions: list[str]) -> list[str] | None:
        """Intent macros: when the adapter can parse the current subgoal into intents, each intent is bound
        to a menu option - by exact label, from the binding cache, or by asking Jev once - and the whole
        subgoal is replayed without per-click model calls."""
        if not (self.static and hasattr(self.env, "intents")) or self.step >= len(self.plan):
            return None
        intents = self.env.intents(self.plan[self.step])
        if not intents:
            return []  # unparseable subgoal: skip it rather than improvise
        binds, out = self.h.cache.setdefault("bind", {}), []
        label = lambda a: a.split("] ", 1)[-1]
        for kind, phrase in intents:
            exact = [a for a in actions if label(a).lower() == f"{kind} {phrase}".lower()]
            key = f"{kind}|{phrase}"
            if exact:
                out.append(exact[0])
                continue
            if key not in binds:
                controls = [a for a in actions if not label(a).lower().startswith("cell ") and not a.startswith("finish")]
                keys = {f"o{i}": a for i, a in enumerate(controls)}
                ans = self.h.jev.ask({"wanted": {"kind": kind, "name": phrase}}, {"bind": {
                    "type": "choice",
                    "instructions": "Which control selects the `wanted.kind` called `wanted.name`?",
                    "criteria": {**{k: label(a) for k, a in keys.items()}, "other": "No control does this"},
                }}, purpose="bind")["bind"]
                best = max(keys, key=lambda k: ans["probabilities"].get(k, 0))
                if ans["confidence"] < 0.6:  # never cache a guess
                    bus.emit("bind", kind=kind, phrase=phrase, control=None, confidence=ans["confidence"])
                    return []
                binds[key] = label(keys[best])
                bus.emit("bind", kind=kind, phrase=phrase, control=binds[key], confidence=ans["confidence"])
            hit = [a for a in actions if label(a) == binds[key]]
            if not hit:
                return []
            out.append(hit[0])
        return out

    def after_decision(self, d, obs: dict, history: list[dict]) -> bool:
        """Returns True when the subgoal changed and Jev should choose again."""
        x = d.extras
        if self.static:
            progress = x.get("progress") or {}
            if progress:
                best = max(progress, key=progress.get)
                at = int(best[1:]) + max(0, self.step - 1)
                if at > self.step and progress[best] >= 0.5:
                    self.step, self.on_subgoal = min(at, len(self.plan) - 1), 0
                    self.subgoal = self.plan[self.step]
                    self.publish()
                    return True
            return False
        new_page = (x.get("noteworthy") or 0) >= 0.6 and obs.get("url") not in self.read_urls
        if (x.get("subgoal_done") or 0) >= 0.7 or self.on_subgoal >= 4 or new_page:
            before = self.subgoal
            self.foreman(obs, history)
            return self.finished or self.subgoal != before
        return False

    def foreman(self, obs: dict, history: list[dict]) -> None:
        if not budget.allows_llm("escalate"):
            return
        self.read_urls.add(obs.get("url"))
        self.foreman_calls += 1
        confirmed = [f'{h["action"]} -> {h["result"].split("app replied:")[-1].strip()}'
                     for h in history if "app replied" in str(h.get("result"))]
        payload = {
            "task": obs.get("task"), "outline": self.plan, "briefing": self.briefing, "notes": self.notes,
            "changes_confirmed_by_app": confirmed, "results": history[-10:], "last_subgoal": self.subgoal,
            "steps_left": obs.get("steps_left"),
            "screen": {k: obs.get(k) for k in ("url", "page_title", "page_text_excerpt", "form_state")},
            # What can actually be clicked: collapsed sections, tabs and menus hide data the text does not show.
            "controls_on_screen": [a.split("] ", 1)[-1][:60] for a in (self.env.legal_actions() or [])[:45]],
        }
        try:
            out = self.h.llm.json(FOREMAN, payload, purpose="foreman", tier="cheap", max_tokens=700)
            if confirmed and not out.get("finished") and VERIFY.search(str(out.get("subgoal", ""))):
                # A second opinion under the rule it just broke: name a remaining change, or finish.
                payload["rejected_subgoal"] = {"subgoal": out.get("subgoal"), "why": "verification is forbidden: "
                                               "name a CHANGE that is still missing, or set finished=true"}
                out = self.h.llm.json(FOREMAN, payload, purpose="foreman", tier="cheap", max_tokens=700)
        except Exception as e:
            bus.emit("error", where="foreman", error=str(e)[:200])
            return
        fresh = [str(n)[:170] for n in out.get("notes", []) if not TODO.match(str(n)) and str(n) not in self.notes]
        self.notes = (self.notes + fresh[:6])[-24:]
        self.env.notes = self.notes  # adapters that judge completion themselves may want what was learned
        for v in out.get("values", [])[:10]:
            if hasattr(self.env, "pool") and str(v) not in self.env.pool:
                self.env.pool.append(str(v))
        self.finished = bool(out.get("finished"))
        if out.get("subgoal"):
            if str(out["subgoal"]) != self.subgoal:
                self.version += 1  # a new subgoal makes earlier actions fair game again
            self.subgoal, self.on_subgoal = str(out["subgoal"]), 0
        self.publish()

    def after_step(self, obs_after: dict, history: list[dict], noops: set) -> None:
        self.ticks += 1
        self.on_subgoal += 1
        # Looping shows up as few distinct actions over many steps; long tasks that keep moving are not stuck.
        looping = len(history) >= 12 and len({h["action"] for h in history[-12:]}) <= 5
        stuck = self.on_subgoal >= 9 if self.static else looping
        if not (stuck or len(noops) > self.rescues * 3 + 2) or self.rescues >= 2 or self.env.done() \
                or not budget.allows_llm("escalate"):
            return
        self.rescues, self.on_subgoal = self.rescues + 1, 0
        bus.emit("thinking", who="librarian")
        fix = self.h.librarian.unstick(obs_after.get("task", ""), self.plan, self.step,
                                       [h["action"] for h in history[-10:]], obs_after, self.notes)
        self.briefing = fix.get("briefing") or self.briefing
        self.pages = list(dict.fromkeys(self.pages + fix.get("pages_used", [])))
        if fix.get("plan"):
            self.plan = (self.plan[:self.step] if self.static else []) + fix["plan"]
            self.subgoal = self.plan[self.step] if self.static else None  # foreman re-reads the new outline
        self.publish(rescued=True)
