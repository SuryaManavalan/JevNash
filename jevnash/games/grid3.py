"""3x3 line-up game against a random opponent."""

from __future__ import annotations

import random
from typing import Any

from ..env import GameEnv

LINES = [
    [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(2, 0), (2, 1), (2, 2)],
    [(0, 0), (1, 0), (2, 0)], [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
    [(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)],
]


class Grid3Env(GameEnv):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self) -> None:
        self.grid = [["." for _ in range(3)] for _ in range(3)]
        self.winner: str | None = None
        self.message = "Your turn."
        # Opponent opens half of the games.
        if self.rng.random() < 0.5:
            self._opponent_move()

    def observe(self) -> dict[str, Any]:
        return {
            "grid": ["".join(row) for row in self.grid],
            "your_mark": "X",
            "opponent_mark": "O",
            "empty_mark": ".",
            "message": self.message,
        }

    def _empty(self) -> list[tuple[int, int]]:
        return [(r, c) for r in range(3) for c in range(3) if self.grid[r][c] == "."]

    def legal_actions(self) -> list[str]:
        return [f"place {r},{c}" for r, c in self._empty()]

    def render(self) -> dict[str, Any]:
        return {
            "kind": "grid",
            "cells": [list(row) for row in self.grid],
            "targets": {f"place {r},{c}": [r, c] for r, c in self._empty()},
        }

    def _check(self) -> None:
        for line in LINES:
            marks = {self.grid[r][c] for r, c in line}
            if len(marks) == 1 and "." not in marks:
                self.winner = marks.pop()
                return
        if not self._empty():
            self.winner = "draw"

    def _opponent_move(self) -> None:
        r, c = self.rng.choice(self._empty())
        self.grid[r][c] = "O"
        self.message = f"Opponent placed at {r},{c}. Your turn."
        self._check()

    def step(self, action: str) -> dict[str, Any]:
        try:
            r, c = (int(x) for x in action.removeprefix("place ").split(","))
            assert self.grid[r][c] == "."
        except Exception:
            self.message = f"Rejected action: {action!r}"
            return {"error": self.message}
        self.grid[r][c] = "X"
        self._check()
        if not self.done():
            self._opponent_move()
        if self.done():
            self.message = {"X": "You won.", "O": "You lost.", "draw": "Draw."}[self.winner]
        return {}

    def done(self) -> bool:
        return self.winner is not None

    def outcome(self) -> float:
        return {"X": 1.0, "draw": 0.5, "O": 0.0}[self.winner]
