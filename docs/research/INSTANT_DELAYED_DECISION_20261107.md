# Delayed decision evidence and later cutoff grading

The offline module `instant_delayed_decision.py` adds two draft record versions,
`instant-delayed-decision-v1-draft` and `instant-later-cutoff-grade-v1-draft`.

## Decision and publication clocks

`prepare_decision` builds a timed F1–F5 row for a declared slot. It freezes
canonical feature and paired anchor-quote bytes and measures preparation
completion after serialization. The snapshot retains the observation cutoff
`b`, evidence as-of, feature completion, and decision preparation completion.
All observations used in the feature values precede `b`. A later evidence
as-of can admit later proof of a pre-cutoff interval. Unavailable features
stay unavailable in that snapshot.

`observe_publication` associates the snapshot with a caller-supplied
publication identity and timestamp. It validates this chronology and
measures when the observation was recorded:

```text
b <= decision evidence as-of <= feature computation completed
  <= snapshot preparation completed <= observed publication <= observation recorded
```

The observation uses the feature computation completion as the time all
computed inputs could be available, while the feature row preserves the
individual evidence clocks. The supplied timestamp is an observation
assertion. Durable delivery and scoring are separate work. An optional
diagnostic age bound uses the existing publication helper. Study selection
of an age limit awaits measured source and processing latency.

## Later grading

`grade_publication` returns an independent diagnostic view at a later
as-of. It checks the decision's inventory, ledger prefix and source provenance,
and records the grading prefix and decision digest. The requested as-of
must have elapsed and include the publication observation. It returns
`pending` through the period before `b+H`, with `H` equal to 300 or 900
seconds. Once mature, absent or contradicted evidence returns
`unavailable` with a null outcome. A mature grade with adequate evidence
returns a Boolean `cutoff_verified_forward`.

For this draft the published snapshot needs all five features available.
Grading rechecks the frozen inputs' trade proof windows and both products'
receipt-ID coverage from the 5s bucket preceding the anchor through
the horizon. Later conflicts in these windows can invalidate a grade.
As-ofs that fall during a packet's processing are unavailable once the
horizon is mature. This conservative boundary keeps a monitor result
from reaching grading before the recorder finishes the packet. The
original snapshot and earlier evidence views remain independently
reproducible.

The outcome uses paired, fresh receipt-time midpoints at each 5s endpoint,
the frozen anchor and volatility/beta, and first-receipt matches strictly
inside `(b,b+H)`. The terminal residual, spread and sigma threshold, peak
retention and forward match floor follow the pinned V2 impulse rules.
A contradiction in the anchor quote vetoes grading. A different outcome
as-of can change the grade's evidence without substituting new decision
inputs. Publication time is reported separately from the fixed cutoff
horizon. The grade includes whether publication preceded the horizon end.

This draft measures a fixed-cutoff outcome on scoped evidence. A later
publication-anchored quote benchmark needs its own entry and maturity
rules. The recorder and publication path still need durable clock and
connection evidence before a data-only coverage and latency pilot.

See the [check record](results/instant_delayed_decision_20261107/CHECKS.json).
