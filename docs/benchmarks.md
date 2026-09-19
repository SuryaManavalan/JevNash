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
| G | + typed values limited to what the foreman quotes, foreman refresh every 4 ticks, broader verify guard; fifth family `double_charge` added | 10 | 0.90 | 9 | 0.11 |
| H | **Chaos mode** (labels and nav change per episode, session interstitials with a log-out decoy); foreman sees on-screen controls, cycle guard resets per subgoal | 10 | 0.80 | 8 | 0.12 |

Rounds A-F used four task families (refund, update_contact, reorder, escalate). Two 4-task runs
between B and C are not tabled: one was invalid (a half-applied patch of mine made every typing action
fail) and one, right after two-stage typing landed, scored 2 of 4 and was superseded by round C.

Step counts fell as well: `escalate` from the full 60-step allowance to 32-39, `refund` from 24-60 to 10-21.

Failures that recurred: `refund` typed the wrong amount twice (rounds D-F, before typed values were limited to
what the foreman quotes); `reorder` once ordered an extra SKU; `double_charge` failed 3 of 6 times because the
billing account number hides behind a collapsed "More" section and the foreman kept sending Jev to a
"Billing tab" that does not exist - the nav link of that name leaves the customer record. After the third
failure the brain wrote that trap down on its own (`brain/workflows/void-duplicate-invoice.md`); in chaos mode
the foreman also quoted dialog buttons ("Stay signed in"), which then got typed into search boxes (fixed after
round H: control labels are never typing candidates).

Where the money goes in round F (8 tasks, $1.06): Jev ticks $0.32, foreman $0.2x, briefs, rescues and
consolidation the rest. LLM spend still dominates.

## One continuous hour (`--env suite --chaos --minutes 60 --usd 5`)

A single unattended session, chaos mode on, five task families in rotation, brain carried over from
the rounds above. Log: `runs/shift_60min.log` (not committed).

| Measure | Result |
| --- | --- |
| Wall clock | 60 min, no crashes or restarts |
| Tasks finished | 41 |
| Full passes | 35 (85%); mean score 0.92 |
| Last 21 tasks | 20 full passes |
| Misses | `reorder` skipped one qualifying SKU 3 times; `double_charge` never found the hidden account number twice; `escalate` ran out of steps once |
| Harm checks tripped | 0 of the 6 misses came from a harm check: every miss was incomplete work, not damage |
| Spend | $4.21 total, $0.10 per task (Claude $2.82, Jev ~$1.38 assumed) |

The spend ceiling was $5, so pacing never had to throttle. At this rate an hour costs roughly $4 and clears
about 40 multi-app tasks.

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

## Live internet, read-only (`--env web_open --v2`, 2026-09-19)

First runs on real public sites, with the guardrails in `OpenWebEnv`: navigation confined to the start
domain, no password/e-mail/payment fields, and no controls that buy, sign in, register, post or delete.
There is no ground truth on the open web, so "done" is Jev's own judgement of the final page plus the
agent's notes; I checked each answer by hand.

| Site | Task | Steps | Answer the agent noted | Correct? | $ |
| --- | --- | --- | --- | --- | --- |
| books.toscrape.com | price of "A Light in the Attic" | 1 | GBP 51.77 | yes | 0.07 |
| en.wikipedia.org | search "Eiffel Tower", note height and completion year | 3 | 330 m to tip (300 m architectural), 31 March 1889 | yes | 0.07 |
| news.ycombinator.com | open comments of the #1 story, note title and points | 2 | title and points at the time | yes | 0.05 |
| docs.python.org | search "asyncio", open the library page, note first high-level API | 4 | "run Python coroutines concurrently..." | yes | 0.07 |
| developer.mozilla.org | site-search "flatMap", open the reference page, note return value | 4 | "A new array ... flattened by a depth of 1" | yes (second attempt) | 0.03 |

What the real web broke that the playground never did: a page-load timeout, a script context destroyed
mid-navigation, and MDN's search box living inside a web component's shadow DOM (invisible to the first
scanner; the first MDN attempt burned all 30 steps). All three are fixed. Jev's completion judge scored the
correct Wikipedia and Hacker News runs 0.82-0.83, under my arbitrary 0.85 bar; with failures scoring
0.02 the bar is now 0.7 - tuned on six runs, so treat it as provisional.

Nothing here logs in, pays, posts or submits. Tasks that do need credentials, an allowlist and approval
gates decided by the account owner first.
