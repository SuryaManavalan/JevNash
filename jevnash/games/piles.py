"""Pile-removal game against a random opponent. Whoever takes the last item wins."""

from __future__ import annotations

import random
from typing import Any

from ..env import GameEnv


class PilesEnv(GameEnv):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self) -> None:
        self.piles = [self.rng.randint(1, 5) for _ in range(3)]
        self.winner: str | None = None
        self.message = "Your turn. Whoever removes the last item wins."

    def observe(self) -> dict[str, Any]:
        return {"piles": list(self.piles), "message": self.message}

    def _moves(self) -> list[tuple[int, int]]:
        return [(i, n) for i, size in enumerate(self.piles) for n in range(1, size + 1)]

    def legal_actions(self) -> list[str]:
        return [f"take {n} from pile {i}" for i, n in self._moves()]

    def render(self) -> dict[str, Any]:
        return {
            "kind": "piles",
            "piles": list(self.piles),
            "targets": {f"take {n} from pile {i}": [i, n] for i, n in self._moves()},
        }

    def step(self, action: str) -> dict[str, Any]:
        try:
            parts = action.split()
            n, i = int(parts[1]), int(parts[-1])
            assert (i, n) in self._moves()
        except Exception:
            self.message = f"Rejected action: {action!r}"
            return {"error": self.message}
        self.piles[i] -= n
        if not any(self.piles):
            self.winner, self.message = "you", "You removed the last item. You won."
            return {}
        i, n = self.rng.choice(self._moves())
        self.piles[i] -= n
        self.message = f"Opponent took {n} from pile {i}. Your turn."
        if not any(self.piles):
            self.winner, self.message = "opponent", "Opponent removed the last item. You lost."
        return {}

    def done(self) -> bool:
        return self.winner is not None

    def outcome(self) -> float:
        return 1.0 if self.winner == "you" else 0.0
