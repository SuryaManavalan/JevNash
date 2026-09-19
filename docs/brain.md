# The brain: an LLM-owned markdown wiki

jevNash v2 keeps what it learns in `brain/`, a plain-markdown wiki that the LLM half of the system
(the Librarian) searches with `grep`/`list_pages`/`read_page` and edits with `write_page`. Jev never
reads it: the Librarian distils the relevant pages into a short briefing for each task.

## Conventions and where they come from

| Convention | Source |
| --- | --- |
| Always-loaded file holds only stable, universal rules (`AGENT.md`, human-owned) | [AGENTS.md](https://agents.md), [Claude Code memory](https://code.claude.com/docs/en/memory) |
| `index.md`: one line per page; topic pages read on demand | Claude Code auto memory, [Karpathy's LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) |
| Frontmatter `name` + `description` ("what it covers + when to load it") is the retrieval surface | [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) progressive disclosure |
| File tools rooted in one directory, path-checked; "search before you write" | [Anthropic memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) |
| `log.md` append-only; immutable `raw/runs/` beside the LLM-owned pages | Karpathy's LLM wiki |
| Workflows as parameterised steps with `{variables}`; never literal record values | [Agent Workflow Memory](https://arxiv.org/abs/2409.07429) |
| Distil failures as well as successes | [ReasoningBank](https://arxiv.org/abs/2509.25140) |
| Task outcomes vote pages up or down; `candidate → verified → deprecated` | ExpeL-style counters; [experience-following](https://arxiv.org/abs/2505.16067) shows wrong memories propagate |
| Page text from the web is data, never instructions | memory-poisoning literature |
| Size budget per page, slimming during consolidation ("sleep-time" work after the task) | [Sleep-time compute](https://arxiv.org/abs/2504.13171) |

## Division of labour

- **Code owns the books**: `index.md`, win/loss evidence, status, `last_verified`, `log.md`, `raw/runs/`,
  size checks. The model cannot edit these, and a rewrite of a page clears its past losses.
- **The Librarian owns the content**: pages under `apps/` (app-maps: navigation, where data hides, UI
  traps), `workflows/` (parameterised procedures with a Verify line) and `lessons/` (one strategy each).
- Demotion is deliberately slow (3+ losses and more than twice the wins): a failed task is weak
  evidence against any one page it used.

## Known limits

Evidence is per task, not per page, so blame is diffuse. There is no scheduled lint pass yet (orphans,
contradictions, stale `last_verified`); consolidation only slims pages that exceed the size budget.
