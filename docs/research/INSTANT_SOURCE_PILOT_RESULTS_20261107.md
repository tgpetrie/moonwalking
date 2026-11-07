# Instant-radar source and latency pilot results

The corrected four-product capture ran on November 7, 2026 from 10:49:20
to 11:23:49 Pacific, measured from the full subscription acknowledgment.
It stopped at the declared packet budget after **34 minutes 28.392 seconds**.
The 99,991 committed rows include the final closing marker. The SQLite
journal occupies 90,972,160 bytes. It used one connection. The 62-minute
warmup check was never reached.

| Product | Paired ticker and match IDs with opposite sides | Fresh cutoff quotes | Full fresh 30s book windows | Trade windows verified at cutoff | Trade windows verified by cutoff +5s | p95 proof lag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC-USD | 10,045 / 10,045 | 67 / 68 | 68 / 68 | 0 / 68 | 68 / 68 | 876 ms |
| SOL-USD | 1,478 / 1,478 | 68 / 68 | 68 / 68 | 0 / 68 | 68 / 68 | 884 ms |
| ALCX-USD | 26 / 26 | 43 / 68 | 14 / 68 | 0 / 68 | 68 / 68 | 867 ms |
| AURORA-USD | 18 / 18 | 66 / 68 | 61 / 68 | 0 / 68 | 68 / 68 | 859 ms |

Fresh cutoff quotes and full book windows use the knowledge available at
the cutoff. Full book-window counts were identical at cutoff +5s. BTC's
one incomplete cutoff quote was ready in the later view. Each product
had 2,068 strict verified heartbeat intervals. Later proof completion
ranged up to 1,060 ms after the cutoff across the sampled windows. The
5-second column is a diagnostic evidence view. It does not select a
publication limit. Feed certification still requires the separate audit
evidence, including independent coverage reconciliation.

The local callback-through-commit p95 was 16 ms for all four book-update
groups. The largest observed book-update callback was 390 ms. Python's
monotonic timer on this Windows host reports 15.625 ms resolution, so
those callback quantiles are coarse. For book updates the separate
wall-clock payload-completion-to-commit p95 was 9 ms. Most exchange
timestamps were ahead of the local receipt clock. Clock offset and
source timestamp semantics remain unresolved, so exchange-to-callback
differences cannot estimate network latency. External publication delay
was outside the local recorder measurement.

Book updates accounted for 68,566 committed rows, about 69% of the
capture. At this observed average rate, 62 minutes would require roughly
180,000 rows. That is an extrapolation from this session. The next
capacity check needs to preserve warmup and continuity on one connection,
and the next timing measurement needs a higher-resolution duration
clock and a documented clock-offset check. The thin-product book data
also needs an explicit availability policy. Delayed trade proof alone
would leave most ALCX book windows unavailable.

Attempt 01 stopped before the pilot clock started, after 20.875 seconds
and 1,032 committed rows. Coinbase acknowledged the book subscription as
`level2_50`, the documented legacy name. The corrected adapter accepts
the alias while preserving the received message. The same products,
limits and readout were used in attempt 02. [Coinbase channel reference](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels#level2-batch-channel)

Both raw SQLite files passed digest, packet-record hash, sequence and
SQLite quick checks. They are saved under
`%USERPROFILE%\.moonwalking\analysis\instant_source_pilot_20261107` on
the Windows research host. The aggregate reports retain the digests and
code commits.

- [Predeclared protocol](INSTANT_SOURCE_PILOT_PROTOCOL_20261107.md)
- [Attempt 01 aggregate](results/instant_source_pilot_20261107/ATTEMPT_01.json)
- [Attempt 02 aggregate](results/instant_source_pilot_20261107/ATTEMPT_02.json)
- [Verification](results/instant_source_pilot_20261107/CHECKS.json)
