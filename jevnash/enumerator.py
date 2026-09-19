"""Game Model + state -> a concrete option menu with criteria objects."""

from __future__ import annotations

from .clients import LLMClient

MAX_OPTIONS = 1500  # the policy fans menus larger than one Choice out into parallel chunks

SYSTEM = """Instantiate the action schema against the current observation. Return a JSON array of
concrete action strings the agent could plausibly take right now (at most 40). Respect
preconditions. Do not explain."""


class OptionEnumerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def enumerate(self, model: dict, observation: dict, legal: list[str] | None) -> list[str]:
        if legal is None:
            legal = self.llm.json(
                SYSTEM, {"action_schema": model.get("action_schema"), "observation": observation},
                purpose="enumerate", tier="cheap",
            )
        return [str(a) for a in legal][:MAX_OPTIONS]

    def criteria(self, model: dict, actions: list[str]) -> tuple[dict, dict[str, str]]:
        """Build Choice criteria. Learned action_notes are written into the option objects."""
        criteria: dict = {}
        keys: dict[str, str] = {}
        for i, action in enumerate(actions):
            option: dict = {"what": action}
            for note in model.get("action_notes", []):
                if note.get("match") and note["match"] in action:
                    kind = note.get("kind", "heuristics")
                    option.setdefault(kind, []).append(note["note"])
            key = f"a{i + 1}"
            criteria[key] = option if len(option) > 1 else action
            keys[key] = action
        criteria["other"] = "None of the listed actions is reasonable"
        return criteria, keys
