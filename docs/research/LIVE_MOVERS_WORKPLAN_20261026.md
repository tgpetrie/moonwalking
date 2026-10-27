# Live mover scoring: priority and work split — 2026-10-26

The immediate dashboard is the primary product question: **which newly appearing
move is developing, continuing, extended or failing right now?** Give that work
its own numeric, horizon-labelled score. The daily/fundamentals experiment is a
separate lane and does not answer this minute-scale question.

This checkpoint is an inventory and work brief, not a fitted model or a change
to the dashboard. Evidence is under
[`results/live_movers_scope_20261026/`](results/live_movers_scope_20261026/).

## What is actually available

The inspected runtime checkout is `Moonwalking-Runtime` at `ed3e231`; its
`backend/live_ranking.py` already calculates a deterministic numeric score using
1m/3m/1h moves, volume, confirmation, persistence and extension/liquidity terms.
The board records forward 5/15/30/60-minute outcomes and point-in-time feature
snapshots. A new formula should be compared with that existing score and the
plain percentage-move ranking.

Read-only local inventory, captured on October 26 in Pacific time:

| Evidence | Observed scope | Implication |
|---|---|---|
| Price snapshot store | About 24 hours retained; last 999 BTC intervals had median 23 seconds and maximum 110 seconds | Sub-minute observations exist, but a long, uniformly sampled 30-second history has not been established |
| Candle archive | Recorded window granularities 60 and 3,600 seconds | A one-minute candle cannot establish the path inside that minute |
| Newest 1,000 signal rows | All have feature snapshots; 950 already have 5m labels in this sample | Existing minute-scale work has a starting point; incomplete new outcomes need maturity handling |
| Newest 1,000 board rows | All have feature snapshots; 978 already have 5m labels in this sample | The displayed-board population can be studied directly |
| Separate fresh 1,000-board-row availability sample | 1m and 3m moves populated in all rows; quote-volume USD and realized-volatility fields populated in none | Audit the recording path before promising a richer board formula |
| Same fresh signal sample | Quote-volume USD in 157/1,000; realized volatility in 1,000/1,000 | Feature availability differs between recording paths; field names alone are not usable data |

The two recent samples were taken at different times. They are **bounded samples,
not full-history coverage, independent sample sizes or performance estimates**.
Key-presence counts and non-null counts are separate artifacts. Categorical
`normal`/`neutral` values also require provenance and variation checks.

The inspected board-ranking call in `backend/app.py` does not supply
`volatility_snapshot` or `liquidity_snapshot`, while the signal-feature call
does. This is a concrete candidate explanation for missing retained board
features. Trace the actual writer and add a regression before changing it;
this checkpoint does not patch or restart the collector.

The current stored price features are **1m, 3m and 1h**, not 30 seconds. Verify
the UI's window and refresh semantics. A true 30-second feature needs observed
prices on both sides of that window with explicit age/gap rules and honest
coverage. Do not derive it from an update timer or invent a sub-minute path
from one-minute OHLC data.

## Formula to investigate

Build a **0–100 live move-quality rank** from a small, explainable function of:

- movement relative to that coin's own volatility and the contemporaneous market;
- acceleration versus its preceding, non-overlapping interval;
- unusual quote-volume participation where genuinely measured;
- persistence and independent confirmation;
- extension/exhaustion, freshness and trading friction.

Weights and even the useful direction of an effect must be estimated in the
training/discovery period, not assumed from the words "momentum" or "volume".
Initially, use only factors the frozen data actually supports. Spread and
numeric order flow remain optional until their recorded coverage is established;
categorical liquidity/pressure flags are not numeric bid/ask or trade-flow history.

A precise candidate is `score = 100 * percentile_rank(predicted 5m continuation)`
within an explicitly eligible cohort, using a small regularized model. That is
an **ordinal score, not a probability**. Direction, forecast horizon and data
reliability must remain explicit. An exhausted upside move should not receive
a stronger continuation interpretation merely because its past gain is larger.

The earlier corrected scoring brief found a negative short-horizon relationship
on its selected signal sample (section C1 of `BHABIT_SCORING_RESEARCH.md`). Treat
that as a warning about extension and selection, not permission to invert the
old score and claim a trading edge. It has not been rerun in this inventory.

## First experiment contract to freeze before fitting

1. Start with **new board-entry episodes**, timestamped at first server
   publication/observation. A browser impression timestamp is not currently
   established. Keep up and down boards separate; down-board continuation is
   a risk-context result, not a short-selling recommendation.
2. Primary horizon: the next **5 minutes**. Secondary: **15 minutes**. These are
   forward horizons; 30s/1m/3m are input windows. Add shorter forward horizons
   only when their actual grading data is available.
3. Freeze field definitions, identity rules, feature availability by date,
   episode/cooldown policy, minimum usable history and chronological splits.
   Audit any available historical minute candles separately for replay scope.
   The newest 1,000 rows are an inventory sample, not the training set.
4. Compare with percentage-move ranking, current live strength and a small
   price/volume baseline on **identical episodes**. An event-selected result
   applies to the displayed population; a whole-universe claim needs the
   contemporaneous eligible universe or a separately validated replay.
5. Features must be known at the decision timestamp. Use **closed** volume bins;
   the final volume of the still-open minute is future information. Future
   universe ranks, end-of-episode persistence and later data-quality updates
   must not become entry features.
6. Purge/embargo overlapping labels and cluster uncertainty by time/episode.
   Repeated appearances of one coin are not independent experiments. Report
   distinct time blocks, missingness and regime coverage alongside row counts.
7. Evaluate continuation/exhaustion separation and favorable/adverse excursions,
   delayed-entry sensitivity and gross versus cost-adjusted outcomes. The board
   table has both gross and net fields: avoid deducting its estimated costs
   twice. Historical last-price grades are not executable fills. Fee scenarios
   and spread assumptions must be explicit; absent quotes stay absent.
8. Freeze the analysis on discovery, test once, then observe a versioned score
   alongside the current dashboard before considering a visible ranking change.
   A null result is an acceptable outcome. No live weights change in this task.

## Who does what now

| Worker | Concrete assignment | Boundary / next deliverable |
|---|---|---|
| **Codex** | Trace board versus signal field retention; freeze a reproducible episode/feature-coverage inventory and the minute-scale experiment contract; review implementations and results | Primary immediate-board lane. First deliverable: which fields/dates are genuinely usable and what recording fix is required |
| **Local Qwen 9B** | Draft data dictionaries and triage reports generated by deterministic missingness/staleness/duplicate checks | Source-bounded packets; code calculates counts. No invented weights or unsupervised repository edits |
| **Local Qwen 14B** | Draft regression cases for the retention path, review specific feature traces and help turn verified findings into clear explanations | Hosted-agent review remains responsible for statistics and final correctness |
| **Claude** | Its fundamentals comparison driver now exists at `058d740` with a reported ready phase; Codex still needs to review it before outcomes. Keep that checkpoint separate. For the live lane, implement the frozen short-horizon comparison after the data contract is ready | Separate branch/worktree for minute-scale code; no mixing daily/fundamental features into a 30-second decision |
| **Gemini** | Independently verify timestamp, trade-side, spread and update-frequency semantics of the existing Coinbase sources; critique whether proposed real-time inputs were available before a move | Exact primary documentation/endpoint evidence and recorded availability; no new vendor/cohort expansion needed for this first comparison |

These are handoff assignments; no messages were sent to separate Claude/Gemini
chats in this task. No separate cloud agent was spawned.

## Local jobs actually run

Ollama was stopped. Its already-installed server was started locally, then two
bounded jobs ran sequentially: 9B data-QA drafting and 14B protocol critique.
Both requests and first responses are saved, with no model tools or filesystem
access. They received public schema/coverage metadata, not holdings or keys.
Both models were unloaded after completion; the local server is available.

The drafts need correction before use:

- 9B correctly noticed the 110-second sampled price gap, but incorrectly treated
  `1000` key-presence counts as actual feature values. Reject that claim. Missing
  minute OHLC fields do not by themselves make a volume table defective. Its
  suggestion of imputation is not accepted.
- 14B correctly flagged variable sub-minute coverage. Its claim that 1m/3m input
  windows prevent a 5m/15m forecast is incorrect, and its suggestion to relax
  closed-bin timing for cost efficiency is rejected. Inventory size must not
  be mistaken for the planned experiment's sample size.
- The first packet's field label was ambiguous; future packets explicitly name
  presence **counts**, separate from values.
  These two completed jobs demonstrate useful questions and the need to verify
  local drafts; they are not a model-quality benchmark or statistical signoff.

Next practical output is the board data contract and retention-path regression,
followed by a measured minute-scale formula. Keep the immediate dashboard's
purpose central throughout the longer-horizon research.
