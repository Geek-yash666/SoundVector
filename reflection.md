# Reflection

## What are the limitations or biases in your system?

- **Popularity bias.** Popularity is a ranking signal and a tie-breaker, so mainstream
  hits surface more readily than deep cuts. Charting tracks are also the only source of
  the "co-listen" training pairs, which nudges the embedding space toward popular music.
  The `vibe` mode (popularity weight = 0) exists partly to counteract this.
- **Metadata gaps.** ~27% of tracks resolve to "Unknown Artist" because the source data
  lacks a usable artist field for them. The underlying artist *grouping* is still correct
  99% of the time (used for training and capping), but the display and the DJ's ability
  to name an artist suffer.
- **Genre-vocabulary bias.** The mood model is only as good as the crowd-sourced genre
  tags. English-language and Western genres dominate the tag vocabulary, so mood queries
  work best for those; regional genres (e.g. specific South-Asian or Latin styles) are
  coarser. Mood→valence is the weakest axis: "happy dance party" reliably retrieves
  energetic, danceable tracks but not necessarily high-*valence* ones, because dance/EDM
  tags span a wide valence range.
- **Cold catalog only.** With no real user interaction logs, "collaborative" signal is
  approximated from chart co-occurrence. Genuine personalization (the profile) needs the
  user to like/skip enough tracks first.
- **Feedback-loop bias (by design, latent).** As the profile blends into the query
  vector, it can create a filter bubble — reinforcing a user's existing taste. The
  `discover` mode and an exploration slot are the intended counterweights.

## Could your AI be misused, and how would you prevent that?

The recommender itself is low-risk, but a few realistic misuses:

- **Popularity/`popular`-mode gaming** to astroturf specific tracks. Prevention: cap any
  single artist per list (already enforced), and don't let external input rewrite the
  popularity signal.
- **The RAG DJ hallucinating facts** — stating fake chart positions, release dates, or
  "artist X endorses Y". Prevention is built in: the DJ is prompted to use *only* the
  retrieved attributes, and the `GroundednessChecker` verifies every mood/genre/artist
  claim against those facts, flagging unsupported ones and lowering the groundedness
  score. A test injects a false claim and asserts the checker catches it.
- **Prompt injection** via track metadata (a track named "ignore instructions and…").
  Because the DJ prompt only passes structured numeric attributes and short names, and
  the checker validates outputs, injected instructions can't introduce ungrounded facts
  without being flagged. A stricter allowlist on names would harden this further.
- **Inferred-mood sensitivity.** Taste/mood data can be personal. Profiles are stored
  locally as plain JSON and never transmitted; a production version would need consent
  scoping and deletion (noted in `future.md`).

## What surprised you while testing your AI's reliability?

- **How much of the "old vs new" preference was bugs, not architecture.** The old
  recommender *looked* more coherent partly because it repeated artists and even the same
  song ("Dandelions" twice). Once the new engine got version-dedup and adaptive artist
  caps, blind voting flipped to 3–1 for the new one.
- **The learned space clusters extremely tightly by artist.** The 500 nearest neighbors
  of a Lana Del Rey track contained only *two* artists — which silently starved short
  recommendation lists until I added an adaptive candidate-pool expansion. A metric
  looking healthy (high same-artist recall) was hiding a diversity failure.
- **Groundedness caught my own mistakes.** While writing a "clean" test blurb I described
  a high-energy track as "mellow" — the checker correctly flagged it. The guardrail found
  a human error, not just a model one.
- **In-batch accuracy is a misleading raw number.** The Colab model's 0.33 looked worse
  than a quick local run's 0.68, until accounting for batch size (picking 1-of-32768 vs
  1-of-2048) — the "worse" number was the far stronger model.

## Collaboration with AI during this project

**A helpful suggestion.** When mood queries were misrouting ("sad rainy night" returning
a Train song), the AI traced it to the *artist* matcher, not search: short artist names
like "Rain" and "RK" were substring-matching mood words ("**rain**y", "wo**rk**out").
The fix — requiring the whole query to fuzzy-equal the artist name rather than merely
contain it — was the right root-cause fix, and it also explained a class of similar bugs.

**A flawed suggestion.** The AI first proposed training the MoodToVector Ridge heads with
`solver="cholesky"` for speed. That crashed — cholesky can't fit an intercept on sparse
input — and the initial attempt also would have been slow because of a per-row Python loop
building the corpus. Both had to be corrected: append a constant column as the intercept,
and vectorize the corpus construction. The lesson: an AI's first "optimized" path can be
confidently wrong about a library constraint, and empirical testing (it timed out, then it
errored) is what surfaced it — not the plan.

**Overall.** The most effective pattern was *reproduce-before-fix*: every reported problem
(search bugs, the 2-recommendation starvation, the A/B loss) was first turned into a small
diagnostic script that confirmed the mechanism, so fixes addressed causes rather than
symptoms. The AI was strong at generating that diagnostic scaffolding quickly and honest
about trade-offs, but needed a human-in-the-loop to define what "good recommendations"
actually feel like — which is exactly what the blind A/B test formalizes.
