# Startup book and burst verification results

The pre-acknowledgment book amendment activates a staged snapshot on
the first valid subscription response from the same explicitly opened
connection. It keeps the original observation age and requires a
post-acknowledgment heartbeat. Loss, connection change, invalid
book data, and missing membership discard the staged data as specified.

Two new tests reproduced the startup defect on the previous code.
The amended implementation passes both tests plus four rejection
controls. A 271-row replay of the preserved real startup prefix,
using original receipt order and a simulated processing clock,
activated the ALCX snapshot at acknowledgment sequence 3 and
produced a usable quote at the subsequent grid probe. This replay
verifies ordering behavior under the amended code.

## Burst results

Each condition was run three times with the real indexed SQLite writer.
The larger-queue trials delivered their 160-frame bursts in roughly
100–104 ms and drained the complete 205-frame synthetic source,
including startup and the tail. All 12 journals passed ordered-prefix
comparison, single-connection verification and SQLite quick check.

| Queue capacity | Injected writer pause | Outcome | Data frames committed per trial | Peak queue depth | Largest measured queue wait |
| --- | ---: | --- | ---: | ---: | ---: |
| 128 | 0 ms | 3 / 3 explicit overflows | 14 / 205 | 128 | 280 ms |
| 128 | 450 ms | 3 / 3 explicit overflows | 5 / 205 | 128 | 292 ms |
| 256 | 0 ms | 3 / 3 complete | 205 / 205 | 150 | 1,481 ms |
| 256 | 450 ms | 3 / 3 complete | 205 / 205 | 174 | 1,920 ms |

The larger queue absorbed this workload with the same per-frame
commit path, at the cost of up to about 1.9 seconds in the queue.
The shorter waits at the 128-frame cap describe only the committed
prefix. The experiment uses a declared synthetic arrival schedule
and does not establish the arrival pattern of the discarded live
frames or a safe decision-age budget.

Next, compare bounded transaction batching or another faster writer
against these same conditions, including crash recovery and known-at
availability, before selecting the next real capture profile.

The first synthetic harness attempt stopped during verification
because it compared Python tuples in the generator with JSON lists
on disk. The preserved journal matched after canonicalization.
The complete run used the same declared workload and compared
wire-format JSON. The original live journal and loss marker are
preserved independently.

- [Protocol and startup amendment](INSTANT_STARTUP_AND_BURST_PROTOCOL_20261108.md)
- [Burst run](results/instant_startup_and_burst_20261108/RUN_02.json)
- [Verification](results/instant_startup_and_burst_20261108/CHECKS.json)
