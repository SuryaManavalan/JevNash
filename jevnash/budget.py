"""Spend pacing for a time-boxed session: LLM spend may not run ahead of the clock."""

from __future__ import annotations

import os
import time

from .events import bus

# TypeSafe does not publish a per-token price in the docs; override to match your plan.
JEV_USD_PER_MTOK = float(os.environ.get("JEV_USD_PER_MTOK", "0.5"))


class Budget:
    def __init__(self, minutes: float = 60, usd: float = 1.0):
        self.start = time.time()
        self.seconds, self.usd = minutes * 60, usd
        self.llm_usd = 0.0
        self.llm_calls = 0
        self.jev_tokens = 0
        self.jev_calls = 0
        self.cache_hits = 0

    @property
    def jev_usd(self) -> float:
        return self.jev_tokens / 1e6 * JEV_USD_PER_MTOK

    @property
    def spent(self) -> float:
        return self.llm_usd + self.jev_usd

    def elapsed_fraction(self) -> float:
        return min(1.0, (time.time() - self.start) / self.seconds)

    def time_up(self) -> bool:
        return time.time() - self.start >= self.seconds

    def allows_llm(self, kind: str = "learn") -> bool:
        """Escalations are cheap and cached forever, so each one makes the rest of the hour
        cheaper: they are allowed up to 90% of the ceiling. Reflection and re-modelling are paced
        against the clock, front-loaded by 35% because early learning pays off for longest."""
        if kind == "escalate":
            return self.spent < 0.9 * self.usd
        return self.spent <= self.usd * min(1.0, self.elapsed_fraction() + 0.35)

    def publish(self) -> None:
        bus.emit(
            "budget", usd=self.usd, spent=round(self.spent, 4), llm_usd=round(self.llm_usd, 4),
            jev_usd=round(self.jev_usd, 4), llm_calls=self.llm_calls, jev_calls=self.jev_calls,
            jev_tokens=self.jev_tokens, cache_hits=self.cache_hits,
            elapsed=round(time.time() - self.start), seconds=self.seconds,
        )


budget = Budget()
