# jevNash — a game-agnostic Jev harness

Jev (TypeSafe System One) is the fast policy, a frontier LLM writes the rulebook, and the harness
is where learning happens. Design notes: `docs/design.md`.

## Run

```sh
# one paced hour on a confined game, with the brain dashboard at http://localhost:8765
uv run python -m jevnash.run --env env_a --minutes 60 --usd 1 --dashboard

# browser tasks (add --headed to watch the real browser window with its overlays)
uv run python -m jevnash.run --env web_form --episodes 5 --dashboard --headed
uv run python -m jevnash.run --env web_race --episodes 5 --dashboard
uv run python -m jevnash.run --env web_open --episodes 1 --dashboard \
    --task 'Search the Python documentation for "asyncio" and open the asyncio library page.' \
    --url https://docs.python.org/3/

# random-agent baseline
uv run python -m jevnash.run --env env_a --episodes 200 --agent random
```

Environments, from confined to open: `env_a` (3x3 grid game), `env_b` (pile game), `web_form`
(local multi-step form), `web_race` (reach a Wikipedia article by links), `web_open` (any task on
any site; Jev judges completion). Ids are opaque: no model is ever told which game it is in.
State lives in `runs/<env>/` (game model, caches, episode log, event log) and carries across runs.

## How an hour stays cheap

- One batched Jev call per tick; menus above 250 options fan out into parallel chunk Choices plus
  one final Choice over the survivors (tested up to 1,500 links).
- Confident Jev decisions are cached per situation and learnings; LLM escalations are cached per
  situation forever. Repeated situations cost nothing.
- Escalations use the cheap tier with thinking off (~$0.002-0.006) and are allowed up to 90% of
  `--usd`. Reflection and re-modelling use the smart tier and are paced against the clock.
- Wins are reviewed every fifth time, losses every time. A no-op guard removes actions that
  changed nothing, so neither Jev nor the cache can loop.
- `JEV_USD_PER_MTOK` (default 0.5) is an assumed Jev price for the spend meter; set your real one.

## LLM backend

Uses the Anthropic API when `ANTHROPIC_API_KEY` works (set `ANTHROPIC_WORKSPACE_ID` if the key is
not workspace-scoped); otherwise falls back to the logged-in `claude` CLI in headless mode.
Force one with `JEVNASH_LLM_BACKEND=api|cli`.

## Adding a game or task

Subclass `GameEnv` (`jevnash/env.py`) or `BrowserEnv` (`jevnash/games/browser.py`), register
it in `jevnash/games/__init__.py`. Optionally implement `render()` so the dashboard can draw it.
