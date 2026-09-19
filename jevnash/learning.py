"""Where the harness improves: episode logs, post-episode reflection, and a learned value model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .clients import LLMClient
from .policy import SCORES


class EpisodeLogger:
    def __init__(self, run_dir: Path):
        self.path = run_dir / "episodes.jsonl"
        self.ticks: list[dict] = []

    def tick(self, **record) -> None:
        self.ticks.append(record)

    def end(self, episode: int, outcome: float, agent: str) -> dict:
        record = {"episode": episode, "agent": agent, "outcome": outcome, "ticks": self.ticks}
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        self.ticks = []
        return record

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines()]


REFLECT_SYSTEM = """You review one finished episode played by a fast pattern-matching policy (it
cannot look ahead). Outcome: 1.0 win, 0.5 draw, 0.0 loss. Identify the decisive moments, then
return the updated learnings as JSON:

{"heuristics": [str],   // full replacement list, max 10, most important first
 "action_notes": [{"match": <substring of an action string>, "note": str,
                   "kind": "heuristics"|"not_for"}],   // full replacement list, max 12
 "rule_corrections": [str]}   // anything the game model got wrong about the rules; may be empty

Everything you write must hold for FUTURE episodes, where task details (names, targets,
values, positions, element ids) will differ: say "the size the task asks for", never a literal
value seen in this episode. The policy cannot look ahead or simulate, so never ask it to; give it
patterns it can recognise directly in the observation.
Heuristics must be concrete situation -> response patterns that can be recognised directly in the
observation, not generic advice. Keep existing entries that still hold, fix or drop ones the
episode contradicts, and merge duplicates."""


class Reflector:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def reflect(self, model: dict, episode: dict) -> dict:
        slim = [
            {
                "observation": t["observation"],
                "action": t["action"],
                "confidence": round(t["confidence"], 2),
                "top_options": sorted(t["probabilities"].items(), key=lambda kv: -kv[1])[:3],
                "escalated": t["escalated"],
                "error": t.get("error"),
            }
            for t in episode["ticks"]
        ]
        out = self.llm.json(
            REFLECT_SYSTEM,
            {
                "game_model": {k: model.get(k) for k in ("goal", "heuristics", "action_notes")},
                "outcome": episode["outcome"],
                "final_observation": episode.get("final_observation"),
                "ticks": slim,
            },
            purpose="reflect",
        )
        model["heuristics"] = out.get("heuristics", model.get("heuristics", []))[:10]
        model["action_notes"] = out.get("action_notes", model.get("action_notes", []))[:12]
        if out.get("rule_corrections"):
            model.setdefault("open_questions", []).extend(out["rule_corrections"])
        return model


class ValueModel:
    """Logistic regression over the per-tick Score features, labelled with the episode outcome."""

    def __init__(self) -> None:
        self.w: np.ndarray | None = None
        self.n = 0

    def fit(self, episodes: list[dict], min_episodes: int = 8) -> bool:
        rows = [
            ([t["scores"][k] for k in SCORES], ep["outcome"])
            for ep in episodes
            for t in ep["ticks"]
            if t.get("scores")
        ]
        outcomes = {ep["outcome"] for ep in episodes}
        if len(episodes) < min_episodes or len(outcomes) < 2:
            return False
        x = np.array([[1.0, *r[0]] for r in rows])
        y = np.array([r[1] for r in rows])
        w = np.zeros(x.shape[1])
        for _ in range(2000):
            p = 1 / (1 + np.exp(-x @ w))
            w -= 0.5 * (x.T @ (p - y) / len(y) + 1e-3 * w)
        self.w, self.n = w, len(rows)
        return True

    def predict(self, scores: dict[str, float]) -> float | None:
        if self.w is None:
            return None
        x = np.array([1.0, *[scores[k] for k in SCORES]])
        return float(1 / (1 + np.exp(-x @ self.w)))
