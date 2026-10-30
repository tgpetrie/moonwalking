# Preserved feed replay: counts verified, data readiness still blocked

On October 30, Codex replayed the single completed October 28 capture already
pinned in the GitHub handoff. No new connection, capture, return-label study,
scoring-model fit or live change ran. This is data-pipeline verification,
not a rerun of the locked historical scoring comparison.

The recorded run used adapter **`837db34`**. A follow-up actual-receipt-span
guard is at **`a5bb397`**; the preserved raw span of 3,600,154ms independently
satisfies that guard. The saved run report retains its original adapter hash;
no alternative capture was selected and the counts were not recomputed to
change a verdict. Recorder: `ab95159`. Target evaluator
and both target JSON files remain unchanged at `92fb51d`.

## What ran and passed

- Six source files matched the committed transfer manifest before/after.
- All **63,258 packets** were replayed, including **24,424 unique live matches**.
  All four products' counts equal the original audit. USD volumes and per-bucket
  maker-to-taker amounts agree with independent Decimal calculations within
  **$0.000001**; exact raw totals are in the report.
- **248,000 saved REST rows** were read for reconciliation, including repeated
  pages; they are not additional unique live trades or recovery-time volume.
- Required ticker/matches/heartbeat product memberships were acknowledged on
  one connection. Only aligned interior receipt buckets, with reconciled ID
  ranges and <=5s heartbeat gaps, receive retrospective coverage assertions.
  Out-of-watermark buckets are excluded. Quote ages remain separate checks.
- Source totals include startup/tail observations outside the audit's first/
  last heartbeat-ID watermarks. Those observations are preserved; the total
  match count is not a claim that every boundary trade is REST-certified.
- The sparse store has **1,385 occupied bucket keys** and **29,020,160 bytes**.
  This one-hour/four-product artifact does not set a production throughput,
  retention budget or a 407-product daily storage estimate.

The [full replay report](results/instant_capture_replay_20261030/REPLAY_REPORT.json)
and [artifact manifest](results/instant_capture_replay_20261030/ARTIFACT_MANIFEST.json)
are committed. The [verification record](results/instant_capture_replay_20261030/CHECKS.json)
records code, checks and backup receipt.

## What the real data revealed

These are endpoint midpoint checks at 719 interior 5s cutoffs per product,
**after retrospective coverage verification**. They do not establish a
continuous 30s fresh-book interval or F3 eligibility.

| Product | Unique live matches | Fresh sampled midpoint /719 | Verified zero-trade buckets |
|---|---:|---:|---:|
| BTC-USD | 21,776 | 719 | 1 |
| SOL-USD | 2,641 | 709 | 63 |
| ALCX-USD | 4 | 6 | 716 |
| AURORA-USD | 3 | 4 | 717 |

SOL has ten stale-quote endpoints. Thin products mostly fail the unchanged
10s quote-age rule: ALCX has 712 stale endpoints and AURORA 714; each also has
one initial quote crossing the unverified boundary. A known zero-trade bucket
does not create a new quote or fresh observed OHLC. Do not carry a stale price
forward as a new observation to fill this gap.

The original gate remains **false**: ALCX/AURORA's 4/3 paired trades still do
not satisfy the original side-evidence requirement. Longer capture alone is
not a declared solution to sparse quote updates. Any new quote source or
restricted universe must be versioned and specified before new study data;
this run does not change either policy.

### Contemporaneous versus retrospective knowledge

The capture has packet timestamps and a later REST-reconciled audit, not a
persisted contemporaneous coverage verdict for every decision cutoff.
The adapter stamps its evidence with the actual current verification time.
All **2,876 original-cutoff queries** therefore correctly remain unverified;
explicit later-as-of queries can inspect the reconciled receipt buckets.
Repeated original-as-of queries remain identical after the later query.

This does not mean every recorded quote was unavailable at the time. It means
the required then-known complete-coverage claim cannot be reconstructed from
later audit evidence. The retrospective assertions establish the stated
receipt/ID checks, not unobserved book updates or production queue behavior.
They must not be used to manufacture earlier live features.

### Baseline warmup

All four baseline requests at the last captured cutoff return
`unavailable/baseline_coverage`. In addition to the missing contemporaneous
verdicts, the required sigma history begins before this capture starts.
The one-hour audit was designed for feed checks, not full feature warmup.

For this builder, the oldest required coverage point lies 60m40s to 61m35s
before a 5s-grid decision, depending on its minute alignment. Plan **at least
62 minutes of complete warmup** before counting valid study observations;
clock time alone is insufficient if coverage/quote requirements fail. Retain
final label maturity separately. Do not import later candles as if they had
been observed before the original decisions.

## Reproduce or restore elsewhere

Restore the original source bundle using
[`INSTANT_EVIDENCE_MANIFEST_20261029.json`](../ai/INSTANT_EVIDENCE_MANIFEST_20261029.json)
and the existing resume instructions. Use a new absent output directory:

```sh
python scripts/scoring_experiment/verify_preserved_feed_replay.py --capture ~/.moonwalking/analysis/feed_audit_campaign_20261028/attempt-01 --manifest docs/ai/INSTANT_EVIDENCE_MANIFEST_20261029.json --capture-key feed_audit_campaign_20261028/attempt-01 --out-dir ~/.moonwalking/analysis/capture-replay-new
```

The adapter refuses altered source files, source errors, unsupported connection/
subscription changes, capture bounds above 3,605 seconds, >100,000 packets or
>1,000,000 saved REST trade rows. It never truncates a larger file and declares
that prefix complete. This is a bounded adapter for this profile, not a
certified general live monitor. Failures stay in the new output directory.
Reruns use their own real verification time, so derived database byte hashes
can differ while the captured source hashes/counts remain the same.

The exact run-01 derived database, health assertions and report are also on the
existing authenticated **draft** GitHub release. See the
[transfer manifest](../ai/CAPTURE_REPLAY_EVIDENCE_MANIFEST_20261030.json) and
[verified transfer receipt](../ai/CAPTURE_REPLAY_GITHUB_TRANSFER_20261030.json).

```sh
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --pattern moonwalking-capture-replay-20261030.tar.gz --dir handoff-downloads
python scripts/restore_macbook_evidence.py handoff-downloads/moonwalking-capture-replay-20261030.tar.gz --manifest docs/ai/CAPTURE_REPLAY_EVIDENCE_MANIFEST_20261030.json --destination ~/.moonwalking/analysis
```

Native Mac/cloud execution remains unverified. The downloaded archive was
restored into a fresh Windows folder and checked against every member hash.

## Next concrete step

Define and implement contemporaneous per-product subscription/receipt-health
and reconciliation-availability records, and paired immutable sample adapters.
Set a quote-source/freshness policy that honestly addresses thin-product
staleness; preserve the current gate while reviewing any explicit amendment.
Predeclare warmup and any bounded supplemental diagnostic before starting it.
Then verify actual eligible rows before the >=14-valid-day shadow study.
F1-F5 implementation/stages/model/readiness freeze and fresh validation remain
required. No extra general Claude/Gemini review is queued for this completed
replay, and no new collection or fitting was launched by it.

**363 targeted checks pass**, including seven new adapter cases. Formatting,
repository guardrails, source/target compatibility and all 11 historical
contract artifact hashes pass. No full-suite, predictive-power or live-readiness
claim follows from these results.
