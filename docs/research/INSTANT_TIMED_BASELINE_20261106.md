# Timed volatility and activity baseline draft

The offline `build_timed_baseline(recorder, product, cutoff, asof=...)` API
takes a declared product and 5-second feature cutoff. It computes two
independent components from the timed input-evidence ledger.

- **Volatility and BTC beta.** Use 61 fresh, paired minute-close midpoints
  to form 60 log returns. The final close is
  `floor((cutoff_ms - 35000) / 60000) * 60000`. Use the coin's sample
  standard deviation and centered OLS against BTC. A flat BTC return series
  gives beta 1 with an explicit fallback flag. The trade receipt proof covers
  the preceding 5-second bucket at the first close through the final close.
- **Activity pace.** Use 120 half-open 30-second receipt windows ending at
  `cutoff_ms - 30000`. Median trade count and quote USD amount use first
  receipts. One proof chain within a single continuity epoch covers the
  full hour. A proved empty bin contributes zero to both medians. When a
  proof is missing, the component is unavailable. Maker side is irrelevant
  for these unsigned medians.

A missing benchmark close can block volatility while pace is ready. Each
ready component records the latest availability of the quote or trade
evidence it used, including the producer's payload completion. The
evidence as-of can precede the feature cutoff once a component's window
has closed. The plan must already be recorded by that as-of, and the as-of
must have elapsed on the recorder clock. The builder reads the clock again
after calculation and provenance hashing to record computation completion.
A later calculation with the same evidence as-of can use the same evidence
while having a later completion timestamp.

The result pins the inventory hash and its recorded time, the packet count
and SHA-256 of the known canonical packet prefix, and normalized source
and contract hashes. The draft is for offline component calculation.
Positive eligibility still requires feature, quote-health and publication
evidence. Throughput and availability on a real capture remain to be
measured.

The five new synthetic cases cover delayed proof completion, stable
prefix provenance, BTC quote missingness, verified empty versus unknown
activity, a trade exactly at the exclusive right boundary, and the
inventory and processing clocks. See the
[check record](results/instant_timed_baseline_20261106/CHECKS.json).

Next, define F3's book observation integration and F4's candle source and
alignment, then build cutoff-bound F1–F5 feature evidence. The data-only
pilot will measure coverage and latency after the remaining interfaces and
pilot rules are in place.
