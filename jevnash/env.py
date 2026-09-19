"""GameEnv interface. Adapters must never leak the game's name into observations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GameEnv(ABC):
    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def observe(self) -> dict[str, Any]:
        """Current observation as named JSON fields."""

    def legal_actions(self) -> list[str] | None:
        """Concrete legal actions, or None when the env cannot enumerate them."""
        return None

    @abstractmethod
    def step(self, action: str) -> dict[str, Any]:
        """Apply an action. Returns info; info["error"] is set when the action was rejected."""

    def render(self) -> dict[str, Any]:
        """View spec for the dashboard (humans only; never shown to a model)."""
        return {"kind": "json"}

    def show_decision(self, probabilities: dict[str, float], action: str, label: str) -> None:
        """Hook for envs with their own surface (e.g. a browser) to draw decision overlays."""

    def close(self) -> None: ...

    @abstractmethod
    def done(self) -> bool: ...

    @abstractmethod
    def outcome(self) -> float:
        """1.0 win, 0.5 draw, 0.0 loss. Only meaningful once done()."""
