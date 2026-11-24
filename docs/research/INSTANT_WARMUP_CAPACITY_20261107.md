# Instant-radar warmup capacity and timing draft

The November 7 source pilot measured about 48 packets per second and
stopped at 99,991 rows. A 67-minute diagnostic at that observed rate would
require approximately 194,000 records. This draft adds an explicit
250,000-packet profile through the journal, input ledger, book and trade
monitor. The ordinary cap remains 100,000. The opt-in profile retains the
1 MiB frame and 256 MiB logical record limits and stops at 249,990 packets
or 240 MiB to leave room for the final marker. The earlier source-pilot
reports stay pinned to their original code and bounds.

## Synthetic acceptance run

Drive the real callback path and SQLite writer with one continuous synthetic
socket. Simulate 67 minutes at 60 frames per second, about 24% more than the
observed average, plus startup snapshots using the observed level counts.
The fixed mix is 42 book updates, four heartbeats and seven trade/ticker
pairs per simulated second. The generated prices, sizes, update order and
watermarks are synthetic. The underlying SQL writer keeps its normal
transaction and synchronization settings. No network socket is needed.

Require a duration stop, one connection, and ready volatility and pace
components at the first 62-minute cutoff. Report packet/byte totals, actual
host runtime, callback duration by frame type, and baseline/feature
readiness. Thin synthetic products may have insufficient current trade
participation even with complete baseline evidence. This test measures
recorder capacity under the declared workload. It does not certify live
throughput under bursty market traffic.

Run the synthetic workload from the research checkout with
`python scripts/scoring_experiment/instant_warmup_capacity.py --out-dir <new-directory>`.
A future data-only pilot must separately predeclare when to use the
`--warmup-capacity` profile, source checks and timing comparisons.

## Timing and thin-product evidence

Measure local callback durations with `perf_counter_ns`. Receipt and
processing availability retain their separate clocks. Signed
exchange-stamp-to-callback values are recorded separately and are not
transit estimates. Check the host clock against an independent time source
near any follow-up capture before interpreting cross-clock differences.

Keep the current 10-second book observation age and full 30-second span
requirement for F3 in this draft. Preserve the product and its missingness
reason in planned probes. Assess whether ticker would supply observations
through the same intervals using the saved pilot journal before considering
a replacement source. A shorter set of products, a looser quote age, or a
changed feature requires an explicit policy amendment.
