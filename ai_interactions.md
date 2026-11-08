# AI Interactions Log

> This log covers the stretch features built with an AI coding agent (Claude Code): advanced song attributes, multiple ranking modes, diversity and fairness logic, and table-formatted output.

---

## Agentic Workflow (SF8)

**What task did you give the agent?**

The work was split into four multi-step tasks. Each was one prompt, and the agent read the repository, made the changes, ran the code and reported back.

1. Expand `data/songs.csv` to at least 20 songs across diverse genres and add 5 advanced attributes, then show the schema before touching any Python.
2. Implement `src/recommender.py`: CSV loading, scoring with multiple ranking modes, and diversity-aware ranking, without breaking the existing tests.
3. Update `src/main.py` to run three listener profiles and a mode comparison, and print ASCII tables.
4. Write the README, model card and this log.

**Prompts used (summarized):**

- *Step 1:* "Read data/songs.csv to see the exact existing columns... Expand data/songs.csv so it has at least 20 total songs across diverse genres (hip-hop, indie rock, lofi, EDM, R&B, acoustic, jazz, pop)... add 5 new meaningful columns... popularity, release_decade, danceability, acousticness, detailed_mood_tag... Show me the updated CSV schema and a summary of the 20 songs before we touch any Python code."
- *Step 2:* "Now let's implement src/recommender.py. Keep all existing function signatures intact... Define a WEIGHT_STRATEGIES dictionary supporting at least 3 modes... apply a repetition penalty (-0.75 for same artist..., -0.35 if the same genre appears more than twice)... explain how the Strategy Pattern and Diversity Penalty work."
- *Step 3:* "Update src/main.py to verify our recommender and run the Phase 4 multi-profile experiments... Format the terminal output using clean ASCII table formatting... Run `python -m src.main`... show me the exact CLI output."
- *Step 4:* "Complete all documentation files to hit every rubric requirement..."

**What did the agent generate or change?**

| Step | Files changed | Summary |
|---|---|---|
| 1 | `data/songs.csv` | Added 10 songs (now 20 across 12 genres) and 5 columns: `popularity`, `release_decade`, `detailed_mood_tag`, `instrumentalness`, `speechiness`. |
| 2 | `src/recommender.py`, `tests/test_scoring.py` | Implemented `load_songs` (with `csv.DictReader` and numeric casting), `WEIGHT_STRATEGIES`, `score_song`, `recommend_songs` and the greedy diversity re-ranker. Wired the `Recommender` class to the same logic. Added 15 tests. |
| 3 | `src/main.py`, `src/recommender.py`, `tests/test_scoring.py` | Added three profiles, the mode comparison and an ASCII table formatter. Made the import work with both `python -m src.main` and `python src/main.py`. Let preferences accept a list of genres. Added 1 test. |
| 4 | `README.md`, `model_card.md`, `ai_interactions.md` | Wrote the documentation with real CLI output. |

Commands the agent ran included `python -m pytest`, `python -m src.main` and a CSV range-check script.

**What did you verify or fix manually?**

- **A conflict in the prompt.** Step 1 asked for 5 "new" columns, but `danceability` and `acousticness` already existed in the starter CSV. The agent flagged this before writing any Python. It added `instrumentalness` and `speechiness` instead, so there are still 5 genuinely new columns.
- **An ambiguous rule.** "Same genre appears more than twice" could mean penalizing the 3rd song or the 4th. The agent chose the 3rd (`>= 2` already picked) and called it out so it could be changed.
- **Profiles that did not fit the data.** The profiles listed two genres ("lofi/acoustic") and two moods ("energetic/aggressive"). The agent added list support for genres and split the two moods into `mood` and `detailed_mood_tag`.
- **Data checks.** A script confirmed 20 rows, 15 columns per row, no empty cells, and every 0–1 value and 0–100 popularity in range.
- **Tests and CLI run.** All 18 tests passed after each step. `python -m src.main` exited with code 0 and no errors.
- **Hand-checked scores.** For example, Focus Flow: genre 2.0 + mood tag 1.0 + energy 1.27 + acousticness 0.93 displays as 5.20. The program's total is 5.21 because it sums unrounded values and rounds only the total, so the one-cent gap is display rounding. Subtracting 0.75 and 0.35 gives 4.11, which matches the CLI output.

**Review and verification (final audit session)**

- A multi-agent audit ran a code review (`python-reviewer`) and a documentation audit. It found the bugs and gaps listed below.
- **Diversity re-rank bug.** The re-rank removed songs by value, so a duplicate song entry could be dropped. Removal now uses identity. Regression tests cover duplicate entries.
- **Missing feature crash.** `score_song` raised a `KeyError` when a song lacked a feature. It now skips missing features. A test covers this.
- **Unhelpful numeric error.** A bad numeric preference gave an unclear error. The error now names the preference. A test covers this.
- **Stale tables.** The pasted tables in the README were out of date. They were regenerated from the current `python -m src.main` output and inserted by script, not typed by hand.
- **Missing profile and experiment.** The README lacked the edge-case profile and the diversity on/off experiment. Both were added with their real output.
- **Incomplete genre list.** The README listed only two genres with 2 songs. It now matches the model card.
- **Diversity claim corrected.** The lofi top five was described as an effect of the penalty. Experiment 3 showed the same five songs with the penalty off, so the penalty only changed their order.
- **Verification.** All 23 pytest tests pass. `python -m src.main` exits with code 0 and prints no errors.

---

## Design Pattern (SF10)

**Which design pattern did you use?**

The **Strategy pattern**, for multiple ranking modes.

**How did AI help you brainstorm or implement it?**

The prompt asked for a `WEIGHT_STRATEGIES` dictionary with at least three modes. The agent implemented each strategy as a *weight table*, not as a separate class or function. Every mode uses the same features and only the weights differ, so a table is the simplest form of the pattern (KISS):

- The scoring algorithm is written once.
- The "strategy" is the data that configures it.
- Adding a new mode is a one-dictionary change with no new code paths.

**Alternatives considered:**

- **(a) Subclass per mode with an abstract `score()` method.** Rejected. It adds boilerplate for what is only a difference in weights.
- **(b) An `if/elif` on the mode name inside `score_song`.** Rejected. It grows messy with each new mode and breaks the open/closed principle, because adding a mode means editing the scoring function.
- **(c) Chosen: a dictionary of weight tables (a data-driven Strategy).** Adding a mode means adding one dictionary entry.

The agent also added a test that every mode defines every weight, so a new mode cannot silently miss a feature.

**How does the pattern appear in your final code?**

- `WEIGHT_STRATEGIES` in `src/recommender.py` holds the three strategies: `balanced`, `genre_first` and `vibe_and_energy`.
- `_weights_for(mode)` selects a strategy and raises a clear `ValueError` for an unknown mode.
- `score_song(user_prefs, song, mode)` is the "context". It passes the chosen weights to `_categorical_points`, `_proximity_points` and `_bonus_points` and never checks which mode is active.
- `recommend_songs(..., mode=...)` and `run_mode_comparison()` in `src/main.py` switch strategies at runtime.

**Effect:** for the hip-hop workout profile, `genre_first` kept hip-hop at #1 and #2, while `vibe_and_energy` pushed the best hip-hop song to #5. The code was identical; only the strategy changed.

---

## Diversity & Fairness Logic

**The problem:** content-based scoring rewards songs that resemble what the user already likes. That creates a filter bubble: the same genre, and often the same artist, over and over.

**How the penalty works** (`_rerank_with_diversity` and `_apply_diversity_penalty` in `src/recommender.py`):

1. Score and sort all songs with `sorted()`.
2. Build the top-*k* list one pick at a time.
3. Before each pick, re-score every remaining song against the songs already chosen:
   - **-0.75** if its artist is already on the list.
   - **-0.35** if its genre already appears twice.
4. Re-sort the penalized candidates, pick the best, and repeat.
5. Each penalty is added to the song's reasons, so the user can see it.

The penalty depends on what has already been picked, so it has to be applied step by step. A single pass and sort would not work.

**Why it helps prevent filter bubbles:**

- **Artist fairness:** one artist cannot fill the list. LoRoom's second song lost 0.75 points for the lofi listener.
- **Genre fairness:** after two songs from one genre, other genres get a better chance. The lofi listener's top 5 included acoustic and ambient songs, but Experiment 3 showed they were in the top five with the penalty off too. For this profile the penalty changed the order (Focus Flow moved from #3 to #4), not which songs were recommended.
- **Transparency:** the penalty is visible, so the listener knows the system made a deliberate trade-off.
- **Not a hard ban:** a very strong match can still make the list after a penalty. Focus Flow stayed at #4. Relevance still matters most.
- **Can be turned off:** `apply_diversity=False` disables it for comparison.

---

## Agentic Workflow: Final Audit and Docs Pass

**Prompt used:** "complete all project phases using multiple agents"

**Agents used:**

- `python-reviewer`: audited `src/` and `tests/` and reported the diversity re-rank, missing-feature and bad-number issues.
- A documentation audit: checked the README, model card and this log against the program's real output.
- `doc-updater`: updated the documentation, including the new edge-case profile and the diversity experiment.

**Changes:**

- Code fixes made during the session: identity-based removal in the diversity re-rank, skipping missing features in `score_song`, and a named error for bad numeric preferences.
- README: five profiles, the edge case, the diversity on/off experiment, pairwise comparisons, and output tables regenerated from the program.
- Model card: a Limitations and Bias section, the five-profile evaluation, the Gym Hero explanation, and a reflection on AI help.
- This log: the review list above, the strategy alternatives, and this entry.

**Verification:** 23 pytest tests pass. `python -m src.main` exits with code 0. Every output table in the README was inserted from the program's output, and the diversity claim was checked against Experiment 3.


---

# Project 4: agentic extension

## Reasoning traces (stretch feature evidence)

Every agent run appends its full plan/act/critique/revise trace to
[`logs/agent_traces.md`](logs/agent_traces.md), written by `src/agent/trace.py`. The file is
append-only, so a session's history survives. `python -m src.agent_cli "QUERY" --trace`
prints the same trace to the terminal.

One trace is embedded below in full: the over-constrained query that the agent cannot fully
satisfy. It shows the planner relaxing the least specific requirement first (pass 1),
detecting that the concession left the ranking unchanged and switching ranking strategy
instead of spending another concession (passes 2–4), and finally reporting best effort with
the surrendered requirements named.

```text
## Query: "chill acoustic 90s stuff for studying, nothing too poppy"

- Status: **best_effort** (confidence 0.42, 1 counted revision over 5 passes)
- Outcome: Best effort: the catalog has nothing matching mood = chill, release decade =
  1990s, so that part of the request was given up. Everything else still holds.
- Surrendered: mood = chill, release decade = 1990s

### Reasoning trace

- **Pass 1** - mode `vibe_and_energy`, 18 song(s) survived the filter stage
    - PLAN: acousticness=0.7, instrumentalness=0.1, genre=acoustic, mood=chill,
      release_decade=1990s, energy=0.3
    - FILTERS: exclude genre pop
    - REQUIREMENTS: genre = acoustic; mood = chill; release decade = 1990s
    - ACT: Porch Light Letters (5.98), Midnight Coding (5.96), Library Rain (5.96),
      Spacewalk Thoughts (5.95), Slow Burn Text (4.53)
    - CRITIC: 5/7 checks passed, confidence 0.67
    - PROBLEMS: top pick has mood='relaxed', wanted 'chill'; top pick has
      release_decade='2000s', wanted '1990s'
    - ACTION: revise: relaxed release decade = 1990s
- **Pass 2** - mode `vibe_and_energy`, 18 song(s) survived the filter stage
    - REQUIREMENTS: genre = acoustic; mood = chill
    - ACT: Porch Light Letters (5.98), Midnight Coding (5.96), Library Rain (5.96),
      Spacewalk Thoughts (5.95), Slow Burn Text (4.53)
    - CRITIC: 5/6 checks passed, confidence 0.64
    - PROBLEMS: top pick has mood='relaxed', wanted 'chill'
    - ACTION: no-op concession, trying next: switched ranking mode to balanced
- **Pass 3** - mode `balanced`, 18 song(s) survived the filter stage
    - ACT: Porch Light Letters (5.24), Midnight Coding (4.03), Library Rain (3.94),
      Spacewalk Thoughts (3.90), Slow Burn Text (2.84)
    - CRITIC: 5/6 checks passed, confidence 0.64
    - PROBLEMS: top pick has mood='relaxed', wanted 'chill'
    - ACTION: no-op concession, trying next: switched ranking mode to genre_first
- **Pass 4** - mode `genre_first`, 18 song(s) survived the filter stage
    - ACT: Porch Light Letters (5.87), Midnight Coding (2.48), Library Rain (2.46),
      Spacewalk Thoughts (2.44), Slow Burn Text (1.62)
    - CRITIC: 5/6 checks passed, confidence 0.64
    - PROBLEMS: top pick has mood='relaxed', wanted 'chill'
    - ACTION: no-op concession, trying next: relaxed mood = chill
- **Pass 5** - mode `genre_first`, 18 song(s) survived the filter stage
    - PLAN: acousticness=0.7, instrumentalness=0.1, genre=acoustic, energy=0.3
    - FILTERS: exclude genre pop
    - REQUIREMENTS: genre = acoustic
    - ACT: Porch Light Letters (5.87), Slow Burn Text (1.62), Velvet Hours (1.56),
      Coffee Shop Stories (1.53), Midnight Coding (1.48)
    - CRITIC: 5/5 checks passed, confidence 0.85
    - ACTION: accept
```

## How AI was used on the extension

| Stage | What AI did | What I did |
|---|---|---|
| Choosing the extension | Generated four options with failure modes and a recommendation | Rejected part of the recommendation (keeping the RAG stretch) and set the scope |
| De-risking | Wrote a throwaway spike that ran the plan/critique loop against the real catalog before any production code | Required the spike before approving the design |
| Architecture | Proposed splitting hard filters from weighted scoring after the spike exposed the failure | Accepted; it is now the core of the extension |
| Implementation | Wrote modules test-first, 109 new pytest cases | Reviewed each failure and decided whether the test or the code was wrong |
| Evaluation | Built the golden-case harness | Wrote expectations; the harness then proved two of them wrong |

The full reflection, including the suggestion I accepted and the one I rejected, is in
[`model_card.md`](model_card.md) sections 14 and 15.
