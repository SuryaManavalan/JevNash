"""Two-speed loop runner, paced for a time-boxed session.

    uv run python -m jevnash.run --env env_a --minutes 60 --usd 1 --dashboard
    uv run python -m jevnash.run --env web_form --episodes 5 --dashboard --headed
    uv run python -m jevnash.run --env env_a --episodes 200 --agent random
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
from dataclasses import asdict
from pathlib import Path

from .brain import Brain, Librarian
from .budget import budget
from .clients import JevClient, LLMClient
from .enumerator import OptionEnumerator
from .env import GameEnv
from .events import bus
from .games import ENVS
from .learning import EpisodeLogger, Reflector, ValueModel
from .modeler import GameModeler
from .policy import SCORES, Decision, Escalator, JevPolicy, choose_value
from .workstream import Workstream

MAX_TICKS = 60
REMODEL_EVERY = 10  # episodes; the periodic re-run trigger
REFLECT_ON_WIN_EVERY = 5  # wins teach less than losses, so they are reviewed less often
# Mean outcome of a uniformly random agent (env_a/env_b measured over 200 episodes).
BASELINE = {"env_a": 0.515, "env_b": 0.495, "web_form": 0.0, "web_race": 0.0, "web_open": 0.0,
            "web_canvas": 0.5, "suite": 0.0, "paint": 0.0}
CACHE_MIN_CONFIDENCE = 0.6  # only confident Jev decisions are replayed from cache


def run_random(env: GameEnv, episodes: int) -> list[float]:
    outcomes = []
    for _ in range(episodes):
        env.reset()
        while not env.done():
            env.step(random.choice(env.legal_actions()))
        outcomes.append(env.outcome())
    return outcomes


def _situation(obs: dict) -> dict:
    # steps_left / message only restate the history; they are not part of the situation.
    return {k: v for k, v in obs.items() if k not in ("message", "steps_left")}


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


class Harness:
    def __init__(self, env: GameEnv, run_dir: Path, learn: bool = True, pace: float = 0.0,
                 documents: str | None = None, planner: str = "smart"):
        self.env, self.run_dir, self.learn, self.pace = env, run_dir, learn, pace
        self.documents = documents
        run_dir.mkdir(parents=True, exist_ok=True)
        bus.open(run_dir)
        self.jev, self.llm = JevClient(), LLMClient()
        self.modeler = GameModeler(self.llm, self.jev)
        self.enumerator = OptionEnumerator(self.llm)
        self.policy = JevPolicy(self.jev)
        self.escalator = Escalator(self.llm)
        self.reflector = Reflector(self.llm)
        self.logger = EpisodeLogger(run_dir)
        self.value = ValueModel()
        self.value.fit(self.logger.load())
        self.model_path, self.cache_path = run_dir / "game_model.json", run_dir / "cache.json"
        self.model: dict | None = self._load(self.model_path)
        # "jev": confident fast decisions, keyed on the learnings so new heuristics invalidate them.
        # "llm": System 2 answers, keyed on the situation only; they stay valid across learnings.
        self.cache: dict = self._load(self.cache_path) or {"jev": {}, "llm": {}}
        self.transitions: list[dict] = []
        self.wins_since_reflect = 0
        # Workstreams (long tasks the agent must declare finished) are steered by the Librarian,
        # which owns the markdown brain. One brain is shared by every workstream env.
        self.workstream = bool(getattr(env, "can_finish", False))
        self.librarian = Librarian(Brain(Path("brain")), tier=planner) if self.workstream and self.llm.api else None
        if self.workstream:
            self.escalator.max_threat, self.escalator.budget_per_episode = 2.0, 10
            # No rulebook to infer: the task text is the goal and the brain holds the know-how.
            self.model = {"goal": "Complete `observation.task` exactly as written, then finish.", "heuristics": []}

    @staticmethod
    def _load(path: Path):
        return json.loads(path.read_text()) if path.exists() else None

    def save(self) -> None:
        self.model_path.write_text(json.dumps(self.model, indent=2))
        self.cache_path.write_text(json.dumps(self.cache))

    def publish_model(self) -> None:
        bus.emit("model", model=self.model)

    def remodel(self, trigger: str) -> None:
        print(f"  [slow loop] rebuilding game model ({trigger})")
        bus.emit("slow_loop", phase="start", trigger=trigger)
        self.model = self.modeler.build(
            self.env.observe(), self.env.legal_actions(), self.transitions, self.model, trigger,
            self.documents,
        )
        bus.emit("slow_loop", phase="end", trigger=trigger)
        self.publish_model()
        self.save()

    def decide(self, obs: dict, actions: list[str], history: list[dict],
               ws: dict | None = None) -> tuple[Decision, str]:
        learnings = (self.model.get("heuristics"), self.model.get("action_notes"))
        situation = _key(_situation(obs), actions, ws and (ws["current_subgoal"], ws["briefing"]))
        jev_key = _key(situation, learnings)
        if jev_key in self.cache["jev"]:
            budget.cache_hits += 1
            return Decision(**self.cache["jev"][jev_key]), "cache"

        criteria, keys = self.enumerator.criteria(self.model, actions)
        bus.emit("thinking", who="jev")
        d = self.policy.decide(self.model, obs, history, criteria, keys, ws)
        source = "jev"
        if self.escalator.should_escalate(d):
            if situation in self.cache["llm"] and self.cache["llm"][situation] in d.probabilities:
                budget.cache_hits += 1
                d.extras["jev_action"] = d.action
                d.action, d.escalated, source = self.cache["llm"][situation], True, "cache"
            elif budget.allows_llm("escalate"):
                bus.emit("thinking", who="llm")
                try:
                    d = self.escalator.decide(self.model, obs, history, d, ws)
                except Exception as e:  # a failed System 2 call must never stop play
                    bus.emit("error", where="escalate", error=str(e)[:200])
                if d.escalated:
                    self.cache["llm"][situation] = d.action
                    source = "llm"
        if not d.escalated and d.confidence >= CACHE_MIN_CONFIDENCE:
            self.cache["jev"][jev_key] = asdict(d)
        return d, source

    def episode(self, n: int) -> float:
        self.env.reset()
        self.escalator.new_episode()
        if self.model is None:
            self.remodel("cold_start")
        elif self.learn and not self.workstream and n > 0 and n % REMODEL_EVERY == 0 and budget.allows_llm():
            self.remodel("periodic")
        bus.emit("episode_start", n=n, view=self.env.render(), observation=self.env.observe())
        history: list[dict] = []
        noops: set[tuple[str, str]] = set()
        taken: dict[tuple[str, str], int] = {}  # how often each action was taken from each exact situation
        ws_ctl = Workstream(self, self.env) if self.librarian else None
        if ws_ctl:
            ws_ctl.start()
        seen_verbs = {s.get("verb") for s in self.model.get("action_schema", [])}

        for tick in range(getattr(self.env, "max_steps", MAX_TICKS) + 1):
            if self.env.done():
                break
            obs = self.env.observe()
            view = self.env.render()
            ws = ws_ctl.context(obs, history) if ws_ctl else None
            actions = self.enumerator.enumerate(self.model, obs, self.env.legal_actions())
            if ws_ctl:
                actions = ws_ctl.shape(actions)
            # No-op and cycle guard: an action that changed nothing, or was already taken twice from this
            # exact situation, is not offered again, so neither Jev nor the cache can loop.
            here = _key(_situation(obs))
            actions = [a for a in actions if (here, a) not in noops and taken.get((here, a), 0) < 2] or actions[-1:]
            if not actions:  # dead end: nothing left to do and the env has not declared an outcome
                bus.emit("stuck", n=n, observation=obs)
                break
            steps = ws_ctl.macro(actions) if ws_ctl else None
            if steps is not None:  # the subgoal compiles to a macro: replay it with no per-click model calls
                for k, act in enumerate(steps):
                    bus.emit("tick", n=n, tick=tick, view=view, observation=obs, action=act, source="macro", confidence=1.0,
                             options=[[act, 1.0]], n_options=len(actions), scores={}, escalated=False, value_pred=None,
                             why=None, jev_action=None, label=f"MACRO {k + 1}/{len(steps)} → {act[:60]}")
                    self.env.show_decision({act: 1.0}, act, f"MACRO · {ws_ctl.subgoal[:70]}")
                    if self.pace:
                        time.sleep(self.pace / 3)
                    self.env.step(act)
                    self.env.legal_actions()  # refresh element ids for the next click
                self.logger.tick(observation=obs, options=[], action=" ; ".join(steps), confidence=1.0, probabilities={},
                                 scores={}, escalated=False, source="macro", value_pred=None, extras={}, error=None)
                ws_ctl.step += 1
                ws_ctl.finished = ws_ctl.step >= len(ws_ctl.plan) and not ws_ctl.repair()
                if not ws_ctl.finished:
                    ws_ctl.subgoal = ws_ctl.plan[ws_ctl.step]
                    ws_ctl.publish()
                    continue
            if ws_ctl and ws_ctl.finished:
                d, source = Decision("finish: the whole task is complete, stop here", 1.0, {}, {}), "foreman"
            else:
                d, source = self.decide(obs, actions, history, ws)
                if ws_ctl and ws_ctl.after_decision(d, obs, history):
                    if ws_ctl.finished:
                        d, source = Decision("finish: the whole task is complete, stop here", 1.0, {}, {}), "foreman"
                    else:
                        actions = ws_ctl.shape(self.enumerator.enumerate(self.model, obs, self.env.legal_actions()))
                        actions = [a for a in actions if (here, a) not in noops and taken.get((here, a), 0) < 2] or actions[-1:]
                        d, source = self.decide(obs, actions, history, ws_ctl.context(obs, history))
            if d.action.endswith("= ?"):  # two-stage typing: Jev now selects the value
                tried = {a for h, a in taken if h == here}
                values = [v for v in self.env.value_candidates() if f'{d.action[:-1]}"{v}"' not in tried]
                if ws_ctl and ws_ctl.subgoal:
                    # The foreman quotes what must be typed: when it did, only those values are candidates.
                    quoted = [v for v in re.findall(r'"([^"]{1,60})"', ws_ctl.subgoal) if v in values]
                    values = quoted or values
                if not values:  # nothing left to type here: take this field off the menu and look again
                    noops.add((here, d.action))
                    continue
                value, vconf = choose_value(self.jev, obs, ws_ctl.context(obs, history) if ws_ctl else None,
                                            history, d.action[:-4], values)
                d.action, d.confidence = f'{d.action[:-1]}"{value}"', min(d.confidence, vconf)
                d.probabilities = {d.action: 1.0}
            value_pred = self.value.predict(d.scores) if d.scores else None
            label = (f"{source.upper()} → {d.action[:60]}  ·  conf {d.confidence:.2f}"
                     + ("  ·  escalated to System 2" if d.escalated else ""))
            ranked = sorted(d.probabilities.items(), key=lambda kv: -kv[1])
            bus.emit(
                "tick", n=n, tick=tick, view=view, observation=obs, action=d.action, source=source,
                confidence=d.confidence, options=ranked[:40], n_options=len(actions),
                scores=d.scores, escalated=d.escalated, value_pred=value_pred,
                why=d.extras.get("why"), jev_action=d.extras.get("jev_action"), label=label,
            )
            self.env.show_decision(d.probabilities, d.action, label)
            if self.pace:
                time.sleep(self.pace)
            info = self.env.step(d.action)
            after = self.env.observe()

            self.logger.tick(
                observation=obs, options=actions[:60], action=d.action, confidence=d.confidence,
                probabilities=dict(ranked[:20]), scores=d.scores, escalated=d.escalated,
                source=source, value_pred=value_pred, extras=d.extras, error=info.get("error"),
            )
            if not info.get("error") and _key(_situation(after)) == here:
                noops.add((here, d.action))
                bus.emit("noop", action=d.action)
            taken[(here, d.action)] = taken.get((here, d.action), 0) + 1
            history.append({"action": d.action, "result": info.get("error") or after.get("message")})
            self.transitions = (self.transitions + [{"before": obs, "action": d.action, "after": after}])[-24:]
            if ws_ctl:
                ws_ctl.after_step(after, history, noops)

            # Surprise triggers: a rejected action, or an action verb the model doesn't know.
            verb = d.action.split()[0] if d.action else ""
            surprised = info.get("error") or (seen_verbs and verb not in seen_verbs)
            if self.learn and surprised and not self.workstream and budget.allows_llm():
                self.remodel("rejected_action" if info.get("error") else "new_action_type")
                seen_verbs = {s.get("verb") for s in self.model.get("action_schema", [])} | {verb}

        outcome = self.env.outcome() if self.env.done() else 0.0
        record = self.logger.end(n, outcome, "harness")
        record["final_observation"] = self.env.observe()
        record["pages_used"] = ws_ctl.pages if ws_ctl else []
        record["plan"] = (ws_ctl.plan if ws_ctl else [])
        record["rescues"] = ws_ctl.rescues if ws_ctl else 0
        record["notes"] = ws_ctl.notes if ws_ctl else []
        if bus.shot:  # keep the last frame of browser episodes for later inspection
            (self.run_dir / f"episode_{n}.jpg").write_bytes(bus.shot)
        bus.emit("episode_end", n=n, outcome=outcome, view=self.env.render(),
                 observation=record["final_observation"])
        if self.learn:
            self.learn_from(record)
        budget.publish()
        return outcome

    def learn_from_workstream(self, record: dict) -> None:
        """Workstreams learn into the brain: evidence votes are free, consolidation is paced."""
        brain, won = self.librarian.brain, record["outcome"] >= 1.0
        report = self.env.report() if hasattr(self.env, "report") else {}
        brain.vote(record["pages_used"], won)
        run = {"task": record["ticks"][0]["observation"].get("task") if record["ticks"] else "",
               "score": record["outcome"], "checks": report, "outline": record["plan"], "rescues": record["rescues"],
               "notes": record["notes"],
               "pages_used": record["pages_used"],
               "steps": [{"url": t["observation"].get("url", "").split("/", 3)[-1], "action": t["action"],
                          "by": t["source"], "error": t.get("error")} for t in record["ticks"]]}
        (brain.root / "raw/runs" / f"{int(time.time())}.json").write_text(json.dumps(run, indent=1))
        brain.log(f"run | score {record['outcome']:.2f} in {len(record['ticks'])} steps | {run['task'][:70]}")
        self.wins_since_reflect = self.wins_since_reflect + 1 if won and not record["rescues"] else 0
        # A clean win on known ground teaches little; anything else is worth writing down.
        if (self.wins_since_reflect == 0 or not record["pages_used"]) and budget.allows_llm():
            bus.emit("thinking", who="reflect")
            try:
                self.librarian.consolidate(run)
            except Exception as e:
                bus.emit("error", where="consolidate", error=str(e)[:200])
        self.save()

    def learn_from(self, record: dict) -> None:
        if self.librarian:
            return self.learn_from_workstream(record)
        won = record["outcome"] >= 1.0
        self.wins_since_reflect = self.wins_since_reflect + 1 if won else 0
        due = not won or self.wins_since_reflect >= REFLECT_ON_WIN_EVERY
        if due and budget.allows_llm():
            bus.emit("thinking", who="reflect")
            before = set(self.model.get("heuristics", []))
            try:
                self.model = self.reflector.reflect(self.model, record)
            except Exception as e:
                bus.emit("error", where="reflect", error=str(e)[:200])
            new = [h for h in self.model.get("heuristics", []) if h not in before]
            bus.emit("reflect", new=new, outcome=record["outcome"])
            self.publish_model()
            self.wins_since_reflect = 0
        if self.value.fit(self.logger.load()):
            bus.emit("value_model", weights=dict(zip(["bias", *SCORES], self.value.w.round(3).tolist())),
                     rows=self.value.n)
        self.save()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=list(ENVS), default="env_a")
    ap.add_argument("--episodes", type=int, default=0, help="0 = run until --minutes is up")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--usd", type=float, default=1.0, help="spend ceiling for the session")
    ap.add_argument("--agent", choices=["harness", "random"], default="harness")
    ap.add_argument("--no-learn", action="store_true", help="freeze the game model and heuristics")
    ap.add_argument("--dashboard", action="store_true", help="serve the brain dashboard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-hold", action="store_true", help="exit when done instead of keeping the dashboard up")
    ap.add_argument("--pace", type=float, default=None, help="seconds to pause per tick for viewers")
    ap.add_argument("--headed", action="store_true", help="show the real browser window (web envs)")
    ap.add_argument("--chaos", action="store_true", help="suite: per-episode label changes, shuffled nav, session interstitials")
    ap.add_argument("--family", help="suite: run only this task family (refund, update_contact, reorder, escalate)")
    ap.add_argument("--planner", choices=["cheap", "smart", "max"], default="smart",
                    help="LLM tier for the Librarian (Haiku 4.5 / Sonnet 5 / Opus 5)")
    ap.add_argument("--style", help="paint: pixel-art | anime | photo-realistic")
    ap.add_argument("--scene", help="paint: sunset | house | portrait")
    ap.add_argument("--task", help="web_open: what to accomplish")
    ap.add_argument("--url", help="web_open: where to start")
    ap.add_argument("--inputs", default="", help="web_open: comma-separated strings the agent may type")
    ap.add_argument("--rulebook", help="PDF/image/doc with rules or a brief; parsed via LlamaParse")
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    kwargs = {"seed": args.seed} | ({"headed": True} if args.headed else {})
    if args.env == "web_open":
        if not (args.task and args.url):
            ap.error("web_open needs --task and --url")
        kwargs |= {"task": args.task, "url": args.url,
                   "inputs": [s for s in args.inputs.split(",") if s]}
    if args.family:
        kwargs["family"] = args.family
    if args.chaos:
        kwargs["chaos"] = True
    kwargs |= {k: v for k, v in (("style", args.style), ("scene", args.scene)) if v}
    if args.agent == "random":
        outcomes = run_random(ENVS[args.env](**kwargs), args.episodes or 100)
        print(f"random agent: mean outcome {sum(outcomes) / len(outcomes):.3f} over {len(outcomes)}")
        return

    budget.__init__(minutes=args.minutes, usd=args.usd)
    if args.dashboard:
        from .server import serve
        serve(args.port)
        print(f"  brain dashboard: http://localhost:{args.port}")
    pace = args.pace if args.pace is not None else (0.7 if args.dashboard else 0.0)
    env = ENVS[args.env](**kwargs)
    documents = None
    if args.rulebook:
        from .perception import parse_file
        documents = parse_file(args.rulebook)
    h = Harness(env, Path(args.run_dir or f"runs/{args.env}"), learn=not args.no_learn, pace=pace,
                documents=documents, planner=args.planner)
    past = [ep["outcome"] for ep in h.logger.load()]
    bus.emit("run_start", env=args.env, minutes=args.minutes, usd=args.usd, past_outcomes=past,
             baseline=BASELINE.get(args.env))
    budget.publish()
    if h.model:
        h.publish_model()
    outcomes: list[float] = []
    try:
        i = len(past)
        while not budget.time_up() and (not args.episodes or len(outcomes) < args.episodes):
            outcome = h.episode(i)
            outcomes.append(outcome)
            print(f"episode {i}: outcome={outcome}  mean={sum(outcomes) / len(outcomes):.3f}  "
                  f"jev={budget.jev_calls} llm={budget.llm_calls} cache={budget.cache_hits} "
                  f"spent=${budget.spent:.3f}")
            if hasattr(env, "report"):
                failed = [name for name, ok in env.report().items() if not ok]
                print(f"    [{getattr(env, 'task_family', '')}] steps={env.steps}" + (f"  FAILED: {failed}" if failed else "  all checks pass"))
            i += 1
    except KeyboardInterrupt:
        pass
    finally:
        h.save()
        env.close()
    bus.emit("run_end", episodes=len(outcomes), spent=round(budget.spent, 4))
    print("heuristics:", *h.model.get("heuristics", []), sep="\n  - ")
    print(f"session: {len(outcomes)} episodes, ${budget.spent:.3f} "
          f"(llm ${budget.llm_usd:.3f}, jev ~${budget.jev_usd:.3f})")
    if args.dashboard and not args.no_hold:
        print("  dashboard still live; Ctrl-C to exit")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
