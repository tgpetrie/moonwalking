# Bounded journal batching results

The bounded writer at `aa953b5` took up to 16 already queued frames at a
time. Both profiles used the same indexed writer fixture and SQLite durability
settings. All 24 journals matched the exact ordered source prefix and passed
SQLite quick check and file-digest verification.

| Queue | Injected pause | Single-frame completions | Batched completions | Worst single receipt through commit | Worst batched receipt through commit |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 128 | 0 ms | 0 / 3 | 1 / 3 | 296 ms | 360 ms |
| 128 | 450 ms | 0 / 3 | 0 / 3 | 337 ms | 322 ms |
| 256 | 0 ms | 3 / 3 | 3 / 3 | 1,540 ms | 396 ms |
| 256 | 450 ms | 3 / 3 | 3 / 3 | 1,988 ms | 857 ms |

Complete runs committed all 205 source frames. In the 128-frame no-pause
case the single writer committed 14 frames in each trial. The batched writer
committed 22, 22 and 205. In the 128-frame pause case each writer committed
the five startup frames. Latency in overflow trials only covers committed
frames. In the complete 256-frame trials, batched worst queue wait was
367 ms without the pause and 829 ms with it. A single batch callback took
as long as 301 ms through the audit commit. The two durable transactions
can add overhead when few frames are waiting.

At a cutoff before ingress commit observation, the indexed evidence
prefix stayed identical to the pre-batch prefix. All three hard exits
recovered the expected prefix. An exit in the audit transaction left two
durable input envelopes and zero processed audit rows from that batch.
An exit during ingress left neither. An exit after audit commit left the
full processed batch. A processing failure preserved the staged inputs
and blocked decision preparation. A malformed frame wrote its barrier
before the connection ended.

**Candidate for the next diagnostic** is a 256-frame reader queue with
up to 16 frames per batch. Predeclare the follow-up at that profile and
measure warmup, quote missingness, frame loss and decision latency on real
data. The stress test establishes neither real coverage nor a decision-age
budget. The real runner still uses its original 128-frame queue and
single-frame writer by default. The stopped capture, feed gate and
historical results retain their prior status.

**1,313 targeted checks passed** on Windows with Python 3.12.10 and SQLite
3.49.1. Black, guardrails and the 11 frozen historical hashes passed.

- [Protocol](INSTANT_BATCHED_JOURNAL_PROTOCOL_20261108.md)
- [Single-frame run](results/instant_batched_journal_20261108/SINGLE.json)
- [Batched run](results/instant_batched_journal_20261108/BATCHED.json)
- [Checks](results/instant_batched_journal_20261108/CHECKS.json)
