# Resume Moonwalking from anywhere

## Board continuation research · November 13

The [fresh replication](https://github.com/tgpetrie/moonwalking/blob/7bd275748e1b9ee5758835337843a2dc1fe2a64e/docs/research/LIVE_MOVERS_FRESH_REPLICATION_RESULTS_20261113.md)
supports an overextension warning on board entries. A separate
[exploratory runner screen](../research/RADAR_BOARD_RUNNER_SCREEN_20261113.md)
on the same dates finds enrichment in both tails. Raw percentage move and
nominal 1m acceleration flag more adverse excursions than favorable ones.
The follow-up also tested Carbon's sustained runner and its mirror. Every
tested flag had a higher sustained reversal rate, so none advanced to a
directional freeze. Percentage move remains the reference. A causal
flag budget and fresh confirmation design remain open.

Claude's local Step 1 result `6ed116c` reached the same selection decision
on earlier dates. The runner report now includes an archive coverage
check and a day-level power sensitivity at the observed 2–3% runner
base rate.

[Step 2 and early-watch results](../research/RADAR_CANDLE_RESULTS_20261113.md)
are available. None of the three standalone candle scores advanced. The
early-watch replay observed about two minutes of median lead among successful
simulated graduates, with raw 3m move ahead of both candle challengers on
runner precision. The separate public backfill is running. The opt-in
16-rank quote recorder and existing v3 feature metadata need a collector
rollout before they can produce fresh rows.

Read the [sentiment and Chart Read audit](../research/RADAR_SENTIMENT_AND_CHART_20261113.md)
and the [Carbon or Gemini research assignment](CARBON_SENTIMENT_RADAR_ASSIGNMENT_20261113.md)
for the external attention and catalyst feasibility study.

The [received review and source checks](../research/RADAR_SENTIMENT_REVIEW_20261113.md)
identify Hyperliquid open interest as the first positioning feasibility
candidate. A short public probe succeeded. Asset mapping and usable
freshness still need measurement. The always-on collector is still writing
v2 only. The v3 rollout and a sustained external intake pilot are open.

Claude's [runner-study brief](https://github.com/tgpetrie/moonwalking/blob/b5248e1d6c0e00a124768b31cdf07de985a3c413/docs/research/RADAR_RUNNER_STUDY_BRIEF_20261113.md)
and [separate Carbon runner packet](https://github.com/tgpetrie/moonwalking/tree/a090711a5be561d2362348fba9a9393f70aed0fc/docs/research/review_packets)
are available from the fresh-replication branch. The local archive lacks
minute candles for the screen dates. The episode ledger covers ranks
1–8 and omits within-hour same-board re-entries. A broader early-watch
study needs evidence before board entry.

## November 13 research restart

Active continuation is `codex/instant-radar-research-restart-20261113`.
Read the [restart handoff](RADAR_RESEARCH_RESTART_20261113.md). The two
independent reviews are ready for Tom to dispatch. The full source bodies
in both upload packets are pinned to `257be69`.

- Carbon owns the hypothesis and fresh study design.
  [Prompt](CARBON_RADAR_RESEARCH_ASSIGNMENT_20261113.md) ·
  [Source packet](../research/review_packets/radar_20261113/CARBON_RADAR_SOURCE_257be69.txt) ·
  [SHA-256 manifest](../research/review_packets/radar_20261113/CARBON_RADAR_SOURCE_257be69_MANIFEST.json)
- Fable owns pipeline correctness and capture readiness on
  `claude/instant-radar-pipeline-review-20261113`.
  [Prompt](FABLE_RADAR_PIPELINE_ASSIGNMENT_20261113.md) ·
  [Source packet](../research/review_packets/radar_20261113/FABLE_RADAR_SOURCE_257be69.txt) ·
  [SHA-256 manifest](../research/review_packets/radar_20261113/FABLE_RADAR_SOURCE_257be69_MANIFEST.json)

Codex reverified the original US and Asia journals read-only. Both matched the
archived verifier results and reached zero timing cohorts. The VPN adapter
disconnect about 102 ms after the last Asia frame is a lead for the transport
diagnosis. The next decision is which bounded offline probe or additional
failure-time observation can distinguish plausible causes before any new
capture. The study freeze, feed gate and fitting remain closed.
The older dated checkpoints below remain historical evidence.

Updated November 10, 2026 (Pacific). This page is the current portable
checkpoint for the **instant radar scoring work**. GitHub holds the code,
contracts, completed results, work status and downloadable research evidence.
The [active-work record](ACTIVE_WORK.json) supplies the branch, implementation
commit, owners, gates and next actions in machine-readable form.

The active continuation branch is now **`codex/instant-radar-disconnect-diagnosis-20261111`**,
from verified Windows checkpoint **`598fba0`**. Verification **`975234e`** adds
ten offline disconnect probes; **1,253 Instant Radar tests pass** (60 focused),
with Black and guardrails passing. No reader-loss or propagation defect was
reproduced, so the reader runtime remains **`cfa4aff`**. Transport exception
text alone cannot link the disconnect to the later DNS error. The final marker
is an owner observation after draining, not an exact reader failure clock.
Read the [disconnect review and copy-ready Windows evidence collection command](../research/INSTANT_READER_DISCONNECT_REVIEW_20261111.md)
and [checks](../research/results/instant_reader_disconnect_20261111/CHECKS.json).
**Next: collect and inspect existing Windows logs before another pilot.**
No new capture, cap change or runtime fix ran. A documentation-only commit may
follow the verification checkpoint. Other agents' review status is preserved.

The previous branch `codex/instant-radar-overflow-diagnosis-20261110` continued
from verified Radar tip `fca475e`. Implementation **`cfa4aff`** adds a bounded
failure-time reader snapshot and 11 deterministic burst/stalled-writer cases.
**1,243 Instant Radar tests, guardrails and Black pass on Linux Python 3.12.14.**
The snapshot records arrival pressure and the writer phase at failure.
The cause of the original US overflow remains open because the preserved
capture lacks those fields. Read the
[offline diagnosis](../research/INSTANT_READER_OVERFLOW_DIAGNOSIS_20261110.md)
and [checks](../research/results/instant_reader_overflow_20261110/CHECKS.json).
The original `codex/instant-radar-20261028` is the historical base branch.

The bounded Windows Asia attempt at checkout `d24dadc` lost its connection
39m 14.898s after full subscription acknowledgment, before the 62-minute
warmup. The reader delivered all 167,405 received frames, with a sampled
high-water mark of 231 of 256 and zero overflows. The verifier checked
167,407 journal records and SQLite integrity. All 20 timing cohorts
were unreached. Fifty Windows regression checks passed. The immediate
post-run clock sample failed DNS resolution, and the retry returned all
five samples. Review the saved transport and clock evidence before
predeclaring another capture.
[Asia attempt evidence](../research/results/instant_reader_overflow_20261110/ASIA_01_VERIFIED.json).

The first [bounded live timing attempt](../research/INSTANT_LIVE_TIMING_PILOT_PROTOCOL_20261109.md)
at `91165cc` ended at the 256-frame reader queue limit. The last reader
receipt was 49m 03.474s after the six-product subscription acknowledgment.
The 62-minute warmup did not finish and none of the 20 planned cohorts ran.
The [independent verifier report](../research/results/instant_live_timing_20261109/US_01_VERIFIED.json)
confirmed the pinned plan, SQLite integrity and 302,679 journal records.
There are no +1.5s or +5s local delivery observations or readiness
measurements for this attempt. The startup check and earlier replay
remain separate evidence.

The separate [Coinbase paper-trading handoff](https://github.com/tgpetrie/moonwalking/blob/codex/coinbase-paper-trading/docs/ai/COINBASE_CLOUD_HANDOFF.md)
starts the account-integration work from existing Portfolio Mode. Its
offline exit comparison uses explicitly supplied bids and position costs.

The delayed eligibility draft at **`4b19a7a`** replayed all 166,035
saved packets at four fixed waits. The +1.5s view preserved the same complete decision-input slots as +5s.
It matched the original +5s feature results for all 80 rows. Local delivery
at the shorter waits remains unmeasured. **109 focused tests passed.**
[Replay results](../research/INSTANT_DELAYED_ELIGIBILITY_REPLAY_20261109.md).

The batched source follow-up at **`c9d79be`** reached its 67-minute stop
with 166,035 journal records and no reported queue overflow. All ten
cohorts completed and the local consumer observed all 80 rows. BTC and
SOL had all five features ready on every cohort row. ALCX and AURORA
still had missing features. **1,316 targeted checks pass**.
[Follow-up results](../research/INSTANT_BATCHED_SOURCE_PILOT_RESULTS_20261108.md).

Gemini's [15-source eligibility response](../research/reviews/GEMINI_ELIGIBILITY_REVIEW_20261109.md)
is received and [reconciled](../research/INSTANT_ELIGIBILITY_REVIEW_TRIAGE_20261109.md).
Keep complete-vector readiness separate from delivery and outcome gradability.
BTC cancels against itself under the current V2 residual, leaving SOL as the
only fully ready non-benchmark product in the pilot. The adapter and saved
journal comparison are complete. The +1.5s wait and +2.5s delivery age bound
remain candidates for a measured source check.
The earlier methodology assignment is complete.

The bounded journal writer at **`aa953b5`** passed crash and causal visibility
probes. The comparison verified 24 journals across both writer modes. All 256-frame
trials completed. Worst reader-to-commit time fell from 1.99s to 0.86s.
**1,313 targeted checks passed** at that checkpoint.
[Batching results](../research/INSTANT_BATCHED_JOURNAL_RESULTS_20261108.md).

The pre-acknowledgment book amendment is implemented at **`90ac993`**.
The preserved startup prefix verifies activation on acknowledgment under
a simulated clock. The burst harness at **`3e5e168`** overflowed in all six
128-frame trials. All six 256-frame trials completed, with up to 1.9s of
queue wait. **1,306 targeted checks passed** at that checkpoint.
[Startup and burst results](../research/INSTANT_STARTUP_AND_BURST_RESULTS_20261108.md).

The real indexed pilot at **`4aab7be`** ended at the 128-frame reader
queue limit after 20m 35.553s and 45,828 committed records. Warmup and
delivery probes were unreached. Coinbase sent ALCX's only snapshot
before its acknowledgment, leaving that book unavailable. The saved
prefix and clock checks are verified. **1,300 targeted checks pass**.
[Real indexed pilot results](../research/INSTANT_REAL_INDEXED_PILOT_RESULTS_20261107.md).

Indexed evidence at **`dddd2e4`** prepared 80 diagnostic decisions while
the synthetic recorder committed 241,208 packets on one connection.
Preparation p95 was 89 ms per decision. The full eight-decision cohort
with local outbox receipts took up to 682 ms. All 16 batch comparisons
matched and **1,296 targeted checks pass**. Next is the predeclared
real-data latency and readiness diagnostic.
[Indexed latency results](../research/INSTANT_INDEXED_LATENCY_RESULTS_20261107.md).

The opt-in warmup profile at **`a39d73e`** passed the 67-minute synthetic
run on one connection with 241,208 committed rows. All four products had
ready volatility and activity baselines at minute 62. Feature calculation
took 4.1–6.2 seconds per product after capture. The preserved live journal
shows zero fresh full ticker windows for ALCX and AURORA. **1,292 targeted
checks pass**. Next is incremental feature calculation under recorder load.
[Capacity and thin-quote results](../research/INSTANT_WARMUP_CAPACITY_RESULTS_20261107.md).

The four-product source pilot is complete at **`92ed71f`**. The corrected
attempt reached the packet budget in 34m 28s, short of 62 minutes of warmup.
All 272 sampled trade windows were verified by cutoff +5s. Full fresh
book windows were available at 68/68 BTC and SOL probes, 14/68 ALCX probes
and 61/68 AURORA probes. **1,290 targeted checks pass**. Both attempts and
raw journal digests are preserved. Read the
[pilot results](../research/INSTANT_SOURCE_PILOT_RESULTS_20261107.md)
and [predeclared protocol](../research/INSTANT_SOURCE_PILOT_PROTOCOL_20261107.md).

The streaming journal is implemented at **`ce2dd03`**. It allocates a new
identity per connection, commits original packet and trade processing evidence,
and records local publication commit observations. After a process exit, the
committed prefix can be read and a fresh segment can begin. **1,283 targeted
tests passed** at that checkpoint.
[Journal draft](../research/INSTANT_STREAM_JOURNAL_20261107.md)
and [checks](../research/results/instant_stream_journal_20261107/CHECKS.json).

Delayed decision snapshots and later cutoff grading are implemented at
**`ad67a3a`**. A later grading view can mark evidence unavailable while the
original snapshot remains reproducible. **1,271 targeted tests passed** at
that checkpoint.
[Decision and grading draft](../research/INSTANT_DELAYED_DECISION_20261107.md)
and [checks](../research/results/instant_delayed_decision_20261107/CHECKS.json).

Timed F1–F5 features are implemented at **`2838eb6`**. F3 uses the full 30s
sampled book window. F4 uses receipt-time candles from 15 closed minutes
ending before the expansion window. **1,261 targeted tests passed** at
that checkpoint. [Feature draft](../research/INSTANT_TIMED_FEATURES_20261107.md)
and [checks](../research/results/instant_timed_features_20261107/CHECKS.json).

Timed volatility, BTC beta and activity baseline components are implemented at
**`2ac3b25`**. They use declared windows, measured evidence and computation
times, and independent volatility and pace readiness. **1,252 targeted tests
passed** at that checkpoint. [Baseline draft](../research/INSTANT_TIMED_BASELINE_20261106.md)
and [checks](../research/results/instant_timed_baseline_20261106/CHECKS.json).

Claude's input-evidence review `f1ab7d5` is accepted as **`086eb20`** with
46 independent probes, no defect and no code patch. Its **1,241 targeted tests passed**
on Windows Python 3.12.10. Read [the acceptance](../research/INSTANT_INPUT_REVIEW_ACCEPTANCE_20261106.md).
The separate [Gemini methodology task](GEMINI_METHOD_REVIEW_20261104.md) used the
[uploadable packet](../research/review_packets/GEMINI_METHOD_SOURCE_PACKET_20261104_fee55a7.txt)
with 29 complete files pinned to `fee55a7`. Its
[manifest](../research/review_packets/GEMINI_METHOD_SOURCE_PACKET_20261104_fee55a7_MANIFEST.json)
verifies all source bodies and the identical Downloads copy. Keep the pinned
packet as provenance; there is no need to upload it for a duplicate review.
The new 29-file response is now received and
[reconciled](../research/INSTANT_METHOD_REVIEW_TRIAGE_20261106.md) at **`840ff97`**.
**1,247 targeted tests pass**, including six new synthetic timing-boundary cases.
The candidate formulas remain, but late-proof availability cannot be relabelled
as receipt-only; the 2,500ms budget and entry/model/readiness choices remain
unfrozen. Both external assignments are complete; no duplicate review is queued.

The reviewed **`8607a36`** implementation (accepted at `086eb20`) added input-evidence stage 1: complete
declared product/cutoff/direction accounting, measured new packet/trade
processing completion, coin/BTC component checks and frozen cutoff cohorts.
Read
[the scope](../research/INSTANT_INPUT_EVIDENCE_20261104.md) and
[initial checks](../research/results/instant_input_evidence_20261104/CHECKS.json).
[Independent review](CLAUDE_INPUT_EVIDENCE_REVIEW_20261104.md) is accepted.
The baseline commit `2ac3b25` shares the stage 1 quote and trade-window
helpers and preserves its schema. Positive eligibility still requires
full-health, publication and decision evidence.

Directional implementation **`9da4987`** adds an opt-in directional exposure
report with own-direction gradability, explicit eligibility cutoffs, time
unions and same-direction ranker comparison rows. Claude review `583a73a`
is accepted as **`4925ac5`** with no defect found or code patch. **1,163 targeted
tests pass**, including 51 independent review probes. Read
[the draft](../research/INSTANT_DIRECTIONAL_EXPOSURE_20261104.md) and
[acceptance/checks](../research/INSTANT_DIRECTIONAL_REVIEW_ACCEPTANCE_20261104.md).
The focused [Claude review prompt](CLAUDE_DIRECTIONAL_EXPOSURE_REVIEW_20261104.md)
is complete; do not repeat it. The full eligibility evidence producer is still open;
the directional reporter's flags and clocks remain caller assertions. Existing joint reporting,
greedy association, targets, monitor, book/publication and production are unchanged.

Reconciliation checkpoint **`055d590`** accepts local Claude's bounded
merging, continuity correction `d26c57d` (as `d80418e`) and second probe set
`1af0a64`. **1,064 targeted tests pass**, including the newer book/publication
tests. The same-millisecond blocker is resolved; original failures and
receipt attribution remain preserved. Read the
[acceptance](../research/INSTANT_RECONCILIATION_ACCEPTANCE_20261104.md) and
[checks](../research/results/instant_reconciliation_acceptance_20261104/CHECKS.json).
The unchanged hour's 33 ordering failures reconcile into 16 bounded proofs.
This does not pass the feed gate or enable fitting. No new capture, outcome
study, target or live change occurred. The baseline components above use
the accepted reconciliation for timed trade proofs.

Book code **`5ff6a8f`** accepts cloud review `6abd95e`, fixing
premature heartbeat knowledge and text-only BBO clock changes. **579 targeted
tests pass** in pinned Windows Python 3.12.10. Read the
[acceptance](../research/INSTANT_BOOK_REVIEW_ACCEPTANCE_20261104.md) and
[checks](../research/results/instant_book_review_acceptance_20261104/CHECKS.json).
The [cloud review assignment](CLAUDE_CLOUD_BOOK_REVIEW_20261104.md) is complete.
Do not repeat it. The former
[same-millisecond continuity blocker](../research/RECONCILIATION_BOUNDARY_REVIEW_20261104.md)
is resolved by the acceptance above. The publication module and targets are unchanged.

Previous checkpoint **`8631231`** accepts cloud association/exposure `96f5652`
(as `e3529c2`) with two validation fixes and three additional tests.
**521 targeted checks pass** in pinned Windows Python 3.12.10. Read the
[acceptance](../research/INSTANT_ASSOCIATION_ACCEPTANCE_20261104.md) and
[verification](../research/results/instant_association_acceptance_20261104/CHECKS.json).
Claude's Linux/3.13 report is retained; no native Mac or full-suite pass is claimed.

The cloud assignment is complete and accepted as a reporting draft. Local
Claude's bounded reconciliation is accepted through `055d590`, including the
two follow-up commits. Do not repeat the completed cloud implementation.
The older `4610bf2` raw-catalog change is not merged: the reporting wrapper
already supplies left-censor flags and is used by association. S1 retains
whole-window strict timing plus a separately named forward-peak diagnostic.
Targets/V1/V2 and all production code remain unchanged; the study is unfrozen.

Previous checkpoint: book/publication draft **`8c51878`** plus accepted coverage-review
fixes **`652f5af`**. Read the
[book/timing implementation](../research/INSTANT_BOOK_AND_PUBLICATION_20261103.md),
[review acceptance](../research/INSTANT_COVERAGE_REVIEW_ACCEPTANCE_20261103.md)
and [468 passing checks](../research/results/instant_book_publication_20261103/CHECKS.json).
The user's older 363-check resume prompt is superseded by these checkpoints.
Do not rebuild completed adapters or repeat general accepted reviews.

Local Claude's `claude/instant-coverage-reconciliation` is pushed at `1af0a64`
and accepted through `055d590`. Cloud Fable completed the separate
[association/exposure assignment](CLAUDE_CLOUD_ASSIGNMENT_20261103.md); its
implementation is accepted in the current checkpoint above.
Codex owns book/timing and integration. No capture, fit, held `d711832` merge
or live integration occurred. New sources/tests/results are in Git; existing
raw-evidence bundles remain valid.

Book replay preserves atomic batches, original quote/change ages and measured
processing completion. It does not enter legacy target samples or certify
continuous F3/full-feed readiness. Publication clocks are explicit; a
publication-anchored target and numerical lag limit remain separate drafts.
The batched source follow-up reached warmup on the tested profile.
Predeclare feature and product eligibility from the measured readiness
and retain the original feed gate and study freeze as separate requirements.

The preserved-capture verifier stays `a5bb397` (recorded run `837db34`),
recorder/baseline `ab95159`, and target evaluator/V1/V2 `92fb51d`.
Earlier replay preserved 63,258 packets / 24,424 live matches. The new review
check independently confirms 33 strict ID failures reconcile across adjacent
runs without changing receipt counts; no expected ID in the heartbeat ranges
is absent. All 14,396 raw proofs are unchanged by the fixes apart from actual
processing time. This is not a gate pass, a new capture or a return/label study.
The old 363- and 405-check records remain pinned historical checkpoints.

October 30 update: both source-based Gemini responses have been received,
reproduced and [triaged](../research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md).
The opt-in v2 draft at `8b5b266` adds a forward-window catalog and names
reference-dependent timing metrics; it incorporates Claude's reviewed
baseline cutoff. V1 stays the default. Claude's independent code review is
complete at `10b0f96`; Codex accepted its catalog/version guard fix through
**`92fb51d`**, the current implementation. Read the
[acceptance and remaining decisions](../research/INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md).
The study remains unfrozen and fitting stays off.

Gemini's v2 design response is now received and reconciled in the
[consolidated study-rule candidate](../research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md).
The eight reported source hashes match its pinned packet. Synthetic checks
show why narrowing the peak window changes the metric, and why catalog
association must not erase a failed prediction at its own horizon. The draft
keeps both questions visible, retains causal cutoffs, proposes null reasons
and concrete five-feature formulas. These are reviewable recommendations,
not frozen code or fitted weights. Current executable labels stay at `92fb51d`.
The original [source packet](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a.txt)
and [manifest](../research/review_packets/GEMINI_SOURCE_PACKET_941f47a_MANIFEST.json)
remain pinned to `941f47a` as evidence of what Gemini reviewed; they do not
contain the v2 draft. Gemini did not inspect the original unamended proposal
as a separate source, so a full original-fidelity claim is still unwarranted.
The full [pre-source conceptual response](../research/reviews/GEMINI_PRE_SOURCE_CONCEPTUAL_REVIEW_20261030.md)
is now archived separately. Its extra suggestions are classified in the triage;
that initial v1 review history is one conceptual response and two source-based
responses; the later v2 design response is recorded above.
It supplies no additional implementation verification or reason to change
the current v2 draft automatically.

Bookmark this page:
<https://github.com/tgpetrie/moonwalking/blob/codex/instant-radar-20261028/docs/ai/RESUME_HERE.md>

The separate fundamentals driver review is complete at `8708c25` on
`codex/fundamentals-driver-review-20261030`. Corrected no-fit readiness and 77
targeted checks pass; discovery and the primary test have not run. The accepted
cohort does not need another Gemini pass. Its 30 exact input files have a
verified GitHub backup. Use the
[fundamentals resume page](https://github.com/tgpetrie/moonwalking/blob/codex/fundamentals-driver-review-20261030/docs/ai/FUNDAMENTALS_RESUME_20261030.md)
for that lane; its readiness does not enable instant-radar fitting.

## Current checkpoint

| Item | Current state |
|---|---|
| Repository | `tgpetrie/moonwalking` |
| Resume branch | `codex/instant-radar-20261028` |
| Current implementation | Batched source follow-up `c9d79be`; bounded writer `aa953b5`; startup and burst verification `3e5e168`; real indexed pilot `4aab7be`; indexed decision evidence `dddd2e4`; warmup capacity `a39d73e`; source pilot `92ed71f`; stream journal `ce2dd03`; delayed decisions and later grading `ad67a3a`; timed features `2838eb6`; timed baseline components `2ac3b25`; original input-evidence stage 1 `8607a36`, review accepted `086eb20`; directional draft `9da4987` reviewed `4925ac5`; reconciliation `055d590` (monitor `d80418e`); book fixes `5ff6a8f`; association `8631231`; legacy verifier `a5bb397` (recorded run `837db34`); legacy recorder `ab95159`; target evaluator `92fb51d` unchanged |
| Instant targets | V1 default preserved; Claude fix accepted; Gemini v2 response reconciled into a study-rule draft; no study freeze |
| Checks | 1,316 targeted tests pass, including three follow-up profile and timing cases, seven batch writer cases and six startup cases, four real-pilot boundary cases and four index parity cases, two capacity/timing cases and seven socket cases, twelve stream-journal cases, ten decision/grading cases, nine timed feature cases, five timed baseline cases, six methodology timing-boundary cases and 46 independent input-evidence probes; earlier replay preserved 63,258 packets / 24,424 matches; formatting, guardrails and 11 historical hashes pass; no full-suite claim |
| Historical experiment | Complete, locked, inconclusive; do not rerun discovery/validation or tune against it |
| Feed audit | One uninterrupted hour completed; sampled coverage REST-reconciled; thin-product side evidence insufficient, overall gate false |
| Live behavior | No ranking, weights, recorder integration or production deployment change |

The instant radar and developing-move boards were always meant to use their
own targets/formulas, sharing market data with broader outlook scores. The
historical three-input comparison did not evaluate Gemini's F1-F5 proposal.
Current work continues that proposal, with fixed 30s/180s input windows and
separate 5m/15m outcomes.

Read these next:

1. [Agent rules](../../AGENTS.md), [AI index](AI_INDEX.md),
   [handoff](../../HANDOFF.md) and [backlog](../../MW_BACKLOG.md).
2. [Review triage / v2 draft specification](../research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md)
   and [v2 JSON](../research/INSTANT_TARGET_CONTRACT_V2_DRAFT.json); the
   [v1 definition](../research/INSTANT_TARGET_LABELS_20261029.md) and
   [v1 JSON](../research/INSTANT_TARGET_CONTRACT_V1.json) remain available.
3. [Corrected prospective contract](../research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md),
   [execution sequence](../research/INSTANT_RADAR_NEXT_STEPS_20261028.md) and
   [locked historical results](../research/LIVE_MOVERS_RESULTS_20261027.md).
4. [Review assignments](INSTANT_RADAR_REVIEW_BRIEF_20261029.md) and
   [completed audit report](../research/results/feed_audit_20261028_completed/REPORT.json).

## Who owns the next actions

Copy-ready [v2 review prompts and attachments](INSTANT_V2_REVIEW_PROMPTS_20261030.md)
are prepared for Claude, Gemini, local 14B and local 9B. The new Gemini packet
contains eight complete sources at `cc3b6a6` (implementation `8b5b266`), so it
includes v2 rather than the old v1-only packet. Claude has now received the
user's start instruction and full role prompt and completed its code review.
Codex accepted its patch/probes; see the acceptance report. The full packet is
still pinned to the initial v2 source, before the catalog guard fix. Include
the acceptance report/patch as a follow-up addendum. Gemini's v2 response has
now been supplied by the user and reconciled; local v2 dispatch is unverified.

| Owner | Assignment | Verified status |
|---|---|---|
| Codex | Own implementation, reproduce findings, integrate reviewed fixes, maintain this checkpoint | Offline Asia disconnect review complete; collect existing Windows logs before another pilot |
| Local Claude | Review plus bounded reconciliation implementation | Review branch `1af0a64` accepted; same-millisecond correction verified; no further patch requested |
| Cloud Claude / Fable | All assigned reviews complete | Input review `f1ab7d5` accepted; no new assignment queued |
| Gemini | Target methodology and post-pilot eligibility review | Both responses received and reconciled. Timing and cohort thresholds remain proposals |
| Local 14B | Bounded source/trace review; findings require deterministic verification | One bounded review completed; two suggestions unsupported by code/tests |
| Local 9B | Summarize supplied logs/test failures | No active assignment verified |

On this Windows PC, Codex works in
`C:\Users\tgpet\Projects\Moonwalking-InstantRadarOverflow-20261110`. Claude's current review
worktree is `C:\Users\tgpet\Projects\Moonwalking-InstantRadarReview`, branch
`claude/instant-coverage-reconciliation`; its earlier `claude/instant-radar-v2-review`
and `claude/instant-radar-review` branches are preserved. Its original separate checkout is
`C:\Users\tgpet\Projects\Moonwalking-Claude`. These are location hints for
this computer, not required paths on another machine. Preserve other agents'
work and use separate branches/worktrees for fixes.

Next, inspect the existing Asia transport and clock evidence using the new
disconnect review; do not repeat a timing pilot yet. The original US overflow
cause is still unresolved. Keep the four-product
gate and >=62 complete warmup minutes. Feature/stage/model/readiness rules,
association/exposure rule freeze and overall study freeze remain required before
14 valid shadow days and fitting. Do not repeat completed outcomes or captures
merely to seek a favorable verdict.

## Unattended checks on a saved timing attempt

Once a capture has finished, run this from the repository root with the
repository's Python environment and pytest. Substitute the finished attempt,
its original plan digest, and a new local output directory.

```text
python -m scripts.scoring_experiment.run_instant_offline_checks --attempt <saved-attempt> --plan-sha256 <pinned-digest> --out-dir <new-local-folder> --model qwen3.5:9b
```

It verifies the saved evidence, runs the journal, socket and timing regression
tests, and optionally asks local Ollama for an advisory note. A verifier or test
failure stops the remaining checks. The run status, verified results and test
log are the evidence. The advisory note is separate and never runs commands.
Omit `--model` on a computer without Ollama. Keep outputs outside the checkout
and use a new directory for each run. A complete job can verify an incomplete
capture. On the US capture, the job verified 302,679 journal records, found
zero timing observations, and passed 39 regression checks.

Codex owns local capture evidence, queue diagnosis, integration and the
next predeclared pilot. Claude is on the separate design work. An
independent Fable code review can follow when that slot is available.
Gemini Argon can review the evidence needed to freeze eligibility, timing
and study rules using the reconciled sources. The Coinbase paper
experiment stays on its separate branch.

Use the Codex handoff when a result is ready to review, a reproducible
failure blocks progress, or a decision changes study scope or a gate.
Send the branch and commit or result link, what passed or failed, and
the single decision needed if there is one. A finished design handoff
should include the preview and build brief. Routine progress can stay
in the job log. The local checker records status on disk.

## Code and environment on another computer

For a new, absent destination directory:

```bash
git clone --branch codex/instant-radar-disconnect-diagnosis-20261111 https://github.com/tgpetrie/moonwalking.git Moonwalking-InstantRadar
cd Moonwalking-InstantRadar
```

Each cloud task is already isolated: use its existing clean checkout and a named
branch; do not create a worktree unless explicitly requested. For an existing
PC checkout, inspect remote, status and worktrees, then fetch
and use the named branch in a suitable separate worktree. Never overwrite
uncommitted work. Both checkout and Git common storage must be outside
OneDrive/synced folders. Follow [the access procedures](WORK_FROM_ANYWHERE.md).

Use Python 3.12 and a fresh local virtual environment. The research dependencies
are pinned in [this requirements file](requirements-macbook-research-20261027.txt);
the filename is historical, and the small environment also supports the new
standard-library target evaluator. Activate the environment for your OS, then:

```bash
python -m pip install -r docs/ai/requirements-macbook-research-20261027.txt
python -m pytest -o addopts= -q tests/test_preserved_feed_replay.py tests/test_micro_replay_review.py tests/test_micro_replay.py tests/test_instant_diagnostics.py tests/test_instant_targets.py tests/test_instant_targets_v2.py tests/test_instant_targets_v2_review.py tests/test_feed_audit_campaign.py tests/test_coinbase_feed_audit.py tests/test_live_contract.py tests/test_live_movers_run.py tests/test_live_movers_review.py tests/test_restore_macbook_evidence.py backend/tests/test_coinbase_ws.py
bash scripts/validate_mw_guardrails.sh
```

These tests use fixtures; they do not rerun historical discovery/validation.
Native Mac/cloud execution still requires checking the environment there.

## Research evidence stored in GitHub

The existing **draft** release `research-handoff-20261027` now carries two
complementary bundles. Use an authenticated GitHub account with release
access. A source checkout alone does not download release assets.

| Bundle | Contents | Committed manifest |
|---|---|---|
| `moonwalking-live-movers-evidence-20261027.tar.gz` (~112 MB) | Frozen public-market research DB/CSV, historical results and persistent validation-attempt marker, first interrupted audit | [Base manifest](MACBOOK_EVIDENCE_MANIFEST_20261027.json) |
| `moonwalking-instant-evidence-20261029.tar.gz` (~9.55 MB) | Second interrupted audit and completed one-hour campaign, raw WS/REST captures, reports, original hashes and status | [Supplement manifest](INSTANT_EVIDENCE_MANIFEST_20261029.json) |
| `moonwalking-capture-replay-20261030.tar.gz` (~5.18 MB) | Derived run-01 SQLite, explicitly retrospective health and replay/report hashes | [Replay manifest](CAPTURE_REPLAY_EVIDENCE_MANIFEST_20261030.json) |

Download from any authenticated machine into a new `handoff-downloads` folder:

```bash
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --dir handoff-downloads --pattern moonwalking-live-movers-evidence-20261027.tar.gz
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking --dir handoff-downloads --pattern moonwalking-instant-evidence-20261029.tar.gz
python scripts/restore_macbook_evidence.py handoff-downloads/moonwalking-live-movers-evidence-20261027.tar.gz
python scripts/restore_macbook_evidence.py handoff-downloads/moonwalking-instant-evidence-20261029.tar.gz --manifest docs/ai/INSTANT_EVIDENCE_MANIFEST_20261029.json
```

The restore tool verifies the exact file list, archive/member hashes, safe
destinations and existing files. It skips identical files and refuses to
overwrite different files. Add `--verify-only` to inspect without restoring.
Default destination is `~/.moonwalking/analysis` on the new machine.

The supplement includes
`feed_audit_campaign_20261028/attempt-01/` and
`feed_audit_20261028_1h/`; use paths under the new machine's analysis directory.
Absolute Windows paths inside original status files describe provenance and
must not be treated as current paths. The base bundle's validation-attempt
marker must remain in place. Do not rerun the locked experiment after restore.

The [upload/verification receipt](INSTANT_GITHUB_TRANSFER_20261029.json)
records cloud asset hashes and round-trip verification. The older
[MacBook handoff](MACBOOK_HANDOFF_20261027.md) describes the base bundle;
its old resume branch and unfinished-audit instructions are superseded by
this checkpoint.

Public-market research is backed up. Live account/portfolio stores, production
credentials, `.env`, virtual environments and AI session folders stay on their
own machines. The Windows collector is a separate running service on port
5003; fetching the research branch does not migrate that service.

## Paste into any next session

> Resume Moonwalking's instant-radar work from repository
> `tgpetrie/moonwalking`, branch `codex/instant-radar-overflow-diagnosis-20261110`.
> The verified base was `fca475e`; overflow instrumentation is `cfa4aff`.
> Read INSTANT_READER_OVERFLOW_DIAGNOSIS_20261110.md first. Offline burst and
> stalled-writer tests pass (1,243 Instant Radar tests). The US capture remains
> inconclusive before warmup. The Windows Asia attempt lost its connection
> before warmup, with zero overflows and zero timing observations. Read the
> verified Asia evidence above before planning another capture.
> Read `docs/ai/RESUME_HERE.md` and `docs/ai/ACTIVE_WORK.json`, then follow
> `AGENTS.md`. Verify the current GitHub tip and review status before acting.
> Batched source follow-up `c9d79be` has 1,316 targeted tests passing.
> Attempt 01 is complete. Read the November 8 batched source results.
> Bounded writer verification is `aa953b5`.
> Read the November 8 batched journal results and startup and burst results.
> The real indexed pilot is `4aab7be`.
> Read the November 7 real indexed results. The capture stopped at the
> reader queue limit before warmup. Indexed decision evidence is `dddd2e4`.
> Read the November 7 indexed latency results before the real-data protocol.
> Warmup capacity `a39d73e` passed 67 simulated minutes on one connection,
> with 1,292 targeted tests passing. Read the November 7 capacity results.
> The source pilot is `92ed71f`. Read its
> November 7 results. It stopped at the packet cap in 34m 28s.
> The stream journal is `ce2dd03`.
> Delayed decisions and later cutoff grading are `ad67a3a`.
> Timed features are `2838eb6`. Read the November 7 decision and grading draft.
> Timed baseline components are `2ac3b25`. Read the November 7 feature draft.
> Stage 1 input-evidence review is accepted at `086eb20`; methodology
> reconciliation is `840ff97`. Positive eligibility still requires quote-health,
> decision and publication evidence. Directional reporting
> draft is `9da4987`, independent review accepted `4925ac5`.
> Reconciliation is accepted through `055d590` (monitor `d80418e`), book fixes
> at `5ff6a8f`, association at `8631231`.
> Latest preserved-capture verifier is `a5bb397`; replay ran at `837db34`;
> recorder is `ab95159`, target evaluator unchanged `92fb51d`.
> Read INSTANT_CAPTURE_REPLAY_RESULTS_20261030.md for the real data findings.
> Read the October 30 Claude acceptance and consolidated study-rule candidate.
> Gemini's v2 and current 29-file methodology responses are received/reconciled; the study remains unfrozen.
> V1 stays default. The real replay is complete but then-known health,
> thin quotes and baseline warmup remain blockers. Read the November 4
> reconciliation, book and association acceptance reports. Those draft
> earlier implementations and directional review are complete; do not repeat them.
> Predeclare eligibility and missingness rules using the follow-up readiness evidence.
> Preserve thin-product reporting and both stopped capture prefixes.
> Fitting remains off; no physical onset is inferred yet.
> Restore the documented GitHub evidence if needed. Historical validation
> is locked; the feed gate is still inconclusive. Keep live scoring and
> production unchanged. Update the portable checkpoint, commit and push
> completed work before handing off.

For a conversation without repository access, supply this page, the active-work
JSON, target definition and historical results as files or text.

## Keep this record current

At each coherent handoff, the implementation owner updates this page and
`ACTIVE_WORK.json` with the code checkpoint, evidence location, completed
checks, agent-review status, open gates and exact next action, then pushes.
Keep a new active-branch pointer here when work moves to another branch.
Documentation-only commits may follow the recorded implementation hash;
the branch's Git history gives the exact latest documentation checkpoint.
This page reconstructs the task without relying on a particular chat history.
