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
(local multi-step form), `web_canvas` (pixel-only board the agent can only read by looking), `web_race` (reach a Wikipedia article by links), `web_open` (any task on
any site; Jev judges completion), `suite` (enterprise workstreams), `paint` (drawing challenge). Ids are opaque: no model is ever told which game it is in.
State lives in `runs/<env>/` (game model, caches, episode log, event log) and carries across runs.

## v2: long enterprise workstreams

Long tasks across several web apps are run by three roles (`jevnash/workstream.py`):

| Role | Model | When | Job |
| --- | --- | --- | --- |
| Librarian | Sonnet 5 (Haiku once the brain is mature) | once per task, plus rare rescues | searches the markdown brain with grep/read tools, returns a briefing and an outline; after the task, writes what was learned back |
| Foreman | Haiku 4.5 | every few ticks | reads the live screen, keeps working-memory notes, names the next subgoal, and alone decides when the task is finished |
| Jev | jev-latest | every tick | picks the UI action for the current subgoal |

Supporting mechanics: typing is select-not-generate (Jev picks the field, then the value, from strings
harvested off visited pages, the task and the notes); an action that changed nothing, or was taken twice
from the same situation, leaves the menu; app confirmation messages are recorded as proof so the foreman
does not burn steps re-verifying; subgoals an adapter can parse into intents are compiled to macros, with
Jev binding each phrase to a control once and the binding cached.

The brain is documented in `docs/brain.md`. Measured results are in `docs/benchmarks.md`.

```sh
# enterprise workstreams across the Acme Suite playground (helpdesk, CRM, billing, inventory)
uv run python -m jevnash.run --env suite --minutes 60 --usd 3 --dashboard
uv run python -m jevnash.run --env suite --family refund --episodes 3 --dashboard --headed
uv run python -m jevnash.run --env suite --chaos --minutes 60 --usd 5      # labels/nav change per task, sessions get interrupted

# real internet, read-only, v2 roles; stays on the start domain unless --allow adds more
uv run python -m jevnash.run --env web_open --v2 --episodes 1 --dashboard \
    --task 'Use the search box to open the article on "Eiffel Tower" and note its height.' --url https://en.wikipedia.org/wiki/Main_Page

# drawing challenge: replicate a picture in a style; --planner picks the LLM tier being tested
uv run python -m jevnash.run --env paint --style anime --scene house --planner cheap --episodes 1 --dashboard
```

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

## Perception (LlamaParse)

With `LLAMA_CLOUD_API_KEY` set, `jevnash/perception.py` turns anything visual or document-shaped
into text the models can read. A parse takes 10-20s, so it stays off the per-tick hot path and
every result is cached by content hash:

- `vision = True` on a `BrowserEnv` adds a `screen_as_seen` reading of the rendered page to each
  observation. `web_canvas` relies on it entirely: its board exists only as canvas pixels.
- `--rulebook manual.pdf` (PDF, image, docx, ...) is parsed once and given to the game modeller.

Parses are usually right but not deterministic: the same board can come back as a slightly
different table, so treat `screen_as_seen` as inferred state, not ground truth.

## LLM backend

Uses the Anthropic API when `ANTHROPIC_API_KEY` works (set `ANTHROPIC_WORKSPACE_ID` if the key is
not workspace-scoped); otherwise falls back to the logged-in `claude` CLI in headless mode.
Force one with `JEVNASH_LLM_BACKEND=api|cli`.

## Adding a game or task

Subclass `GameEnv` (`jevnash/env.py`) or `BrowserEnv` (`jevnash/games/browser.py`), register
it in `jevnash/games/__init__.py`. Optionally implement `render()` so the dashboard can draw it.
