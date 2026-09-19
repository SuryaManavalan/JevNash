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
 "subgoal": "the ONE next concrete outcome, reachable in 1-4 UI actions, with exact values in \\"quotes\\" and the
             control to use if the screen shows it. Never a loop, never a mental step.",
 "finished": true only when EVERY part of the task has been done AND the results list shows each was saved}
Trust `results` (what the app replied) over intentions. If the last subgoal is not achieved yet, give it again,
reworded for the current screen. If the agent is going in circles, choose a different route."""

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

    # ---- start ---------------------------------------------------------------------------------
    def start(self) -> None:
        obs = self.env.observe()
        bus.emit("thinking", who="librarian")
        material = self.env.briefing_material() if self.static else ""
        b = self.h.librarian.brief(obs.get("task", ""), obs, material)
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
        if hasattr(self.env, "focus") and self.subgoal:
            self.env.focus(self.subgoal)
            actions = [a for a in self.env.legal_actions() if a in set(actions)] or actions
        if hasattr(self.env, "pool"):  # quoted values in the subgoal become typeable
            for v in re.findall(r'"([^"]{1,60})"', self.subgoal or ""):
                if v in self.env.pool:
                    self.env.pool.remove(v)
                self.env.pool.append(v)
        may_finish = self.static and self.step >= len(self.plan) - 1 and (
            not hasattr(self.env, "plan_progress") or self.env.plan_progress() >= len(self.plan))
        return [a for a in actions if may_finish or not a.startswith("finish")] or actions

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
        if (x.get("subgoal_done") or 0) >= 0.7 or self.on_subgoal >= 6 or new_page:
            before = self.subgoal
            self.foreman(obs, history)
            return self.finished or self.subgoal != before
        return False

    def foreman(self, obs: dict, history: list[dict]) -> None:
        if not budget.allows_llm("escalate"):
            return
        self.read_urls.add(obs.get("url"))
        self.foreman_calls += 1
        try:
            out = self.h.llm.json(FOREMAN, {
                "task": obs.get("task"), "outline": self.plan, "briefing": self.briefing, "notes": self.notes,
                "results": history[-12:], "last_subgoal": self.subgoal, "steps_left": obs.get("steps_left"),
                "screen": {k: obs.get(k) for k in ("url", "page_title", "page_text_excerpt", "form_state")},
            }, purpose="foreman", tier="cheap", max_tokens=700)
        except Exception as e:
            bus.emit("error", where="foreman", error=str(e)[:200])
            return
        fresh = [str(n)[:170] for n in out.get("notes", []) if not TODO.match(str(n)) and str(n) not in self.notes]
        self.notes = (self.notes + fresh[:6])[-24:]
        for v in out.get("values", [])[:10]:
            if hasattr(self.env, "pool") and str(v) not in self.env.pool:
                self.env.pool.append(str(v))
        self.finished = bool(out.get("finished"))
        if out.get("subgoal"):
            self.subgoal, self.on_subgoal = str(out["subgoal"]), 0
        self.publish()

    def after_step(self, obs_after: dict, history: list[dict], noops: set) -> None:
        self.ticks += 1
        self.on_subgoal += 1
        stuck = self.on_subgoal >= 9 if self.static else (self.ticks >= 24 and self.rescues == 0)
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
