"""Thin clients for Jev (System One) and the frontier LLM. Both report into the budget and bus."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any

import anthropic
import httpx
from dotenv import load_dotenv

from .budget import budget
from .events import bus

load_dotenv()

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"

# tier -> (API model id, CLI alias, list $/Mtok in, $/Mtok out)
TIERS = {
    "smart": ("claude-sonnet-5", "sonnet", 2.0, 10.0),
    "cheap": ("claude-haiku-4-5", "haiku", 1.0, 5.0),
    "max": ("claude-opus-5", "opus", 5.0, 25.0),
}


class JevClient:
    def __init__(self) -> None:
        self.http = httpx.Client(
            headers={"Authorization": f"Bearer {os.environ['JEV_API_KEY']}"}, timeout=60
        )

    def ask(self, state: Any, questions: dict[str, dict], purpose: str = "tick") -> dict[str, dict]:
        """One batched call. Returns the answers map keyed by question id."""
        body = {"model": JEV_MODEL, "state": state, "questions": questions}
        t0 = time.time()
        for attempt in range(5):
            try:
                resp = self.http.post(JEV_URL, json=body)
            except httpx.TransportError:  # timeouts and dropped connections are retried like a 529
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 529) or resp.status_code >= 500:
                time.sleep(2**attempt)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Jev {resp.status_code}: {resp.text}")
            data = resp.json()
            tokens = data.get("usage", {}).get("input_tokens", 0)
            budget.jev_calls += 1
            budget.jev_tokens += tokens
            bus.emit("jev_call", purpose=purpose, questions=len(questions), tokens=tokens,
                     ms=round((time.time() - t0) * 1000))
            return data["answers"]
        raise RuntimeError("Jev unavailable after 5 attempts")


def _parse_json(text: str) -> Any:
    """First JSON value in the text; models sometimes add prose or a second value after it."""
    match = re.search(r"[\[{]", text)
    if not match:
        raise ValueError(f"no JSON in LLM reply: {text[:200]!r}")
    return json.JSONDecoder().raw_decode(text[match.start():])[0]


class LLMClient:
    """Anthropic API when the key works; otherwise the logged-in `claude` CLI in headless mode."""

    def __init__(self) -> None:
        self.backend = os.environ.get("JEVNASH_LLM_BACKEND", "auto")  # auto | api | cli
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        self.api = anthropic.Anthropic(
            default_headers={"anthropic-workspace-id": workspace} if workspace else None
        ) if os.environ.get("ANTHROPIC_API_KEY") else None
        if self.api is None and self.backend == "auto":
            self.backend = "cli"

    def _api(self, tier: str, system: str, user: str, max_tokens: int) -> tuple[str, float]:
        model, _, usd_in, usd_out = TIERS[tier]
        # Sonnet 5 thinks adaptively by default; low effort keeps rulebook/review calls cheap.
        # Haiku runs without thinking. Thinking tokens are billed inside usage.output_tokens.
        extra = {"output_config": {"effort": "low"}} if tier == "smart" else {}
        msg = self.api.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}], **extra,
        )
        cost = (msg.usage.input_tokens * usd_in + msg.usage.output_tokens * usd_out) / 1e6
        return "".join(b.text for b in msg.content if b.type == "text"), cost

    def _cli(self, tier: str, system: str, user: str) -> tuple[str, float]:
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        # Unbounded thinking made single escalations take 100s and cost 10x; cap it hard.
        env["MAX_THINKING_TOKENS"] = "0" if tier == "cheap" else "1500"
        out = subprocess.run(
            ["claude", "-p", "--model", TIERS[tier][1], "--output-format", "json",
             "--system-prompt", system, "--tools", "", "--strict-mcp-config",
             "--setting-sources=", "--disable-slash-commands"],
            input=user, capture_output=True, text=True, env=env, timeout=300, cwd="/tmp",
        )
        data = json.loads(out.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude CLI: {data.get('result')}")
        return data["result"], float(data.get("total_cost_usd", 0.0))

    def json(self, system: str, payload: Any, purpose: str, tier: str = "smart",
             max_tokens: int = 4000) -> Any:
        """Send a JSON payload, get parsed JSON back."""
        system += "\n\nRespond with a single JSON value and nothing else."
        user = json.dumps(payload, separators=(",", ":"))
        bus.emit("llm_start", purpose=purpose, tier=tier)
        t0 = time.time()
        if self.backend in ("auto", "api"):
            try:
                text, cost = self._api(tier, system, user, max_tokens)
                self.backend = "api"
            except anthropic.BadRequestError as e:
                if self.backend == "api" or "workspace" not in str(e):
                    raise
                print("  [llm] API key needs ANTHROPIC_WORKSPACE_ID; using the claude CLI instead")
                self.backend = "cli"
        if self.backend == "cli":
            text, cost = self._cli(tier, system, user)
        budget.llm_calls += 1
        budget.llm_usd += cost
        bus.emit("llm_end", purpose=purpose, tier=tier, backend=self.backend,
                 secs=round(time.time() - t0, 1), usd=round(cost, 4))
        budget.publish()
        return _parse_json(text)
