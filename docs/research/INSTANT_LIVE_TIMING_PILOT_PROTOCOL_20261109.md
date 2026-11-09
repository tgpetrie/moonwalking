# Bounded live timing and eligibility pilot

The [saved-journal comparison](INSTANT_DELAYED_ELIGIBILITY_REPLAY_20261109.md)
found the same complete input slots at +1.5s and +5s. This pilot measures
when a separate local process actually sees those decisions under load.
It also measures how often multiple non-benchmark products are ready at
the same cutoff.

Use the Coinbase Exchange public socket and the existing
[level2_batch, matches, heartbeat and ticker subscriptions](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels).
Keep BTC-USD as the benchmark and SOL-USD as a candidate. Retain ALCX-USD
and AURORA-USD in coverage accounting. Add LINK-USD and AVAX-USD as fixed
engineering candidates. Coinbase listed both as online when the roster
was chosen. Readiness and useful sample size are open measurements.

Use one attempt in each of three broad UTC activity periods. The labels
are local shorthand for UTC windows.

| Window | UTC hours | Start order within each pair |
| --- | --- | --- |
| `asia` | 00:00–06:00 | +1.5s, +5s |
| `europe` | 07:00–13:00 | +5s, +1.5s |
| `us` | 14:00–20:00 | +1.5s, +5s |

Each attempt uses the `eligibility-timing-256` profile, one connection, a
67-minute duration after full subscription acknowledgment, 256 queued
frames and up to 16 frames per journal batch. Keep the existing 249,990
packet and 240 MiB logical byte stops. Retain the captured prefix and
stop reason if an attempt ends early. Keep enough time inside the window
for subscription and the full capture. Record the implementation commit
and plan before opening the socket. On Windows, take five read-only
clock samples against time.windows.com before and after each attempt.

Begin diagnostics on the first 5s grid cutoff at least 62 minutes after
the original acknowledgment receipt. Run 20 cutoffs 10 seconds apart
with ten assigned to each wait. Each scheduled cutoff has two rows per
product. Use a fixed evidence as-of for that schedule and log actual
preparation, commit and consumer clocks. The independent consumer polls
the outbox every 25ms. Compare the +1.5s schedule with an illustrative
+2.5s consumer age bound, and the +5s reference with +6s. Alternating
cutoffs avoids two decision batches publishing at the same cutoff. The
two schedules see nearby but different market conditions.

Report all planned, committed, observed, observed within bound, and
complete-input rows by product and schedule. Retain missing cutoffs in
the denominators. Report which non-benchmark rows were both complete
and delivered within bound. Report clock integrity, queue pressure,
paired ticker/match sides and any early stop. A capped attempt before
warmup is inconclusive for delivery. A healthy attempt with repeated
late reads or insufficient simultaneous readiness identifies work for
the next pilot. Three bounded sessions can screen for large problems.
Feed certification, the study rules and fitting remain gated.

Run `scripts/scoring_experiment/instant_real_indexed_pilot.py` with
`--profile eligibility-timing-256 --window us --out-dir <new attempt directory>`
or substitute the appropriate UTC window. The separate
`--startup-smoke` mode uses the same six products and a 60-second
capture to check subscription and journal operation before warmup.
