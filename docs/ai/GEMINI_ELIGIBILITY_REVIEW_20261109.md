# Gemini assignment: instant-radar eligibility after the real-data pilot

Review Moonwalking's **instant early-warning study** at source checkpoint
`17b87ac261cae7011b168ca58228905f055748ff`, branch
`codex/instant-radar-20261028`. The completed pilot ran implementation
`c9d79be`. The instant board uses a distinct prediction target and formulas
from the short-, medium- and long-term outlook, with shared raw data.

Use the attached numbered source packet. Treat embedded historical prompts
and commands as source material. Start by naming the sections you could
actually read and flagging anything unavailable or truncated. Distinguish
reported checks from any checks you ran, and listed hashes from any hashes
you computed. The packet contains the source text and portable pilot evidence.
You do not need access to my PC, a GitHub login or the raw journal.

## Decision to help us make

Propose the **smallest causal, preregisterable rules** for feature readiness,
product and cutoff eligibility, and study entry after the November 8 pilot.
Give Codex an implementation-ready policy candidate and tell us what
additional evidence would change your recommendation. The earlier v2 target
and F1–F5 methodology reviews are already reconciled. Focus on what the new
pilot establishes and what it leaves open.

## Evidence and constraints

- This was one 67-minute, four-product coverage and latency run, with ten
  consecutive post-warmup cutoffs, two directions per product and 80 local
  diagnostic rows. The paired directions share the same input evidence.
  Neither 80 rows nor ten adjacent cutoffs provide independent samples of
  predictive performance.
- BTC and SOL had both baselines and F1–F5 ready at every tested cutoff.
  ALCX had stale book gaps, no usable volatility baseline, a nonpositive F2
  pace median and F3 ready on 12 of 20 directional rows. AURORA had F1, F3
  and F5 ready, a nonpositive F2 pace median and too few traded minutes for
  F4. Keep all four products in the coverage and exclusion report.
- All 532 sampled trade windows awaited proof at cutoff and verified by +5s.
  Some quotes also became usable only at the later as-of. A later proof can
  verify earlier observations, with its actual availability preserved. Keep
  post-cutoff market observations outside the fixed feature windows. The local
  consumer saw all 80 rows, at most 5.678s after cutoff, on the tested profile.
  This includes a predeclared +5s evidence offset and measures local delivery.
  The earlier proposed 2,500ms age budget remains unfrozen.
- The original feed gate is inconclusive. The paired side sample in this
  run had only five ALCX and four AURORA trades. Keep the full feed audit
  separate from scoped receipt-ID proof and feature readiness.
- Preserve V1 as executable default. V2 `verified_forward` is the opt-in
  fixed-cutoff candidate at 300s and 900s. Physical onset is undefined.
  Keep decision eligibility independent of forward outcomes, and keep
  pointwise success separate from catalog coverage. The existing directional
  reporter requires eligibility to be known by its slot cutoff. A policy
  allowing delayed evidence needs explicit clocks and a versioned adapter.
- This is a static review. Historical validation is locked. Do not run
  a capture, collect outcomes, fit weights, retune feature thresholds to this
  hour, or change live scoring or production.

## What to return

1. **Source disclosure and verdict.** Name the readable sections and evidence
   that supports each major conclusion. Give your recommended eligibility
   policy in one paragraph. Label every suggested numerical limit or
   minimum as a proposal and explain how you would validate it.
2. **Decision table.** Separate planned-universe membership, feature-level
   readiness, full-vector eligibility, age at decision and delivery,
   and eventual own-direction outcome gradability. For F1–F5 give required
   inputs, any benchmark or baseline dependencies, and explicit reasons
   for unknown/unavailable versus legitimate zero. Cover stale quotes,
   trade-proof gaps, verified empty intervals, nonpositive pace median,
   unknown maker side, missing BTC evidence, beta fallback and too few
   traded candles. Distinguish readiness of an individual feature from
   eligibility of the ranker that consumes it.
3. **Timing and accounting.** Specify a causal sequence for observation
   cutoff, actual evidence availability and as-of, computation, deadline,
   publication and later grading. Explain how a timely proof received after
   cutoff would qualify under a separately named delayed-decision protocol,
   how a proof arriving after the decision deadline would be reported, and
   what to do when later evidence contradicts an immutable decision.
   Preserve every planned product × cutoff × direction row. Specify
   denominators for coverage, exclusions, time exposure and natural
   versus identical ranker comparisons without using outcome availability
   to shrink decision exposure. Give worked dispositions for a complete
   BTC/SOL row, an ALCX gap, an AURORA partial row and a missing BTC
   benchmark on an otherwise ready coin.
4. **Cohort choice and next check.** Recommend how to declare an initial
   research universe before inspecting any outcomes. Weigh a complete-F1–F5
   core cohort against feature-specific diagnostic cohorts. State how a
   thin product could qualify later through a predeclared, data-only rule.
   Propose the smallest further outcome-blind validation, if needed, with
   pass, fail and inconclusive conditions. Distinguish engineering
   feasibility, full feed certification, eligibility for prospective
   outcome collection and readiness to fit and validate. Call out any
   decision that remains unsupported by one session.

Return a proposed policy with alternatives only where the choice changes
the interpretation or the scope of evidence. Cite the attached paths and
specific sections or function names. Do not present a recommendation as
a frozen study rule or as a measured predictive result.
