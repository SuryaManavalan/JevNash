# Benchmarks

All numbers are from live runs on 2026-09-18 against the real Jev and Anthropic APIs. Claude costs are
list price (Sonnet 5 $2/$10, Haiku 4.5 $1/$5, Opus 5 $5/$25 per Mtok). **Jev cost is an assumption**
($0.50 per Mtok, `JEV_USD_PER_MTOK`): TypeSafe publishes no price. Samples are small (8-10 tasks per
round), so treat differences of one task as noise.

## Enterprise workstreams (`--env suite`)

Score per task = fraction of state checks that hold, zero if any harm check fails. Each round ran the
task families in rotation with fresh random data; the brain carried over between rounds.

| Round | What changed | Tasks | Mean score | Full passes | $ / task |
| --- | --- | --- | --- | --- | --- |
| A | Static Librarian plan; Jev tracks progress and may finish | 4 | 0.25 | 1 | 0.21 |
| B | + working-memory notes, plan-wide progress Choice, cycle guard | 4 | 0.63 | 2 | 0.14 |
| C | + two-stage typing (plain integers had been untypeable), read-then-refine planning | 8 | 0.63 | 5 | 0.18 |
| D | Haiku foreman replaces the static plan; only the foreman may finish | 8 | 0.98 | 7 | 0.17 |
| E | + app confirmations recorded, shorter page excerpt for Jev, Haiku briefs once the brain is mature | 8 | 0.88 | 7 | 0.17 |
| F | + verification subgoals rejected with a constrained second opinion | 8 | 0.98 | 7 | 0.13 |

Rounds A-F used four task families (refund, update_contact, reorder, escalate). Two 4-task runs
between B and C are not tabled: one was invalid (a half-applied patch of mine made every typing action
fail) and one, right after two-stage typing landed, scored 2 of 4 and was superseded by round C.

Recurring failures: `refund` typed the wrong amount twice (the value picker chose a different number on
the page); `reorder` once ordered an extra SKU. `escalate` (three tickets x CRM lookups) passes but
still uses the full 60-step allowance.

Where the money goes in round F (8 tasks, $1.06): Jev ticks $0.32, foreman $0.2x, briefs, rescues and
consolidation the rest. LLM spend still dominates.

## Drawing challenge (`--env paint`, scene `house`)

Score = pixel similarity to the reference at 32x32, normalised so a blank canvas is 0. The planner LLM
gets the reference as a text grid of palette colours (no vision needed) and writes one stroke per
subgoal; Jev binds tool and colour names to controls once; strokes replay as macros.

| Planner | pixel-art | anime | photo-realistic | $ per picture |
| --- | --- | --- | --- | --- |
| Haiku 4.5, single pass | 0.69 | 0.07 | 0.69 | 0.01-0.02 |
| Haiku 4.5 + closed-loop repair (up to 2 passes) | **0.87** | **0.85** | 0.62 | 0.02-0.05 |
| Sonnet 5 (low effort), single pass | 0.86 | 0.87 | 0.92 | 0.04-0.08 |
| Opus 5 (low effort), single pass | 0.86 | 0.76 | 0.91 | 0.06-0.07 |

Findings: the cheapest tier reaches Sonnet-level pixel-art and anime once the harness closes the loop
(diff the canvas against the reference row by row, ask for corrective strokes). It does not help at
32x32 photo-realistic, where Haiku's repairs made the picture worse. Opus bought nothing over Sonnet.
Executing a picture costs about half a cent of Jev either way; before intent macros the same picture
cost $0.64 and drifted off-plan.

"Style" here is enforced by instructions and grid size, and the score measures fidelity only; nothing
yet judges whether an image actually looks anime or photo-realistic.
