# Batched real-source coverage and latency results

The November 8 attempt at `c9d79be` reached its 67-minute deadline on one
Coinbase Exchange connection. All four products acknowledged at 3:13:17
a.m. Pacific. The last committed reader receipt came 4,019.996 seconds
after acknowledgment. The journal contains **166,035 committed records**,
including the open and close markers. The reader returned 166,035 data
frames, of which the writer committed 166,033. The two remaining frames
are outside the measured prefix at the scheduled stop. The sampled
queue high-water was **97 of 256**, with zero reported overflow and zero
pending ingress records.

The four snapshots arrived after acknowledgment in this attempt. ALCX
received its initial book at sequence 3, 89 ms after acknowledgment.
The pre-acknowledgment path remains verified by the earlier preserved
replay. ALCX quote staleness still limits its usable evidence.

## Coverage

There were 133 probes per product. The table reports the cutoff and
the declared later knowledge time separately.

| Product | Quote at cutoff | Quote by +5s | Full fresh 30s book window by +5s | Trade window by +5s |
| --- | ---: | ---: | ---: | ---: |
| BTC | 130 / 133 | 133 / 133 | 133 / 133 | 133 / 133 |
| SOL | 133 / 133 | 133 / 133 | 133 / 133 | 133 / 133 |
| ALCX | 109 / 133 | 109 / 133 | 47 / 133 | 133 / 133 |
| AURORA | 133 / 133 | 133 / 133 | 132 / 133 | 133 / 133 |

At the cutoff, all 532 trade windows were still awaiting proof. At +5s
they all verified. Ready proof lag p95 ranged from 929 to 936 ms across
products. ALCX's 86 missing full book windows were stale, and AURORA
had one stale span. The side diagnostic paired 11,175 BTC trades,
2,354 SOL trades, five ALCX trades and four AURORA trades. Every paired
ticker and match side was opposite. The thin counts leave the separate
feed-audit gate inconclusive.

## Readiness and local latency

All ten cohorts reached their planned post-warmup cutoffs. Each
product contributed 20 rows across the two directions. BTC and SOL
had both baselines and all five features ready on every row. ALCX
lacked a usable volatility baseline on every row due to stale book
observations. Its F2 was unavailable throughout because its pace
median was nonpositive, and its F3 was ready on 12 of 20 rows.
AURORA had both baselines and F1, F3 and F5 on all 20 rows. Its F2 was
unavailable throughout because its pace median was nonpositive.
Its F4 lacked enough traded candles on all 20 rows.

| Measurement | p95 | Maximum |
| --- | ---: | ---: |
| Decision preparation, 80 rows | 70.2 ms | 107.1 ms |
| Local outbox commit, 80 rows | 20.2 ms | 26.5 ms |
| Complete eight-row cohort, 10 cohorts | 655.2 ms | 655.2 ms |
| Commit observation to separate local reader, 80 rows | 27 ms | 60 ms |
| Cutoff to separate local reader, 80 rows | 5.601 s | 5.678 s |

The separate reader saw all 80 committed diagnostic rows, with zero
missing or mismatched observations. Cutoff-to-read includes the
predeclared 5s evidence offset. The largest reader-to-writer wait
across recorded frame groups was 686 ms. The largest reader-to-audit
commit time was 763 ms. These timings measure a single run on this
host and delivery to a separate local process.

The startup clock check recorded +1.143 to +1.159 seconds, and the
post-capture check recorded +1.285 to +1.346 seconds. Exchange-stamp
differences retain their signed wall-clock values. Queue and commit
durations use the host performance counter.

The journal hash, SQLite quick check, 166,035 packet records, 166,033
batch processing clocks and all 80 outbox digests and cutoff prefixes
verified. The raw journal stays on the Windows research host. The
portable report, plan, local observations and clock checks are below.
**1,316 targeted checks** passed, with Black, guardrails and 11 frozen
historical hashes verified.

The next decision is to predeclare which combinations of quote freshness,
baseline readiness and trade activity qualify a product for each
feature and for the full study. Keep the thin products in coverage
reporting. This run supplies feasibility evidence for that decision.
The feed audit, decision-age policy and prospective study freeze
remain open before fitting.

- [Protocol](INSTANT_BATCHED_SOURCE_PILOT_PROTOCOL_20261108.md)
- [Plan](results/instant_batched_source_pilot_20261108/PLAN.json)
- [Attempt report](results/instant_batched_source_pilot_20261108/ATTEMPT_01.json)
- [Local consumer observations](results/instant_batched_source_pilot_20261108/OBSERVED.jsonl)
- [Startup clock check](results/instant_batched_source_pilot_20261108/CLOCK_BEFORE.txt)
- [Ending clock check](results/instant_batched_source_pilot_20261108/CLOCK_AFTER.txt)
- [Verification](results/instant_batched_source_pilot_20261108/CHECKS.json)
