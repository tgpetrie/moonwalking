# Instant radar: execution sequence - 2026-10-28

**This continues Gemini's existing early-warning design.** Shared market
data does not mean shared formulas. The instant radar, developing 3m move
read and near/short/medium/long outlooks answer different questions and need
their own declared targets and calibration. The historical three-input
comparison was a supporting benchmark; it did not fit or validate Gemini's
F1-F5 early-warning candidate. Its completed validation remains locked.

Owner: Codex implements and verifies the diagnostic and scoring work.
Gemini's reviewed proposal is the design input. Local models may help review
bounded traces and draft reports; deterministic code measures the results.

## 1. Finish the feed audit

A fresh committed-code attempt was launched on this Windows host at
2026-10-28 09:06 UTC, from `c217a52`, with PID 18960 at launch. It writes
`%USERPROFILE%\.moonwalking\analysis\feed_audit_20261028_1h` and generates
its own status/report. The earlier October 27 attempt remains preserved as
an interrupted 34-minute capture. It is not being reclassified as success.

Acceptance stays as defined in the
[prospective contract](LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md): paired
product/trade IDs, side evidence, deduplication, heartbeat monitoring and
REST reconciliation across an uninterrupted >=1h capture. Quiet or
contradictory products remain inconclusive and require additional evidence.
Do not weaken the gate based on this attempt's results.

## 2. Make the instant targets executable while collection is verified

Turn the existing proposal into a machine-readable contract and deterministic
label specification before inspecting prospective outcomes. Keep the
declared 30s/180s inputs distinct from the existing 5m/15m outcome horizons.
Define the onset algorithm, tie rules, adverse path, retention, minimum
activity, costs and readiness counts precisely enough to test on synthetic
paths. No future onset/peak/retention information may enter live features.

Separate **prediction before onset** from **early detection after onset** in
the results. A board detecting the first burst cannot claim it forecast the
move before any evidence appeared. Freeze how each is evaluated; do not
change the target after learning which version gives a better result.

## 3. Record the necessary data

After the audit gate passes, implement the sparse 5s recorder with trade
fields from `matches` and observed BBO from `ticker`. Preserve source/age,
receipt/event timing, coverage, gaps and price-fallback flags. Freeze its
storage budget and archive policy before full study collection.

Retain the contemporaneous eligible universe, including coins before board
entry and coins that never trigger. Entry-only history cannot measure all
missed moves or establish whether a precursor appeared before selection.
Keep one application worker/feed pipeline; use a reviewed runtime handoff
when connecting the recorder to the existing always-on collector.

## 4. Test Gemini's feature hypotheses, then their combination

Use the existing small F1-F5 set: acceleration, signed participation,
observed book/spread pressure, compression/expansion and market-relative
movement. Their predictive value is unproven. Predeclare feature checks and
limited ablations on discovery data before combining them into a score.

- Evidence arising only after onset may support confirmation, not anticipation.
- Evidence with no useful separation from ordinary activity does not support
  that precursor hypothesis.
- Useful individual evidence that disappears in the combined score calls
  for investigating combination/calibration on discovery only.
- Effects that disappear with valid quotes, coverage or friction require
  measurement/liquidity investigation; changing weights cannot supply
  missing observations.

Keep score, direction, stage and reliability separate. Fit the instant
candidate against its early-warning task; fit the developing-move read
against its declared continuation/failure task. Do not copy the broader
outlook formula or its weights into either board.

## 5. Evaluate in shadow before a visible ranking change

Collect at least 14 valid days, with the fixed 30s/180s window pair and the
declared discovery/validation split. This is a minimum pilot, not a promise
of sufficient independent events or regimes. Extend collection when
readiness is inadequate; preserve fresh validation after model freeze.

Compare against percentage movers and current live strength at matched
timestamps/universes. Primary operational questions are earlier detection
at a declared false-alert burden, detection delay, movement already consumed,
missed impulses, retention and adverse movement. Endpoint returns and cost
scenarios remain useful supporting checks. Use paired time/episode-aware
uncertainty and report coverage, rather than treating all rows as independent.

The next concrete deliverables are the new audit report and executable
prospective target contract. A successful data audit alone does not establish
an early-warning edge or approve a UI release.
