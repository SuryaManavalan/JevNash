# Game-Agnostic Jev Harness — Design Handoff

## Goal

Build a harness that lets **Jev** (TypeSafe's System One model) play *any* game it's dropped into, without being told which game it is, and get better the more it plays.

"Game" is broad. It covers formal games (board, card, video, text games) and abstract "life games" such as closing a Jira ticket before sprint end or throwing a successful party.

The core idea is to split the work into three roles:
- **Jev is the policy.** It makes fast, calibrated decisions every tick.
- **A frontier LLM is the rulebook-writer.** It infers the game, its rules, its goals, and its action space from observations.
- **The harness is where learning happens.** Jev's weights don't change, so improvement comes from better menus, better criteria, and a learned value model.

Jev is a chooser over a bounded menu. The harness's real job is to produce a good menu and a good objective at every tick.

---

## Jev / TypeSafe facts (verified from console + docs)

- **Model:** Jev v13, requested as `model: "jev-latest"`.
- **Endpoint:** `POST https://api.typesafe.ai/v1/systemone`. Python (`typesafe_sdk`) and JS SDKs are available.
- **Request shape:** a `state` field (string or JSON; prefer named JSON fields) plus a `questions` map. Question IDs are for code only; the model never sees them.
- **Primitives:**
  - **Choice** selects one option from a set of up to 255. It returns `choice`, a `probabilities` value for every option, and a `confidence` value. Confidence is low when probability is spread across options and high when it peaks on one. Always include an `other` / `none` option when the list may not cover everything.
  - **Noul** returns P(yes). It has no separate confidence. A value near 0.5 means genuinely uncertain, not "medium".
  - **Score** returns a probability-weighted position on ordered levels you define. Each level should describe a concrete situation.
- **Parallelism:** all questions in one call run in parallel and cannot see each other's answers. Extra questions barely affect latency but do cost tokens. Batch speculative questions, and let code use only the answers that apply.
- **Structured criteria:** `instructions` and each criterion can be a string, an object, or an array. Object fields are free-form, so you can use fields like `what`, `not_for`, and `examples`. The model sees the field names as well as the values.
- **Limitations (stated by TypeSafe):** Jev is not good at System 2 (multi-step reasoning) tasks, is not trained on specialized domains, and is not a generative chat model. Planning and lookahead must live in code or the LLM.
- **Relevant docs:** doc index at `https://docs.typesafe.ai/llms.txt` (append `.md` to page paths for Markdown). Pages to read:
  - `concepts/how-to-build-with-system-one`
  - `concepts/state`
  - `primitives/choice`, `primitives/noul`, `primitives/score`
  - `confidence`
  - `sdk/python`, `sdk/javascript`
  - cookbooks: `hierarchical_classification`, `function_calling`, `autoresearch_feature_discovery`, `sde_cascade`
  - patterns: `fan-out`, `composite-scoring`
- **Precedent demos in the console:** Wikirace and Smarthome. Both are sequential-decision harnesses, so study them first.

### Minimal request example

```json
{
  "model": "jev-latest",
  "state": { "game_model": { "...": "..." }, "observation": { "...": "..." }, "history_tail": [] },
  "questions": {
    "move": {
      "type": "choice",
      "instructions": "Given the goal and current state, which action best advances toward winning?",
      "criteria": {
        "a1": { "what": "Move knight to f3", "heuristics": ["develops a piece early"] },
        "a2": { "what": "Push pawn to e4", "heuristics": ["controls the center"] },
        "other": "None of the listed actions is reasonable"
      }
    },
    "position_eval": {
      "type": "score",
      "instructions": "How close is the agent to achieving its goal?",
      "criteria": ["Clearly losing", "Behind", "Even", "Ahead", "Clearly winning"]
    }
  }
}
```

Verify exact Score and Noul request shapes against the live docs before coding.

---

## Architecture: a two-speed loop

### Slow loop: the LLM builds the Game Model

This loop runs occasionally, not every tick. Its output is a structured **Game Model**:

```json
{
  "game_hypotheses": [{ "name": "chess-like", "p": 0.7 }, { "name": "novel", "p": 0.3 }],
  "goal": "close ticket before sprint end",
  "state_vars": [],
  "action_schema": [{ "verb": "", "params": [], "preconditions": [] }],
  "win_signals": [],
  "lose_signals": [],
  "progress_signals": [],
  "heuristics": ["unblock dependencies first"],
  "open_questions": []
}
```

The steps are:
1. **Ingest and enrich the state.** Pull in structured data, text logs, screenshots (via vision → symbolic state), UI labels, and action/outcome history. Summarize long histories.
2. **Classify the game type with Jev.** Ask a Choice over the candidate taxonomy (cascade it hierarchically if it's large). Ask Noul questions for properties: turn-based? perfect information? clear win condition? multi-agent? resource management? Ask Score questions for dimensions like competitiveness.
3. **Generate hypotheses with the LLM.** Give it the state, recent transitions, and Jev's top-k game types. It returns competing rule sets as structured JSON (players, state vars, legal actions, transitions, goals, termination, hidden info), each marked as either well supported or speculative.
4. **Validate the hypotheses.** Jev Noul checks each one: "Is observed action X legal under these rules?" and "Does the observed next state match the predicted transition?" Code runs symbolic checks or short simulations where possible. Contradictions go back to the LLM for revision.
5. **Refine actively.** When hypotheses conflict, pick the test actions or clarifying questions that best discriminate between them. Keep a posterior over game identity and rules (Bayesian or particle-filter style).

**Re-run triggers:**
- surprise (the predicted outcome doesn't match the observed one)
- a new action type appears
- Jev confidence drops below a threshold
- periodic timer

### Fast loop: Jev pilots, every tick

1. **Enumerate options.** Instantiate `action_schema` against the current state. Use code for formal games and a cheap LLM call for abstract ones. The result is a concrete option list.
2. **Make one Jev call per tick** containing:
   - a `move` Choice over all candidate options (≤255)
   - a Score for `position_eval`
   - optional Noul feasibility/legality checks
   - optional speculative questions ("if opponent is bluffing, best move?"), where code uses only the ones that apply
3. **Act.** Threshold on confidence. If confidence is low or probability is split between the top two options, **escalate** that decision to the LLM (System 2).
4. **Log** the state, options, criteria, full probabilities, choice, confidence, and outcome.

This keeps LLM latency out of moment-to-moment play.

### More than 255 actions

Use hierarchical Choice with beam search (see the `hierarchical_classification` cookbook). Choose action type, then target, then parameter, keeping the top-K paths by joint probability at each level.

---

## How the harness gets better over time

1. **Rule refinement.** Prediction errors go to the LLM, which updates the Game Model. This makes the model more *correct* about the game.
2. **Heuristic library in the criteria.** After each episode, the LLM reviews the logs and writes a short list of what worked and what failed. These are written directly into option criteria objects (`what`, `not_for`, `examples`, `heuristics`). This makes the agent *better at* the game without retraining Jev.
3. **Option shaping.** Drop options that are always pruned or never chosen. Add macro-actions that led to wins (e.g. "standard opening X"). A better menu means better choices.
4. **Learned value model.** This is the main compounding signal. Ask the same Score dimensions every turn, pair them with outcomes, and train a small classical model (logistic regression or gradient boosting) on them. See `autoresearch_feature_discovery` and `composite-scoring`. Use it to re-weight Jev's move probabilities or break ties.
5. **Distillation later.** The logged (state, options, choice, outcome) tuples are training data for fine-tuning if that ever becomes available.

---

## Hard parts and mitigations

| Problem | Mitigation |
| --- | --- |
| Continuous or real-time actions (aiming, timing) don't fit a discrete menu | Add a quantization layer, or put a low-level controller under Jev so Jev picks intents |
| Sparse, delayed reward in abstract games | Have the LLM define intermediate `progress_signals`; score them each tick |
| Cold start with zero knowledge | Exploration mode: pick options that maximize information gain between hypotheses, not value |
| Perception errors on screen-based games | Treat vision-to-state as the main error source; keep observed and inferred state separate and check freshness before acting |
| Ambiguous or under-specified rules | Keep a distribution over hypotheses, never a single answer |
| Novel games | Expect genre-level classification plus partial constraints; lower confidence triggers more escalation |
| Typed output ≠ truth | Validate Jev's calibration in each target domain; tune thresholds on real data |

---

## Proving ground and success metric

- Start with **3–4 text or turn-based games of different genres**. Candidates include tic-tac-toe or connect-four, a simple card game, a text adventure, and a resource or negotiation game.
- Give the harness **no game name**.
- Measure two things per game over episodes:
  1. episodes until it beats a **random agent**
  2. episodes until it beats a **fixed-prompt, game-specific Jev harness**
- If the gap closes over episodes, that learning curve is the demo.

---

## Setup and first task for Claude Code

1. Install the TypeSafe skill:
   ```
   claude plugin marketplace add typesafe-ai/skills
   claude plugin install typesafe@typesafe-ai
   ```
2. Read the live docs listed above, especially the SDK page, `state`, `confidence`, and the hierarchical classification cookbook, before writing integration code.
3. Keep the TypeSafe API key server-side, in an env var.
4. **First milestone:** a minimal loop on one text game with these modules:
   - `GameEnv` interface: `observe()`, `legal_actions()` (optional; may be unknown), `step(action)`, `done()`, `outcome()`
   - `GameModeler` (LLM): builds and updates the Game Model JSON
   - `OptionEnumerator`: Game Model + state → option list
   - `JevPolicy`: one batched call per tick → choice, confidence, and eval
   - `Escalator`: sends low-confidence decisions to the LLM
   - `EpisodeLogger` + `Reflector`: post-episode heuristic updates written into criteria
   - `ValueModel`: trained on logged Score features vs outcomes (milestone 2)
5. Then add a second, different game and run it with no code changes except the env adapter. That tests the game-agnostic claim.
