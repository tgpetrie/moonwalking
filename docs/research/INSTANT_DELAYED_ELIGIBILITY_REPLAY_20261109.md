# Delayed eligibility and preserved-journal timing comparison

November 9, 2026 (Pacific). This research draft follows the
[eligibility review](INSTANT_ELIGIBILITY_REVIEW_TRIAGE_20261109.md).
It separates evidence readiness from local delivery. The existing directional
reporter and target evaluators retain their original clock and outcome rules.

`instant_delayed_eligibility.assess_cohort` accounts for every declared
product and direction at a cutoff. An absent decision is an explicit
`decision_missing` row. A complete-vector candidate needs all five features,
both baselines and fresh coin/BTC anchor evidence. BTC can have complete
inputs and stays in coverage as the benchmark, outside the non-benchmark
candidate count. The adapter checks the frozen decision's evidence prefix.
It retains component reasons and, when supplied, an observation linked to
that decision's digest with separate local commit and consumer ages.
Being ready and being observed within a diagnostic bound are separate
fields. The caller supplies the planned cutoff after warmup. These are
scoped research observations and do not certify full-feed or study eligibility.

The comparison uses the same ten post-warmup 5s cutoffs, all four products,
and both directions from the November 8 attempt. It uses a scratch copy
of the preserved journal, checks its full digest, reconstructs verified
packets and first-receipt trades, and evaluates fixed knowledge views at
cutoff plus **0, 1.5, 2.5 and 5 seconds**. Market content still stops before
the original cutoff. The journal records full packet start and finish
times. It does not separately record intermediate monitor and book clocks,
so this replay treats both intermediate stages as available at packet
completion. The report flags an as-of inside the next packet's processing.
Replay has no historical delivery timestamps. The original +5s outbox and
independent consumer observations are checked and reported separately.

The second supplied rendering of the Gemini response lists the full 15
hashes, lengths and paths, all matched to the same packet. Its detailed
protocol proposes three bounded 67-minute sessions instead of continuous
collection. Its summary still mentions 24 hours. Treat the bounded sessions
as a follow-up design candidate. Three short attempts can expose timing,
storage and coverage problems across activity periods. They cannot
establish a p99.9 tail or certify the original feed gate. The received
text digest is `4bcde71ae941179a15bdb09114543fd5f57a0d99c11349df3f3c7af8aa3909cd`.
The earlier archived review and its corrections still apply.

## Results

Replay verified all **166,035 packets** and their recorded first-receipt
trade evidence. The +5s replay matched the status, reason and value of
every F1–F5 component in all **80 original outbox decisions**. All 80
consumer records linked to the original decision digest and commit clock.

| Evidence as-of | BTC full inputs | SOL full inputs | ALCX full inputs | AURORA full inputs | Non-benchmark candidate rows | In-flight as-ofs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| +0ms | 0/20 | 0/20 | 0/20 | 0/20 | 0 | 2/10 |
| +1,500ms | 20/20 | 20/20 | 0/20 | 0/20 | 20 | 2/10 |
| +2,500ms | 20/20 | 20/20 | 0/20 | 0/20 | 20 | 2/10 |
| +5,000ms | 20/20 | 20/20 | 0/20 | 0/20 | 20 | 2/10 |

The +1.5s view preserved the same complete decision-input slots as +5s. The candidate count covers both
directions over ten adjacent cutoffs. It measures availability, not
independent events or ranking quality. The original +5s run observed
a maximum local commit age of **5,662ms** and a maximum consumer age
of **5,678ms**. All 80 original reads were within the illustrative 6s
bound. The other views have no measured delivery ages.

The next step is to predeclare bounded outcome-blind source checks across
activity periods. Test the shorter wait with actual local commit and
consumer clocks and retain the +5s schedule as a reference. Declare a
wider non-benchmark candidate set, as this run still has only SOL with
complete inputs. Keep all monitored products in the denominators.
The feed gate, study freeze and fitting remain closed.

Implementation commit `4b19a7a171c4f1923b85e46f4e33450a263bd51a`. **109 focused tests**, Black 24.8.0
and repository guardrails passed. See the [complete per-slot replay report](results/instant_delayed_eligibility_20261109/REPLAY.json) for counts,
component reasons, source digest and evidence-prefix hashes.
