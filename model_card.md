# 🎧 Model Card: Agentic Music Recommender

> **Scope.** Sections 1–10 describe the original Module 3 system (VibeMatch 1.0).
> Sections 11–16 cover the Project 4 extension: the agent loop, knowledge retrieval,
> explanation voices and the evaluation harness. The graded responsible-AI reflection
> is in sections 12–15.

## 1. Model Name

**VibeMatch 1.0**, a content-based music recommender with switchable ranking modes and a
diversity re-ranker. Extended in Project 4 as **VibeMatch Agent 2.0**: the same scorer
driven by a planning/critiquing agent that accepts natural language.

---

## 2. Goal / Task

VibeMatch suggests the top 5 songs from a small catalog for one listener.

- It takes a taste profile, such as favorite genre, mood and target energy.
- It scores every song against that profile.
- It returns the best matches with a score and a reason for every point.

The goal is transparency. Every recommendation can be traced back to a specific rule.

---

## 3. Data Used

- **Size:** 20 songs in `data/songs.csv`. 10 came with the starter project and 10 were added.
- **Genres (12):** pop, lofi, rock, ambient, jazz, synthwave, indie pop, hip-hop, indie rock, edm, r&b, acoustic.
- **Original features:** genre, mood, energy, tempo (BPM), valence, danceability, acousticness.
- **5 advanced features added:**
  - `popularity`: 0 to 100.
  - `release_decade`: 1960s to 2020s.
  - `detailed_mood_tag`: a finer mood label, such as euphoric, nostalgic or aggressive.
  - `instrumentalness`: 0 to 1, how much of the song has no vocals.
  - `speechiness`: 0 to 1, how much of the song is spoken word, such as rap verses.

**Limitations of the data:**

- The songs and artists are fictional. Their numbers were made up to look realistic, not measured from audio.
- Mood labels are subjective and were assigned by one person with AI help.
- Genres are uneven. Lofi has 3 songs. Pop, jazz, hip-hop, EDM, R&B and indie rock have 2 each. Rock, ambient, synthwave, indie pop and acoustic have only 1 each.
- Large parts of music are missing, including classical, country, Latin, K-pop, metal and non-English music. The catalog also has no song labeled sad.
- `valence`, `instrumentalness` and `speechiness` are stored but not used in scoring yet.

---

## 4. Algorithm Summary

Think of it as a judge with a scorecard.

1. **Matching labels earns fixed points.** If the song's genre is one you like, it gets points. The same goes for mood, mood tag and decade.
2. **Being close earns partial points.** If you want energy 0.8 and the song is 0.7, it is 90% close and earns 90% of the energy points. The same applies to danceability and acousticness.
3. **Optional bonuses.** Matching tempo, or being popular, earns a small bonus, but only if you ask for it.
4. **Add it all up.** The total is the song's score.
5. **Rank the catalog.** Sort all songs from highest to lowest score.
6. **Keep the list varied.** While picking the top 5, a song loses 0.75 points if its artist is already on the list, and 0.35 points if its genre already appears twice. The list is re-sorted after each pick.

**Ranking modes.** The same steps run with different point values:

- `balanced` is the default and weighs everything moderately.
- `genre_first` doubles the value of a genre match.
- `vibe_and_energy` cares most about energy and mood, and much less about genre.

---

## 5. Observed Behavior

**What works well:**

- Listeners with a clear, well-covered taste get strong, sensible results. The lofi study listener and the indie roadtrip listener both got top matches that hit 4 or 5 preferences at once. The default pop listener's #1 song hit all 3 of its preferences.
- Every result explains itself, so it is easy to see why a song ranked where it did.

**Mitigation: the diversity penalty.** For the lofi listener, Focus Flow scores 5.21 before any penalty. It shares an artist with #1 (LoRoom) and is the third lofi song, so it drops to 4.11 and is labeled with both penalties.

Experiment 3 ran the same profile with the penalty off and on, and the evidence is less strong than the rule suggests. The top five contained the same five songs both times. The only change was the order: Focus Flow moved from #3 to #4, and Porch Light Letters (acoustic) moved from #4 to #3. The acoustic and ambient songs were already in the top five without the penalty, so they should not be credited to it. The penalty is a nudge, not a fix: LoRoom still has two songs in the top five.

---

## 6. Limitations and Bias

**Biases and weaknesses:**

- **Filter bubbles.** The scoring rewards sameness. In `balanced` mode a genre match is worth more than any single other feature, so a listener keeps hearing their favorite genre.
- **Genre over-weighting.** In `genre_first` mode, the two hip-hop songs scored over 5.2 and the next song scored 2.34. With a bigger catalog this mode would return only one genre.
- **Small-genre unfairness.** Hip-hop fans had only 2 songs to choose from, and neither was labeled energetic or aggressive. Their best score was 4.34, compared with 6.61 for the lofi listener. The system serves well-covered tastes better.
- **Cold start.** There is no listening history. A new user must describe their taste in the catalog's exact words, and the system cannot learn from what they play or skip.
- **Exact-label matching.** "indie" does not match "indie rock", so a small wording difference can hide a perfect song.
- **Popularity bias (opt-in).** Turning on `prefers_popular` boosts songs that are already popular.

**Weakness found by the edge-case profile.** The edge-case listener wants classical music in a sad mood, but the catalog has no classical songs and no sad songs, so the system gives zero genre and mood points. Nothing gives partial credit for related labels, so the ranking is decided by energy, tempo and popularity alone. The top five is mostly loud rock, EDM and pop (Storm Runner, Gym Hero, Laser Tide, Drop Zone and Sunrise City), and the output never tells the listener that nothing in the catalog is close to their taste. This is unfair to listeners whose taste falls outside the catalog. A fairer version would give partial credit for related labels, such as indie and indie rock, and warn the user when the catalog has no matches.

---

## 7. Evaluation Process

**Five listener profiles** were run in `balanced` mode with diversity on:

- **High-Energy Hip-Hop / Workout.** Top result: Concrete Crown (hip-hop), 4.34. Mostly yes. Genre matched, but no hip-hop song had the energetic or aggressive label.
- **Chill Lofi / Late-Night Study.** Top result: Midnight Coding (lofi), 6.61. Yes. The penalty moved Focus Flow from #3 to #4.
- **Upbeat Indie / Nostalgic Roadtrip.** Top result: Ferris Wheel Summer (indie rock), 6.47. Yes, matching 5 preferences.
- **Default Pop / Happy.** Top result: Sunrise City (pop), 4.97. Yes, matching all 3 preferences (genre, mood, energy).
- **Edge Case: Sad but High-Energy Classical Fan.** Top result: Storm Runner (rock), 2.25. No, and the catalog cannot match this listener. Every point came from energy, tempo and popularity, which is the failure described in Section 6.

**Mode comparison.** The hip-hop profile was run in all three modes.

- `balanced` and `genre_first` kept hip-hop at #1 and #2.
- `vibe_and_energy` pushed hip-hop down to #5, behind aggressive pop, rock and EDM songs.

This confirmed that the weights, not the code, control what the user sees.

**Diversity comparison.** The lofi profile was run with the penalty off and on. The top five was the same set of songs in both runs, so the penalty changed the order and not the membership of the list.

**Pairwise comparisons:**

- **Hip-Hop vs Lofi.** Lofi scores much higher, and the lists share no songs. Lofi matches genre, mood and tag. Hip-hop has no energetic or aggressive songs, so it earns only genre and energy points.
- **Hip-Hop vs Indie.** They share only Gym Hero (#4 in both). Each list is driven by its own genres.
- **Lofi vs Indie.** No shared songs, and the top scores are close (6.61 and 6.47). Both genres are well covered.
- **Pop/Happy vs Indie.** Four of five songs are shared. The indie profile's decade and nostalgic preferences lift Ferris Wheel Summer to #1.
- **Pop/Happy vs Edge Case.** They share Gym Hero and Sunrise City. The edge case has no genre or mood matches, so its scores are much lower (2.25 vs 4.97).
- **Hip-Hop vs Edge Case.** They share Laser Tide, Gym Hero and Storm Runner. Hip-hop keeps its genre-matched songs on top, while the edge case is ranked only by energy and tempo.

**Why "Gym Hero" keeps showing up.** Gym Hero appears in four of the five lists: #4 for the hip-hop listener, #2 for the default pop listener, #2 for the edge-case listener and #4 for the indie listener. In plain terms, it is a loud, fast workout song with a pop label. The scoring rule does not ask whether a song fits the listener overall. It adds up separate points for each thing the song shares with the profile. Gym Hero is pop, so pop listeners get genre points. Its energy is 0.93, near the top of the scale, so anyone who wants high energy gets energy points. Its tag is aggressive, so the hip-hop listener gets tag points as well. Its mood is intense, which matches none of these profiles, so it earns no mood points. A mismatch only means zero points, so a song can rank high on genre or energy even when its mood is wrong.

**Automated tests.** 23 pytest tests check:

- CSV loading and type casting.
- Clear errors for a missing file, a bad number (including the line it is on), an unknown mode or a negative `k`.
- Exact point values for each scoring rule.
- Case-insensitive and multi-genre matching, and an unknown genre or mood falling back to numeric features.
- Both diversity penalties.
- Duplicate song entries are kept by the ranking and the diversity re-rank.
- Songs missing a feature are skipped instead of raising a `KeyError`.
- That the input song list is never modified.

**What was surprising:** the "hip-hop workout" listener's #1 song in `vibe_and_energy` mode was a pop song. Reading the reasons made it clear why: the pop song matched the "aggressive" tag and the energy target, and genre was worth very little in that mode.

---

## 8. Intended vs. Non-Intended Use

**Intended use:**

- Classroom exploration of how recommenders turn data into ranked lists.
- Experimenting with weights, modes and fairness ideas on a small, readable dataset.
- Demonstrating explainable scoring, where every point has a reason.

**Not intended for:**

- Real users or a real music service. The catalog is tiny and fictional.
- Making claims about real artists, genres or listeners.
- Any decision that matters, such as artist payouts, promotion or charts.
- Judging music quality. A high score means "close to this profile", not "a good song".

---

## 9. Ideas for Improvement

- **Collaborative filtering:** learn from what similar listeners enjoyed, so the system can find songs a user would not have described themselves.
- **Learned embeddings:** represent songs and users as vectors learned from audio or listening data, instead of hand-picked weights and exact labels. Related genres like "indie" and "indie rock" would then land close together.
- **Implicit feedback:** use skip rates, replays and listening time to update a profile automatically, which addresses cold start over time.
- **Use the unused features:** add valence, instrumentalness and speechiness to scoring. Instrumentalness is a natural fit for a study playlist.
- **Fuzzy genre matching:** treat related genres as partial matches, and handle moods the catalog does not contain (such as "sad") by mapping them to close labels.
- **Smarter diversity:** reward novelty, such as a new decade or mood, not only penalize repeats.
- **A bigger, balanced catalog** so every genre has enough songs to compete fairly, including classical and sad-mood songs.

---

## 10. Personal Reflection

The most important takeaway was that the essence of recommendation lies in the values assigned to items. When agreeing to assign the genre match a weight of 2.0 and the mood match 1.5, the recommendation process moved from something seemingly trivial to a process that will determine the songs for all listeners. Using the `vibe_and_energy` option allowed a hip-hop listener's recommendations to turn into pop, rock and EDM without changing anything in the model.

I was also shocked at how limited fairness is by the data. While it is true that the hip-hop profile cannot get nearly the same performance as the lofi profile, it has little to do with the algorithm being biased toward lofi, since the catalog has fewer hip-hop tracks than lofi ones, and none of them match the requested mood. The implication of this is that my attitude towards some applications, specifically Spotify, has changed. If a recommendation seems to be too repetitive or fails to suit my tastes, it might not be because the algorithm does not know me well enough, but rather due to the catalog, labels or weights in the end.

I thought that a weighted sum of just a few numbers would feel mechanical. However, it turned out that the top lists were actually more like genuine recommendations because of the reasons behind the inclusion of each song: one belongs to a certain genre, another fits the energy. A score of 2.25 for the edge-case listener makes it clear that a score reflects a proximity to this profile, not a good song.

The use of AI tools made it faster for me to complete this project, but I had to check over their work on numerous occasions. An audit performed using different agents, one checking the code and the other the documentation, detected a few mistakes that I had failed to see. The diversity re-ranking removed already-picked songs by object identity, so a duplicate song entry could be dropped, and it was fixed to remove songs by their position in the list instead. The `score_song` function also showed a `KeyError` for songs with missing features, and a bad numeric preference gave an unhelpful error message. The audit also pointed out that I had no profile for a listener whose taste was not in the catalog, so the edge case was added. I also could not rely on the AI-pasted output tables, so every table was regenerated from what the program actually outputs, and the Focus Flow hand calculation was checked against the code.

I am eager to explore the idea of implementing partial credit in connection to related genres as well as moods, and using the unused features (instrumentalness particularly) for a study profile. I would also like to test out the recommendations with actual listeners to find out if the ranking corresponds with what people would really want and not just verify whether the arithmetic is correct.


---

# Project 4 extension

## 11. What the extension adds

VibeMatch 2.0 keeps the original scorer and diversity re-ranker untouched and wraps them in
an agent that owns the preference dictionary a human used to write by hand.

| Stage | Responsibility | Module |
|---|---|---|
| Guardrail | Refuse empty, overlong or unrecognisable queries | `src/agent/query_parser.py` |
| Plan | Free text + retrieved knowledge into prefs, hard filters, requirements, ranking mode | `query_parser.py`, `hints.py` |
| Filter | Prune the catalog on stated thresholds and exclusions | `src/agent/constraints.py` |
| Act | Score and rank the survivors | `src/recommender.py` (unchanged) |
| Critique | Check the answer against the plan; score confidence | `src/agent/critic.py` |
| Revise | Concede the cheapest thing that could unblock the critic | `src/agent/planner.py` |
| Explain | Re-express the scorer's reasons in a chosen voice | `src/agent/voices.py` |

One change was made inside the original code: `instrumentalness` and `speechiness` were
given weights in all three ranking modes. Both columns existed in `data/songs.csv` and
carried no weight, so no request could act on them.

---

## 12. Limitations and biases of the extended system

These are in addition to the catalog biases described in section 6, which all still apply.

**Vocabulary bias.** The planner understands only words in its keyword tables, which were
built from this catalog's values. A listener who writes "shoegaze", "drill" or "música
clásica" is refused rather than served. The refusal is honest, but the set of people the
system can serve is exactly the set of people who already speak its vocabulary — and that
vocabulary is English-only.

**The knowledge corpus encodes my opinions as facts.** `knowledge/*.md` claims that focus
listening means near-instrumental music and that party listening favours popular tracks.
Those are defensible generalisations, not measurements, and they now actively reorder
results. A listener who studies to vocal hip-hop gets worse recommendations *because* of
retrieval, not despite it.

**Concession order is a value judgement.** The planner gives up decade before mood and mood
before genre. That encodes an assumption that genre matters most to listeners. It was not
validated against anyone.

**Catalog size limits the filter stage.** With 20 songs, filtering on a category would drop
the result set below five, so categorical requests are enforced only as critic requirements
rather than filters. On a real catalog they should be filters.

**Confidence is a heuristic, not a probability.** It combines normalised score, the share of
requirements satisfied, a 15% penalty per revision and a scaling by the share of the
original request still honoured. It is useful for ranking one answer against another and
should not be read as a likelihood of listener satisfaction.

**No feedback loop.** There is still no listening history, so the system cannot learn that
it was wrong. Its self-critique checks only whether it did what it was asked, never whether
what it was asked was any good.

---

## 13. Could this be misused, and how it is prevented

| Misuse | Why it matters | What the system does |
|---|---|---|
| **Laundering promotion as taste** | A weight table is easy to tilt so a label's tracks always surface, while the output still looks like an explanation | Every point is attributed to a named feature in the output, and `WEIGHT_STRATEGIES` is 30 lines of readable constants. A tilt is visible in a diff and in the reasons column |
| **Dressing a thin system up as intelligence** | "Agent" implies understanding the system does not have | Status is reported honestly: `best_effort` whenever part of the request was surrendered, with the surrendered items named, and confidence is scaled down accordingly. The system says "the catalog has nothing matching X" rather than quietly substituting |
| **Silently narrowing what someone hears** | Inferred constraints can hide whole genres without the listener knowing | Retrieval may only *add* soft targets; it can never create a hard filter. Only the listener's own words create an exclusion, and the diversity re-ranker still penalises repetition |
| **Treating the corpus as authoritative** | Hand-written notes reorder results and could encode worse assumptions than mine | Retrieved passages are named in the output with their source file and similarity score, so a listener can see which claim moved their results |

What it does *not* prevent: nothing stops someone editing `knowledge/*.md` to tilt results
while the reasons column still reads innocently, because the hints become ordinary scoring
targets. On a real deployment the corpus would need review and version history of its own.

---

## 14. What surprised me while testing reliability

**The agent could "succeed" by surrendering everything.** The loop's exit condition was "all
critic checks pass", and relaxing a requirement removes the check that was failing. So the
fastest route to a clean verdict was giving up the entire request. The first version
reported that as `accepted` with 0.85 confidence. Two fixes: a result whose requirements
were surrendered is reported as `best_effort` with the surrendered items listed, and
confidence is scaled by the share of the original request still honoured — the same run now
reports 0.42.

**Half of my revisions did nothing.** Relaxing `release_decade` changed the ranking not at
all, because its weight is 0.25 in `vibe_and_energy` — below the noise floor of the other
features. The agent was spending its revision budget on concessions with no effect. The loop
now compares rankings between passes and, on a repeat, switches ranking mode instead.

**The harness found my expectations wrong twice, not the code.** I asserted that
`"moody 1990s jazz"` should be accepted; the only 1990s jazz track in the catalog is
`relaxed`, so reporting best effort is correct. My "query too long" case was exactly 300
characters, which is not over a 300-character limit.

**A keyword table has sharper edges than I expected.** `"popular tracks"` was parsed as a
request for pop, because "pop" is a substring of "popular". Matching had to move to word
boundaries.

---

## 15. Collaboration with AI

I used Claude Code throughout: to pressure-test which extension to build, to write modules
and tests, and to review its own output. The pattern that worked was making it prove things
with runnable evidence instead of argument. Before committing to the agent design we ran a
20-minute throwaway spike against the real catalog to check whether the critic would ever
actually fire; it did, and it also exposed two design flaws that shaped the final
architecture.

**A suggestion I accepted: separating hard filters from weighted scoring.** My instinct was
to express "instrumental" as another weight, which is how everything else in the system
works. The spike showed why that cannot work: weights let a vocal track win on other
features, and `instrumentalness` had no weight at all, so the loop drained its preferences
to nothing and returned score-0 pop songs. Splitting a pruning stage from the scoring stage
fixed it and produced an answer the original design could not give at all — *nothing in the
catalog satisfies this, and here is the closest thing I have*.

**A suggestion I did not take: skipping the RAG stretch feature.** The recommendation was to
drop retrieval, on the argument that a 20-song catalog makes retrieval near-identity and the
corpus would be an hour of prose for no behavioural change. The reasoning was sound for the
version being proposed — retrieving song descriptions would have restated the CSV. I kept
the feature and changed its design instead: the corpus holds editorial knowledge the columns
cannot express ("focus listening means near-instrumental") plus catalog-coverage facts, and
those become scoring targets. That turned retrieval into something measurable — for
`"something for deep focus while coding"`, retrieval moves a vocal acoustic track off the
list entirely and promotes three instrumental tracks. I would not have gotten that from the
version I was advised to skip, and I would not have gotten it from the version I was first
advised to build either.

I also overrode the AI on the eval expectations twice, and both times the system was right
and I was wrong — see section 14. That is the main thing I would carry forward: write the
expected behaviour down before looking at the output, because reading the output first makes
any behaviour look expected.

---

## 16. Evaluation of the extension

### 16.1 Automated results

```text
$ python -m pytest -q
132 passed

$ python eval/run_eval.py
16/16 cases passed | mean confidence 0.52 | 3 guardrail rejection(s)
```

Coverage: 89% overall; 90–100% on every `src/agent` module. Full table in the README.

### 16.2 Human review pass

Manual review of the committed output in `logs/demo_run.txt`, judged against what a listener
would reasonably expect.

| # | Input | Criterion | Verdict | Note |
|---|---|---|---|---|
| 1 | `high energy hip hop to hype me up` | Top pick is hip-hop and genuinely high energy | **Pass** | Concrete Crown, hip-hop, energy 0.78 |
| 2 | `chill lofi for studying` | Low-energy instrumental lofi on top | **Pass** | Library Rain and Midnight Coding rank 1–2 |
| 3 | `chill acoustic 90s stuff for studying, nothing too poppy` | No pop present; surrendered items named | **Pass** | Reports giving up mood and decade; no pop in top 5 |
| 4 | `1990s instrumental hip-hop` | Keeps the instrumental requirement; does not pretend | **Pass** | Surrenders genre, confidence 0.31 |
| 5 | `instrumental lyrical music` | Refuses and names the blocker | **Pass** | Names both filters and the closest song |
| 6 | `moody late night r&b` | Mood and genre both honoured | **Pass** | Slow Burn Text, r&b, mood moody |
| 7 | `something for deep focus while coding` | Nothing vocal in the top 3 | **Pass with retrieval, fail without** | Without retrieval a vocal acoustic track ranks first |
| 8 | `romantic music` | Returns r&b romantic material | **Partial** | Correct songs, but confidence 0.99 with retrieval on (0.65 without) is far too high for a two-word request |
| 9 | `asdfghjkl qwerty` | Refuses with usable guidance | **Pass** | Lists three example queries |
| 10 | `chill acoustic 90s...` (no-RAG) | Same honest status without retrieval | **Pass** | Still best effort, different ranking |

8 clear passes, 1 conditional, 1 partial. The partial is the open issue, and it is worse
than it first looked: `"romantic music"` reports 0.99 confidence. Retrieval supplies an
energy target the listener never gave, the critic then finds every requirement satisfied —
because there were only two — and nothing in the formula accounts for how little was asked.
Confidence should fall when the request is vague, and currently it rises.

### 16.3 Baseline vs specialised output

Same recommendations for `"moody late night r&b"`, three voices. `plain` is the baseline
phrasing of the scorer's own reasons.

| Voice | Lines | Total words | Mean words/line | Unique words | Digits |
|---|---|---|---|---|---|
| `plain` | 3 | 82 | 27.3 | 31 | 0 |
| `dj` | 3 | 62 | 20.7 | 36 | 0 |
| `critic` | 3 | 65 | 21.7 | 49 | 36 |

```text
plain:  Slow Burn Text: it is the r&b you asked for, the mood matches, the energy is close
        to your target, the acoustic balance fits and there is little or no singing.

dj:     Up next, Slow Burn Text by Jade Monroe — straight-up r&b — the mood is dialled in.

critic: Slow Burn Text (Jade Monroe) — the clearest fit in the catalog; genre r&b, mood
        moody, energy 0.48, acousticness 0.40, instrumentalness 0.01; score 6.22 (strong).
```

The differences are measurable, not just stylistic: `dj` is 24% shorter than baseline and
names the artist; `critic` carries 36 digits against the baseline's zero because it quotes
the feature values behind the score, and uses the widest vocabulary of the three. All three
are generated from the same `score_song()` reason strings by few-shot style templates, so no
voice can assert something the score does not support, and repeated runs are identical.

---

## 17. Future improvements

- **Scale confidence by request specificity**, so a one-word query cannot score as high as a
  fully satisfied detailed one (the open issue from 16.2).
- **Validate the concession order** with real listeners instead of assuming genre outranks
  decade.
- **Partial credit for related genres and moods**, so "indie rock" earns something from
  "indie pop" rather than nothing.
- **Make categorical requests real filters** once the catalog is large enough to survive it.
- **Review process for `knowledge/*.md`**, since its claims now move results and it is
  currently just my opinions in a markdown file.
- **Listening feedback**, so the critic can eventually check whether a recommendation was
  good rather than only whether it was compliant.
