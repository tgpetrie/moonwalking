# Warmup capacity acceptance and thin-product findings

The opt-in profile completed 67 simulated minutes on a single connection.
The real SQLite writer committed **241,208 rows** in **37 minutes 36.354
seconds** of host capture time. The run stopped at its declared duration.
It used 167,305,605 logical record bytes and a 205,647,872-byte SQLite
file. The journal hash, every packet digest, sequence, single connection
identity and SQLite quick check passed.

Both volatility and activity baselines were ready for all four products
at the 62-minute cutoff. BTC and SOL produced all five features. The
synthetic ALCX and AURORA activity medians were zero, and AURORA had too
few traded candles for F4. The fixture supplied frequent book updates
to exercise recorder and baseline capacity. Thin-product availability in
real conditions is measured separately below.

| Product | Book callback through commit p95 | One post-capture feature calculation |
| --- | ---: | ---: |
| BTC | 14.968 ms | 4.056 s |
| SOL | 10.342 ms | 6.181 s |
| ALCX | 8.929 ms | 4.723 s |
| AURORA | 8.875 ms | 5.642 s |

The callback timing uses QueryPerformanceCounter with a reported
100 ns resolution on this host. The largest observed book callback
was 740 ms. The synthetic run uses an accelerated receipt clock and
regular synthetic traffic. The per-product feature measurements are
individual post-capture computations. A follow-up needs incremental
baseline and window calculations, benchmarked with the recorder
running, before evaluating a decision age budget.

## Thin-product quote evidence

The preserved real journal has 68 probes for each product. For the ticker
comparison, use the original receipt of each ticker carrying a positive
bid, ask and sizes with bid below ask. At each cutoff inspect the most
recent receipt strictly before the cutoff. For the full-window check,
include the carry-in receipt and require the interval between each
observation and the next boundary to be no more than 10 seconds. These
ticker counts ignore processing delay and health checks, giving an
optimistic source-only comparison.

| Product | Verified book endpoints | Verified full book windows | Fresh ticker endpoints | Fresh full ticker windows |
| --- | ---: | ---: | ---: | ---: |
| ALCX | 43 / 68 | 14 / 68 | 3 / 68 | 0 / 68 |
| AURORA | 66 / 68 | 61 / 68 | 1 / 68 | 0 / 68 |

The longest ALCX book receipt gap was 135.069 seconds. Its longest
ticker gap was 259.344 seconds. AURORA's longest book and ticker gaps
were 20.682 and 317.222 seconds. Keep stale book spans unavailable in
the draft and retain those slots in the coverage denominator. The
observed ticker stream offers little fresh endpoint coverage and no
complete 30-second windows under this age rule.

The read-only Windows clock probe ran after the preserved capture and
reported five offsets from +331 to +512 ms against its time source.
The Windows Time service status query returned service stopped. The
probe documents the host state at the later check. Treat the original
exchange-to-callback values as signed differences between clocks.
A follow-up needs a contemporaneous clock-offset check.

The raw synthetic journal is on the Windows research host under
`%USERPROFILE%\.moonwalking\analysis\instant_warmup_capacity_20261107\run-01`.
The original source pilot remains the real feed evidence.

- [Declared capacity workload](INSTANT_WARMUP_CAPACITY_20261107.md)
- [Capacity run](results/instant_warmup_capacity_20261107/RUN_01.json)
- [Thin quote and clock diagnostic](results/instant_warmup_capacity_20261107/THIN_QUOTES_AND_CLOCK.json)
- [Verification](results/instant_warmup_capacity_20261107/CHECKS.json)
