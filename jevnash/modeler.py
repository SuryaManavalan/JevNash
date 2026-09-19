"""Slow loop: the LLM infers a Game Model from observations; Jev classifies and validates."""

from __future__ import annotations

from typing import Any

from .clients import JevClient, LLMClient

GAME_TYPES = {
    "board_placement": "Pieces or marks are placed or moved on a spatial grid",
    "card_game": "Hands, decks, draws and discards",
    "text_adventure": "Exploring rooms, items and puzzles through text commands",
    "resource_management": "Spending and accumulating quantities over time",
    "combinatorial_take_away": "Players alternately remove or reduce counters from shared stocks",
    "negotiation": "Offers, counter-offers and agreements between parties",
    "real_world_task": "A work or life objective with deadlines, people and dependencies",
    "other": "None of these fit",
}

PROPERTIES = {
    "turn_based": "Do the participants act in alternating turns?",
    "perfect_information": "Is all decision-relevant information visible to the agent?",
    "clear_win_condition": "Is there a clear, explicit win condition?",
    "multi_agent": "Is there at least one other agent whose actions affect the outcome?",
    "resource_management": "Does success depend on managing limited resources?",
}

SYSTEM = """You are the rulebook-writer for a game-playing agent. You are shown raw observations,
available actions and recent transitions from an unnamed game (it may be a formal game or an
abstract real-world objective). Infer what is going on and return a Game Model JSON object:

{"game_hypotheses": [{"name": str, "p": float, "support": "well_supported"|"speculative"}],
 "goal": str,
 "state_vars": [str],
 "action_schema": [{"verb": str, "params": [str], "preconditions": [str]}],
 "win_signals": [str], "lose_signals": [str], "progress_signals": [str],
 "heuristics": [str],
 "action_notes": [{"match": str, "note": str, "kind": "heuristics"|"not_for"}],
 "open_questions": [str]}

Keep competing hypotheses rather than collapsing to one. Heuristics must be short, concrete,
and usable by a fast pattern-matching policy that cannot do multi-step reasoning: phrase them as
recognisable situations -> what to do. `action_notes.match` is a substring of an action string.
Everything you write must hold for FUTURE episodes, where task details (names, targets,
values, positions, element ids) will differ: say "the size the task asks for", never a literal
value seen in this episode. The policy cannot look ahead or simulate, so never ask it to; give it
patterns it can recognise directly in the observation.
If a previous model is supplied, revise it rather than starting over, and preserve heuristics
that came from episode reviews unless the evidence contradicts them."""


class GameModeler:
    def __init__(self, llm: LLMClient, jev: JevClient):
        self.llm, self.jev = llm, jev

    def classify(self, observation: dict, actions: list[str] | None) -> dict[str, Any]:
        """Jev's fast read on genre and properties, passed to the LLM as a prior."""
        state = {"observation": observation, "available_actions": actions}
        questions: dict[str, dict] = {
            "type": {
                "type": "choice",
                "instructions": "What kind of game or task is the agent in?",
                "criteria": GAME_TYPES,
            },
            "competitiveness": {
                "type": "score",
                "instructions": "How adversarial is this situation?",
                "criteria": [
                    "Purely solo; nothing opposes the agent",
                    "Others are present but mostly indifferent",
                    "Others compete for the same goal",
                    "A direct opponent wins exactly when the agent loses",
                ],
            },
        }
        for key, q in PROPERTIES.items():
            questions[key] = {"type": "noul", "instructions": q}
        ans = self.jev.ask(state, questions, purpose="classify")
        top = sorted(ans["type"]["probabilities"].items(), key=lambda kv: -kv[1])[:3]
        return {
            "top_types": [{"name": k, "p": round(p, 3)} for k, p in top],
            "competitiveness": round(ans["competitiveness"]["score"], 2),
            "properties": {k: round(ans[k]["noul"], 2) for k in PROPERTIES},
        }

    def validate(self, model: dict, transitions: list[dict]) -> list[dict]:
        """Jev Noul checks: is each observed transition consistent with the hypothesised rules?"""
        if not transitions:
            return []
        rules = {k: model.get(k) for k in ("goal", "action_schema", "win_signals", "lose_signals")}
        questions = {
            f"t{i}": {
                "type": "noul",
                "instructions": f"Is the transition in `transitions[{i}]` (action taken from "
                "`before`, producing `after`) consistent with `rules`?",
                "criteria": {
                    "true": "The action fits the action schema and the result is plausible under the rules",
                    "false": "The action or its result contradicts the rules",
                },
            }
            for i in range(len(transitions))
        }
        ans = self.jev.ask({"rules": rules, "transitions": transitions}, questions, purpose="validate")
        return [t for i, t in enumerate(transitions) if ans[f"t{i}"]["noul"] < 0.4]

    def build(
        self,
        observation: dict,
        actions: list[str] | None,
        transitions: list[dict],
        previous: dict | None = None,
        trigger: str = "cold_start",
    ) -> dict:
        def slim(obs: dict) -> dict:
            return {k: (v[:300] if isinstance(v, str) else v) for k, v in obs.items()}

        sample = actions if actions is None or len(actions) <= 40 else (
            actions[:30] + [f"... {len(actions) - 40} more like these ..."] + actions[-10:])
        transitions = [{"before": slim(t["before"]), "action": t["action"], "after": slim(t["after"])}
                       for t in transitions[-8:]]
        payload = {
            "trigger": trigger,
            "fast_classifier_prior": self.classify(observation, sample),
            "observation": observation,
            "available_actions": sample,
            "recent_transitions": transitions,
            "previous_game_model": previous,
        }
        model = self.llm.json(SYSTEM, payload, purpose="model")
        contradictions = self.validate(model, transitions[-4:])
        if contradictions:
            payload["previous_game_model"] = model
            payload["trigger"] = "validation_contradictions"
            payload["contradicting_transitions"] = contradictions
            model = self.llm.json(SYSTEM, payload, purpose="revise")
        return model
