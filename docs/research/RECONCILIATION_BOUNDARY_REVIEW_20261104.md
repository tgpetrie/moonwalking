# Reconciliation review: continuity boundary blocker

November 4, 2026. Proposed commit `bfab9c86394a9117951b8f4fb970da88a34a7e32`
was inspected read-only in local Claude's worktree. It has **not been merged**
into `codex/instant-radar-20261028`. Codex reproduced one blocking violation;
this is not a complete acceptance of the remaining implementation or its
reported 645 checks. The root branch's existing 521-check result is unchanged.

## Confirmed false pass

All events below use the same connection ID. Receipt sequence and monotonic
time are nondecreasing, with strictly increasing local sequence numbers.

| Receipt ms | Event |
|---:|---|
| 900 | Acknowledge ticker, matches, heartbeat for TEST-USD |
| 1000 | Heartbeat, last trade ID 10 |
| 2000 | Heartbeat, last trade ID 11: first interval fails, missing ID 11 |
| 2000 | `audit_parse_error`: continuity must reset |
| 2000 | New complete subscription acknowledgement |
| 2000 | New heartbeat baseline, last trade ID 11 |
| 2500 | Live match ID 11, price 100, size 1, maker side sell |
| 3000 | Heartbeat, last trade ID 11: second interval has an out-of-watermark ID |

Actual result on `bfab9c8`: a merged proof covers `[1000,3000)` and
`assess('TEST-USD',1000,3000,asof=3001)['receipt_id_check_passed']` is **True**.
Expected: the audit failure separates the two continuity epochs, so those
proofs must never merge, even with equal receipt milliseconds, the same
connection ID and touching watermarks. Individually valid intervals on either
side may still be used after recovery. Exact union ID equality alone does
not remove an explicit continuity failure.

The cause is `_reconcile` checking connection ID, touching receipt intervals
and watermarks without retaining an epoch or detecting the intervening failure
in receipt-sequence order. The same condition must be checked when `assess`
joins otherwise valid intervals. Actual recorder connection IDs remain a
separate upstream requirement; resubscription on one live connection can
legitimately retain its ID.

## Required follow-up on Claude's branch

Keep the bounded caps, original failed proofs, receipt-attributed trades and
actual reconciliation availability. Add continuity epochs or explicit lifecycle
barriers identified by receipt sequence. No merge or assessment chain may span
an audit/queue/transport failure or lost required subscription, even when all
events share a millisecond and recovery reuses a connection ID.

First add this counterexample against unmodified `bfab9c8`; also test transport
errors, queue loss and lost/readded subscription membership at a shared
timestamp. Test valid recovery on each side, healthy repeated acknowledgements,
ordinary races without a barrier, and known-at immutability. Run the relevant
new tests, original coverage/book tests, formatting and guardrails. Preserve
other agents' work and push the correction on Claude's own branch for Codex
verification. Do not change live services, targets, outcome studies or limits
to hide the failure. No new capture or model fit is required.

The next cloud assignment remains the independent book/publication review;
it should not duplicate this local reconciliation correction.
