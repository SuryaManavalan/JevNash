"""Fast loop: one batched Jev call per tick -> move distribution, confidence, and evals."""

from __future__ import annotations

from dataclasses import dataclass, field

from .clients import JevClient, LLMClient

# The same Score dimensions are asked every tick so they can become value-model features.
SCORES = {
    "position_eval": (
        "How close is the agent to achieving `game_model.goal`?",
        ["Clearly losing", "Behind", "Even", "Ahead", "Clearly winning"],
    ),
    "threat": (
        "How immediate is the danger of the agent losing?",
        [
            "No way to lose in the next few steps",
            "Some risk is building but nothing urgent",
            "A loss is likely unless the agent responds now",
            "The loss can no longer be prevented",
        ],
    ),
    "opportunity": (
        "How close is an immediate win for the agent?",
        [
            "No winning path is visible",
            "A winning path exists but needs several more steps",
            "The agent can win with its very next action",
        ],
    ),
}


CHUNK = 250  # options per Choice (the API allows 255)
BEAM = 12  # survivors per chunk that go into the final Choice


@dataclass
class Decision:
    action: str
    confidence: float
    probabilities: dict[str, float]
    scores: dict[str, float]
    escalated: bool = False
    extras: dict = field(default_factory=dict)


class JevPolicy:
    def __init__(self, jev: JevClient):
        self.jev = jev

    def decide(
        self, model: dict, observation: dict, history: list[dict], criteria: dict, keys: dict[str, str],
        workstream: dict | None = None,
    ) -> Decision:
        state = {
            "game_model": {
                k: model.get(k)
                for k in ("goal", "heuristics", "win_signals", "lose_signals", "progress_signals")
            },
            # Jev gets a shorter page excerpt than the foreman: enough to act on, far fewer tokens per tick.
            "observation": {k: (v[:1500] if k == "page_text_excerpt" else v) for k, v in observation.items()},
            "history_tail": history[-8:],
        }
        instructions = {
            "question": "Which action best advances the agent toward `game_model.goal` from `observation`?",
            "priority": "Apply `game_model.heuristics`. Take an immediate win if one exists; "
            "otherwise prevent an immediate loss.",
        }
        if workstream:  # long tasks: the Librarian's plan and briefing steer every choice
            state["workstream"] = workstream
            instructions = {
                "question": "Which single action should be taken next on this screen to carry out "
                "`workstream.current_subgoal`?",
                "guidance": "Follow `workstream.briefing`. Do not repeat an action in `history_tail` that "
                "already succeeded.",
            }
        questions: dict[str, dict] = {"move": {"type": "choice", "instructions": instructions, "criteria": criteria}}
        if workstream and "plan" in workstream:
            # Static plan: progress is a Choice over the visible window of the plan.
            questions["progress"] = {
                "type": "choice",
                "instructions": "Judging by `observation` and `history_tail`, which subgoal of `workstream.plan` is the "
                "next one that still has to be done?",
                "criteria": {f"s{i}": {"subgoal": sg, "means": "everything before this is finished; this is not"}
                             for i, sg in enumerate(workstream["plan"])},
            }
        elif workstream:
            questions["subgoal_done"] = {
                "type": "noul",
                "instructions": "Judging by `observation` and `history_tail`, has `workstream.current_subgoal` "
                "already been fully accomplished?",
                "criteria": {"true": "The screen or the last result confirms it", "false": "It still needs an action"},
            }
            questions["noteworthy"] = {
                "type": "noul",
                "instructions": "Does `observation.page_text_excerpt` show specific facts (ids, amounts, names, "
                "statuses, table rows) that `observation.task` needs and that are not yet in `workstream.notes`?",
            }
        if not workstream:  # self-evaluation feeds the value model; workstreams are scored by their checks
            for key, (text, levels) in SCORES.items():
                questions[key] = {"type": "score", "instructions": text, "criteria": levels}
        # More than one Choice can hold: fan the menu out into parallel chunk Choices in the same
        # call, then run a final Choice over each chunk's best few (beam over joint probability).
        items = [(k, v) for k, v in criteria.items() if k != "other"]
        chunks = [dict(items[i:i + CHUNK]) for i in range(0, len(items), CHUNK)]
        if len(chunks) > 1:
            base = questions.pop("move")
            for ci, chunk in enumerate(chunks):
                questions[f"move_{ci}"] = {**base, "criteria": {**chunk, "other": criteria["other"]}}
        ans = self.jev.ask(state, questions)
        if len(chunks) > 1:
            beam: dict = {}
            for ci in range(len(chunks)):
                ranked = sorted(ans[f"move_{ci}"]["probabilities"].items(), key=lambda kv: -kv[1])
                beam.update({k: criteria[k] for k, _ in ranked[:BEAM] if k != "other"})
            final = {"move": {**base, "criteria": {**beam, "other": criteria["other"]}}}
            ans["move"] = self.jev.ask(state, final, purpose="beam_final")["move"]

        move = ans["move"]
        probs = {keys[k]: p for k, p in move["probabilities"].items() if k in keys}
        total = sum(probs.values()) or 1.0
        probs = {a: p / total for a, p in probs.items()}
        action = max(probs, key=probs.get)
        return Decision(
            action=action,
            confidence=move["confidence"],
            probabilities=probs,
            scores={k: ans[k]["score"] / (len(SCORES[k][1]) - 1) for k in SCORES if k in ans},
            extras={"other_p": move["probabilities"].get("other", 0.0),
                    "progress": ans.get("progress", {}).get("probabilities"),
                    "subgoal_done": ans.get("subgoal_done", {}).get("noul"),
                    "noteworthy": ans.get("noteworthy", {}).get("noul")},
        )


def choose_value(jev: JevClient, observation: dict, workstream: dict | None, history: list[dict],
                 field: str, values: list[str]) -> tuple[str, float]:
    """Second stage of typing: select, don't generate. Jev picks the value from what has been seen."""
    keys = {f"v{i}": v for i, v in enumerate(values[:250])}
    ws = {k: v for k, v in (workstream or {}).items() if k != "briefing"}
    state = {"task": observation.get("task"), "workstream": ws, "field": field,
             "form_state": observation.get("form_state"), "history_tail": history[-8:]}
    ans = jev.ask(state, {"value": {
        "type": "choice",
        "instructions": {"question": "Which value should be typed into the form field named in `field`, given "
                         "`workstream.current_subgoal`, `workstream.notes` and `task`?",
                         "guidance": "The value must be of the kind the field expects (a quantity is a plain number, "
                         "an id goes in an id field). Do not re-enter values already used in `history_tail` for a finished item."},
        "criteria": {**keys, "other": "None of these values belongs in this field"},
    }}, purpose="value")["value"]
    best = max((k for k in keys), key=lambda k: ans["probabilities"].get(k, 0))
    return keys[best], ans["confidence"]


ESCALATE_SYSTEM = """You are the System 2 fallback for a fast game-playing policy that was unsure.
Check immediate wins, then immediate losses to prevent, then the goal. Answer at once with JSON: {"action": <one of the options,
verbatim>, "why": <one sentence>}."""


class Escalator:
    def __init__(self, llm: LLMClient, min_confidence: float = 0.5, min_margin: float = 0.15,
                 max_threat: float = 0.45, budget_per_episode: int = 4):
        self.llm = llm
        self.min_confidence, self.min_margin = min_confidence, min_margin
        self.max_threat, self.budget_per_episode = max_threat, budget_per_episode
        self.used = 0

    def new_episode(self) -> None:
        self.used = 0

    def should_escalate(self, d: Decision) -> bool:
        top = sorted(d.probabilities.values(), reverse=True)
        margin = top[0] - top[1] if len(top) > 1 else 1.0
        # Jev's own threat score catches confident-but-tactically-blind choices.
        unsure = (d.confidence < self.min_confidence or margin < self.min_margin
                  or d.scores.get("threat", 0.0) >= self.max_threat)
        return unsure and len(top) > 1 and self.used < self.budget_per_episode

    def decide(self, model: dict, observation: dict, history: list[dict], d: Decision,
               workstream: dict | None = None) -> Decision:
        self.used += 1
        ranked = sorted(d.probabilities.items(), key=lambda kv: -kv[1])
        out = self.llm.json(
            ESCALATE_SYSTEM,
            {
                "goal": model.get("goal"),
                "heuristics": model.get("heuristics"),
                "observation": observation,
                "workstream": workstream,
                "recent_actions": [h["action"] for h in history[-8:]],
                "options_omitted": max(0, len(d.probabilities) - 25),
                "options_with_fast_policy_probability": [
                    {"action": a, "p": round(p, 3)} for a, p in ranked[:25]
                ],
            },
            purpose="escalate", tier="cheap", max_tokens=300,
        )
        if out.get("action") in d.probabilities:
            d.extras["jev_action"], d.extras["why"] = d.action, out.get("why")
            d.action, d.escalated = out["action"], True
        return d
