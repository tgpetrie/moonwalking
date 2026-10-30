# Moonwalking / BHABIT Handoff

## Preserved feed replay complete; data-readiness blockers measured — 2026-10-30

The completed October 28 capture was replayed once with adapter `837db34`;
the follow-up receipt-span guard at **`a5bb397`** also accepts that unchanged
3,600,154ms source span. Recorder `ab95159` and target `92fb51d` are unchanged.
Read [the real-data verification results](docs/research/INSTANT_CAPTURE_REPLAY_RESULTS_20261030.md).

- 63,258 packets / 24,424 unique live matches are preserved; counts equal the
  frozen audit and USD totals/bucket amounts agree within $0.000001.
- All 719 interior buckets/product reconcile retrospectively. Endpoint
  midpoint freshness is BTC 719, SOL 709, ALCX 6 and AURORA 4 out of 719.
- The later coverage proof is never backdated: all 2,876 original-as-of
  cutoff queries remain unverified. The hour also lacks full baseline warmup.
- The original thin-side gate stays false. Stale quotes are unavailable,
  not fresh carried values; no source/universe rule was relaxed.
- 363 targeted checks, formatting, guardrails, six source hashes and all
  11 historical contract hashes pass. Source files are unchanged.
- The 29,020,160-byte derived SQLite/report/health evidence is on the existing
  authenticated draft release. All four downloaded/restored members match
  their hashes and SQLite integrity passes; manifests/receipt are in Git.

Next is contemporaneous health/subscription/reconciliation availability and
paired immutable samples, a declared thin-product quote policy, and at least
62 complete warmup minutes before valid study rows. New source/universe or
supplemental diagnostic changes must be versioned/predeclared. No capture,
return-label study, fit, live service or ranking changed. Older "next replay"
records below are superseded; no general AI review is queued for this replay.

## Independent offline review accepted — 2026-10-30

Claude's new `f2cc436` offline review was verified and cherry-picked as
`749e792`; current offline code is **`ab95159`**, including source provenance
and independent missing-data reasons. The older pasted `10b0f96` v2 report
was already integrated and was not reapplied. Read the
[offline acceptance](docs/research/INSTANT_OFFLINE_REVIEW_ACCEPTANCE_20261030.md).

The reproduced monotonic-clock hole (`100s, absent, 50s`) now fails closed.
Untagged WS input compatibility is retained; recovery adapters must preserve
source identity. Baselines expose producer/input provenance, reopen can pin
the producer hash, and historical producers remain distinguishable from readers.
Health evidence must be completed and known by each intended cutoff; cadence
does not justify backdating delayed reconciliation. Assertions remain trusted
inputs requiring independent evidence.

**356 targeted checks pass**, including seven independent Claude probes and
three new Codex producer/reason cases. Formatting, guardrails, 11 historical
hashes and unchanged target-byte checks pass. The target evaluator/contracts
remain `92fb51d`; no full-suite or native Mac pass is claimed. The unrelated
seed-fixture failure remains outside this check set.

The offline review is complete; no general re-review is queued. Next is
bounded replay of preserved feed data plus evidence-backed health/subscription/
reconciliation and paired immutable sample adapters. Feed/study/model/live
gates remain off. No capture, fit, historical rerun, service or other worktree
changed. Older prepared/pending review records below are superseded.

## Offline recorder/baseline implementation — 2026-10-30

New offline layer implemented at **`8211262`** on
`codex/instant-radar-20261028`. Read
[usage and scope](docs/research/INSTANT_OFFLINE_PIPELINE_20261030.md).
The existing target evaluator and V1/V2 contract bytes remain at `92fb51d`.

- Versioned reporting adds explicit null reasons, a separately named
  forward-peak fraction and catalog gap/sampling-edge censoring flags.
- Sparse SQLite packet replay deduplicates live matches, inverts maker side,
  retains unknown amounts, excludes recovery/last_match/ticker sizes from
  execution totals, and reconstructs healthy empty buckets without new OHLC.
- Coverage is explicitly known-at; late audit knowledge cannot backdate a
  live snapshot. Quotes preserve age, and gaps/clock regressions fail closed.
- The builder derives 60 closed minute returns and 120 nonoverlapping pace
  windows at the prescribed cutoffs, with causal metadata and beta fallback.
- **346 targeted checks pass**, including 30 new diagnostic/replay/baseline
  cases. Black 24.8.0, guardrails, 11 historical hashes and target-byte checks
  pass. No full-suite or native Mac pass is claimed.

Next is bounded independent review of this new layer and real-data/reconciliation
adapter verification. A [Claude prompt](docs/ai/INSTANT_OFFLINE_REVIEW_PROMPT_20261030.md)
is prepared, not dispatched. The remote Claude onset/gap branch was inspected
and recorded; it was not merged into the target module. No raw-data campaign,
service, predictive scoring fit, live ranking or other worktree changed.
Feed, stage/model/readiness, study freeze and shadow-data gates remain open.
The older "next implementation" records below are now historical checkpoints.

## Gemini v2 review reconciled; consolidated study draft — 2026-10-30

Gemini's v2 response is archived at
`docs/research/reviews/GEMINI_V2_DESIGN_REVIEW_20261030.md`; all eight claimed
source hashes match the pinned packet. The source was initial `8b5b266` plus
the acceptance report, not an independently executed review of patched code.
The original unamended proposal remains absent.

Read [the consolidated study-rule candidate](docs/research/INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md).
It retains the whole-reference-window peak and proposes a separately named
forward-peak fraction, retains the distinct causal baseline cutoffs, and
specifies missing-fraction reasons for a future additive schema amendment.
Gemini's S1 is a metric change, not a violation of the existing contract.
Its broad false-alert association rule can excuse failed 5m/15m predictions
with a move outside their horizon; reproducible synthetic cases are committed.
The draft keeps pointwise outcomes and window-coverage diagnostics separate.

Five concrete feature formulas are proposed for implementation review, not
frozen or fitted. No evaluator or executable JSON contract changed: current
code remains **`92fb51d`**. The 316 targeted-check result belongs to that code
checkpoint. New evidence here is a replayable synthetic design check plus
archive/hash/link/guardrail verification, not market performance.

Next concrete work is the versioned diagnostic/reporting amendment and an
offline recorder/baseline-builder contract with bounded replay tests. Stage,
model/readiness and final matching rules still need implementation/freeze;
the feed gate stays false. No shadow campaign, fit, historical rerun, live
service or other agent was launched or changed in this checkpoint. The older
review/dispatch records below are historical, superseded by this section.

## Claude v2 review accepted; study definitions still open - 2026-10-30

Claude completed the independent review at `10b0f96`. Codex reproduced and
accepted its catalog/version guard fix, cherry-picked the review/probes as
`1da6f4e`, and formatted the code/tests at **`92fb51d`**, the current
implementation. Both contract JSON files are unchanged. Read the
[acceptance and remaining decisions](docs/research/INSTANT_V2_REVIEW_ACCEPTANCE_20261030.md)
and [Claude's report](docs/research/reviews/CLAUDE_INSTANT_V2_REVIEW_20261030.md).

316 targeted checks pass, including 265 target cases. Guardrails, formatting
and all 11 historical artifact hashes pass. The unchanged isolated seed fixture
still fails (60 points versus 10); no full-suite pass is claimed. V2 evaluator
hashes changed: regenerate unfrozen labels before evaluation. Earlier-wick
timing, sigma/pace cutoffs and null-reference diagnostic policy remain explicit
pre-freeze decisions. Gemini v2 review and the data/study gates remain open;
fitting, historical reruns and live changes stay off.

The dispatch record below is historical. Claude's code review is complete;
do not redispatch it solely because an older prepared prompt says pending.

Four copy-ready role prompts and fresh v2 attachments are in
[`docs/ai/INSTANT_V2_REVIEW_PROMPTS_20261030.md`](docs/ai/INSTANT_V2_REVIEW_PROMPTS_20261030.md).
The full Gemini packet contains eight verified sources from `cc3b6a6`, with
implementation `8b5b266`. Bounded local 14B/9B packets are also committed;
convenience copies are in this PC's Downloads folder. The user has now sent
Claude "Start the review" and the full role prompt. Codex verified Claude's
active response in the desktop app and its branch
`claude/instant-radar-v2-review` in `Moonwalking-InstantRadarReview`, based on
Codex documentation checkpoint `5e02268` with implementation `8b5b266`.
Claude is reading/reviewing the v2 sources; no completed signoff is claimed.
Codex did not resend the assignment or edit Claude's active worktree.
Gemini/local v2 prompts remain prepared with dispatch unverified. The prior
14B review found no confirmed defect, and the 9B has not been run by Codex.
Fitting, historical reruns and live changes stay off.

The separately authorized fundamentals driver review is complete and pushed at
`8708c25` on `codex/fundamentals-driver-review-20261030` (reviewed code `6809933`).
Its corrected no-fit readiness passes; 77 targeted checks pass. Discovery and
the primary test remain unrun. All 30 exact public-market input files are backed
up on the existing authenticated GitHub draft release and were downloaded and
restored with matching hashes. Start with the
[fundamentals resume page](https://github.com/tgpetrie/moonwalking/blob/codex/fundamentals-driver-review-20261030/docs/ai/FUNDAMENTALS_RESUME_20261030.md).
That broader experiment remains separate from this instant-radar implementation.

## Pre-source Gemini response archived - 2026-10-30

The user supplied the full earlier Gemini response that declared no repository
access. It is archived separately as
`docs/research/reviews/GEMINI_PRE_SOURCE_CONCEPTUAL_REVIEW_20261030.md`.
The review manifest and triage now distinguish one conceptual response from
two source-based static responses. MAE/TWAP, a retrospective physical-origin
rule, residualization and alternate inference/feature definitions are recorded
as candidate study choices, not accepted code defects. The early broad
continuation-only claim was corrected after source access. This is not the
missing original unamended proposal. No v2 code or threshold changed; the
implementation checkpoint remains `8b5b266`, with independent v2 review pending.

## Source-review triage and opt-in v2 draft - 2026-10-30

Implementation checkpoint: `8b5b266` on `codex/instant-radar-20261028`.
Both source-based Gemini responses are preserved and triaged in
[`docs/research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md`](docs/research/INSTANT_TARGET_REVIEW_TRIAGE_20261030.md).
Synthetic cases reproduce the trigger-origin/catalog limitations and reject
overstated F1/F2 algebraic guarantees; LF hashing already works. The original
proposal was not separately inspected by Gemini, so original-fidelity review
remains limited to the corrected documents.

V1 JSON/default valid-label behavior and the pinned source packet remain
unchanged. Explicit `contract_path=V2_CONTRACT_PATH` enables a draft with
`verified_forward` as the primary pointwise target, a separate forward-window
catalog/timing API, and named pre-window/post-anchor consumed fractions.
The pre-window boundary is not claimed as physical onset. Operational
missed-move/false-alert rates and fitting remain disabled. The strict
no-retrace rule is retained as a secondary diagnostic, not relaxed to improve
results. Claude's reviewed `d711832` baseline cutoff is incorporated only in
this versioned draft; its active review worktree is untouched.

All 130 targeted tests, formatting, guardrails, links and provenance checks
passed. Eleven historical hashes and the pinned Gemini export are unchanged.
Next: independent v2 review and freeze the event-association/exposure and
remaining study rules. The feed gate stays false; production/live rankings
are unchanged. The portable checkpoint records these states for another host.

## Gemini source access - 2026-10-30

Gemini returned a preliminary conceptual review while explicitly declaring
that none of the five repository sources were inspected. To unblock the
requested independent review, the complete pinned sources from `941f47a`
are exported into
`docs/research/review_packets/GEMINI_SOURCE_PACKET_941f47a.txt` with an
adjacent manifest. Every source section was verified byte-for-byte against
its committed Git blob. A convenience copy is in this PC's Downloads folder
as `Moonwalking-Gemini-941f47a.txt`; other machines can download the committed
packet. Upload that text file directly to Gemini, then request the same
review grounded in the attachment. Source-based review is still pending.

## Portable checkpoint - 2026-10-29

Start with [`docs/ai/RESUME_HERE.md`](docs/ai/RESUME_HERE.md) and
[`docs/ai/ACTIVE_WORK.json`](docs/ai/ACTIVE_WORK.json). These are the current
GitHub-backed record for this scoring lane: implementation commit, active
branch, owners/review status, next actions, constraints and evidence restore.
The latest audit raw evidence is backed up as a supplementary draft-release
asset; code/docs and both evidence manifests are in this branch. Older
MacBook-specific resume instructions below are historical checkpoints.

## Instant target implementation - 2026-10-29

Continue on `codex/instant-radar-20261028` from the independent local checkout
`C:\Users\tgpet\Projects\Moonwalking-InstantRadar`. The executable evaluation
contract, onset/forward labels, event deduplication and retrospective alert
timing are implemented in `scripts/scoring_experiment/instant_targets.py`.
Read [`docs/research/INSTANT_TARGET_LABELS_20261029.md`](docs/research/INSTANT_TARGET_LABELS_20261029.md)
and its versioned JSON contract. Synthetic paths test both directions,
horizons, gaps, future receipts/baselines, boundary trades, reversals, peak
ties, no-move rows and cost scenarios. This is a label implementation;
fitting, live-stage thresholds and recorder integration remain gated.

The audit controller completed its first independent hour (3600.156s) with
no transport errors and stopped. All sampled product intervals reconcile
against REST. BTC/SOL's 21776/2641 paired trades support ticker taker-side
semantics; ALCX/AURORA's 4/3 pairs remain insufficient. `hour_gate_pass` is
false. The replayed report and verified raw hashes are under
`docs/research/results/feed_audit_20261028_completed/`; raw packets remain
outside Git. No new audit was launched to shop for a passing complete sample.

Claude's separate checkout is `C:\Users\tgpet\Projects\Moonwalking-Claude`.
Ready-to-use Claude/Gemini/local-model assignments are in
[`docs/ai/INSTANT_RADAR_REVIEW_BRIEF_20261029.md`](docs/ai/INSTANT_RADAR_REVIEW_BRIEF_20261029.md).
Review the new target definitions before any prospective outcome fitting.
Historical validation stays locked; live scoring/production are unchanged.

Validation: all 104 targeted label/audit/campaign/historical-contract/driver/
restore/WS tests passed, as did formatting, repository guardrails, documentation
links and all 11 frozen historical artifact hashes. A bounded local 14B review
suggested two issues (missing boundary count and out-of-horizon peak); neither
was supported by the implementation or reproducing tests. Claude's independent
review remains pending.

## Continue Gemini's instant radar - 2026-10-28

The instant board was always intended to use a distinct formula from the
broader near/short/medium/long outlooks, sharing underlying market data.
The completed historical benchmark did not validate or reject Gemini's
prospective precursor design. Continue the existing proposal through
[`docs/research/INSTANT_RADAR_NEXT_STEPS_20261028.md`](docs/research/INSTANT_RADAR_NEXT_STEPS_20261028.md).

Both single-attempt feed audits failed on lost remote connections: October
27 after 2059.375s and October 28 after 936.89s. The root cause is not
established. A bounded controller, `scripts/run_feed_audit_campaign.py`, now
retries up to three independent captures without stitching time, preserving
each failure and stopping at the first completed sample even if inconclusive.
Its operational root is `%USERPROFILE%\.moonwalking\analysis\feed_audit_campaign_20261028`;
check `STATUS.json` and the attempt report before claiming a gate pass.
MacBook review is optional; no Mac worker has been launched. Next: finish the audit
and executable onset/target contract, then the 5s recorder and prospective
shadow evaluation under the existing gates. Historical validation stays locked.

## MacBook continuation - 2026-10-27

Use branch `codex/macbook-resume-20261027`. It combines both completed
research branches and carries the transfer instructions, environment pins
and evidence hashes. Start with
[`docs/ai/MACBOOK_HANDOFF_20261027.md`](docs/ai/MACBOOK_HANDOFF_20261027.md).
The historical comparison is complete and inconclusive. The prospective
capture disconnected after 34m19s and **did not pass** the one-hour gate.
All 44 combined research/audit/restore tests and repository guardrails pass.
The 14-file evidence bundle is hash verified and transferred via draft
GitHub release `research-handoff-20261027`; restore instructions and pins
are in the MacBook handoff. Native Mac verification remains to be run there.

## Live-movers comparison review - 2026-10-27

The main immediate-scoring task has resumed on
`codex/live-movers-driver-review-20261027`, based on Claude's driver commit
`0832f24`. Read
[`docs/research/LIVE_MOVERS_DRIVER_REVIEW_20261027.md`](docs/research/LIVE_MOVERS_DRIVER_REVIEW_20261027.md).
The review reproduced and fixed seed drift, artificial separation of tied
scores, a local-only repeat-test guard, and discovery compatibility that
incorrectly depended on docs-only commits. It also checks all six CSV
identity fields and exposes daily IC/attrition details. Frozen contracts,
features, splits and model forms are unchanged. No discovery/test analysis
was run during review. Verify passed from clean committed code at `7a55922`:
333,170 identities/timestamps/phases match; all three readiness gates pass.
Discovery then ran on clean commit `5db135a`; its choices were committed and
pushed at `9747f94` before the one-time validation. Both phases are complete.
The primary result is **inconclusive**: M1-B2 mean daily IC +0.01265, below
the required +0.02, with 3-day-block 95% interval [-0.00047,+0.02545]. The
primary top M1 score band has mean gross 5m return -0.03006% before costs.
Read [`docs/research/LIVE_MOVERS_RESULTS_20261027.md`](docs/research/LIVE_MOVERS_RESULTS_20261027.md).
No live weights/ranking change follows; do not rerun validation to tune it.
All 23 contract/driver/review tests, repository guardrails and diff checks pass.

The separate prospective diagnostic is implemented and pushed at `5e56095`
on `codex/live-movers-spec-corrections-20261027`. Its capture ran from
2026-10-27 09:06 to 09:40 UTC before losing the remote connection.
Its report is preserved in the MacBook evidence bundle; step 2.5 remains
incomplete. Start a new uninterrupted capture on the MacBook.

## Live-mover proposal corrections - 2026-10-27

Follow-up: `scripts/coinbase_feed_audit.py` now implements the standalone
diagnostic, with replayable raw evidence outside Git and conservative side /
coverage gates. Read
[`docs/research/COINBASE_FEED_AUDIT_20261027.md`](docs/research/COINBASE_FEED_AUDIT_20261027.md)
for commands, limits and short smoke findings. Fourteen targeted audit/WS
tests, formatting and guardrails pass. The committed-code run at `5e56095`
ended with a lost-connection error after 2059.375 seconds; the hour gate is
false. Its evidence originated at `%USERPROFILE%\.moonwalking\analysis\feed_audit_20261027_1h`.
The main scoring track has resumed on `codex/live-movers-driver-review-20261027`.
The earlier "No capture was run here" below describes the original
documentation-only checkpoint.

The original documentation checkpoint on
`codex/live-movers-spec-corrections-20261027` extended the research contract
at `a936dec5`. Read
[`docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md`](docs/research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md)
for the corrected prospective rules and checklist. The frozen historical
JSON contracts and comparison artifacts remain unchanged.

The next prospective deliverable is step 2.5: at least one hour of paired
Exchange ticker/matches/heartbeat evidence keyed by product and trade ID.
Match-side inversion is documented; ticker-side meaning still needs packet
verification. Matches can also drop, so heartbeat/REST reconciliation or
explicit incomplete coverage is required. The later interrupted capture
does not complete this gate.

The addendum chooses sparse buckets with read-time gap reconstruction,
per-row price-source/age flags, unnormalized decayed returns in each coin's
volatility units, and hard exclusion of `EXTENDED` moves from the early
board. It fixes 30s/180s windows before fitting and requires >=14 valid
shadow days with paired day-block uncertainty before a UI ranking change.
The collector, application code, historical data and visible ranking were
not changed. Board-retention deployment is still a separate runtime step.

Validation: Markdown links/formatting, numeric storage/decay/extension
examples, all 11 frozen artifact hashes, `git diff --check` and repository
guardrails passed. No application tests were needed for these Markdown edits.

## Always-on collector - 2026-10-12

Collection had silently stopped on 2026-10-05 11:22 because the backend only
ever ran inside a chat/agent session. It now runs as the `Moonwalking
Collector` scheduled task from the `Moonwalking-Runtime` worktree on port
5003, with every store in `%USERPROFILE%\.moonwalking\data` (consolidated
from the RiskBoard, Agents and Design worktrees with the SQLite backup API;
read-only copies of every original are in
`%USERPROFILE%\.moonwalking\archive\2026-10-12-worktree-stores`). Port 5003 is
no longer a dev port: don't kill it, run dev backends elsewhere. Details,
checks and update steps: `docs/developer/ALWAYS_ON_COLLECTOR.md`.

What the local data actually covers: about 1.6 of the 36 days from
2026-09-06 to 2026-10-12, in six short sessions. Production (bhabit.net, up
continuously since early September) has the rest: 965,580 signal outcomes
against ~24,000 locally. Its Scorecard's "2.89 days" is the span of the 5,000
most recent rows per board, not retention; board outcomes are kept 180
days, signal outcomes and dry runs indefinitely, on the Railway volume.
**Backing production up needs Tom's Railway login.**

Data integrity (branch `claude/data-integrity`, deployed to the collector):
outcome trackers used to grade checkpoints with prices from after a gap
(backend stopped or PC asleep). Fixed in `backend/outcome_gaps.py`: such rows
finish as `interrupted` and stay out of every rate. Rows already damaged in
the local store (984 signals finalized 1.8-11 days late; up to 1,224 board
rows open at a stop) are **not yet repaired**: deciding between marking them
interrupted and recomputing from the candle archive is Tom's call. The
sell-plan tracker hasn't had the same fix yet.

Raw Coinbase candles for missed periods are being archived to a separate
store (`docs/developer/CANDLE_ARCHIVE.md`). Open: production backup, local
repair, scheduled agent runs, Coinbase secrets on port 5003.

## P2.6 Portfolio Risk Board QA in progress - 2026-09-23

This section supersedes older P2.6 status below (including the "not
implemented" note under the 2026-09-06 integration checkpoint, which is
stale). P2.6 is implemented and in final QA, in this worktree, on branch
`codex/portfolio-risk-board` at `ff6d72d`.

There are uncommitted polish fixes (chart-expansion layout, page-width
overflow, missing-price label, mobile chip wrapping) sitting on top of
`ff6d72d` in:

- `frontend/src/components/PortfolioRiskBoard.jsx`
- `frontend/src/components/PortfolioRiskBoard.test.jsx`
- `frontend/src/styles/portfolio-risk-board.css`

Tom: these came from a Claude session and are still awaiting your
authenticated-portfolio login check below. **Don't point Codex (or a
fresh Claude session) at this worktree to commit, push, force-reset, or
re-edit those three files until you've done that check** — it would
either redo finished work or collide with it. Once you've confirmed and
either session has committed, remove this note.

Local dev servers were started via the gitignored `.claude/launch.json`:
backend on `http://localhost:5003`, frontend on `http://127.0.0.1:5173`.
`codex/portfolio-risk-board` is 14 commits ahead of
`codex/integrate-production` and 0 behind (clean fast-forward, no
conflicts expected) once this QA closes.

Verified already: guest/no-auth watchlist fallback, thin-history
unavailable cards, portfolio-unavailable-to-watchlist fallback (via a
mocked response), desktop/mobile layout at 1440/900/375px, the frontend
test suite (495 tests), the targeted backend risk tests (43 tests), and
the production build. Not yet verified: an authenticated session with a
real connected Coinbase portfolio at `/app/risk-board` — only Tom can do
that login. Once he confirms it and the three files above are committed,
next step is merging `codex/portfolio-risk-board` into
`codex/integrate-production`, then updating `MW_BACKLOG.md` (P2.6 to
Done) and this file.

The stale earlier note also pointed at
`C:\Users\tgpet\.codex\worktrees\moonwalking-integration` as a working
checkout for this task. That worktree is on `codex/integrate-production`
at `51c35fb1` and has no `PortfolioRiskBoard.jsx` at all — it predates
this implementation. Do not use it for P2.6 work.

## Local-only repository - 2026-09-06

Use `C:\Users\tgpet\Projects\Moonwalking` on this PC. It is an independent
repository with its own `.git` directory, not a linked worktree. Its remote is
`https://github.com/tgpetrie/moonwalking.git`; no Git object storage points into
OneDrive. Current sources are local; older historical file contents can be
fetched from GitHub on demand by the partial clone.

The integration commit `51c35fb1` and backlog source commit `ee0e4bf6` were
preserved through a verified Git bundle without pushing. Both source branches
are available here. The original OneDrive checkout and linked worktrees remain
intact for preservation; do not use them for further development or dependency
installation. Existing runtime databases, secrets, and dependencies were not
copied from OneDrive. This relocation did not migrate live application data.

Codex's saved Moonwalking project still points at the OneDrive folder and must
be reopened at this local path. Until then, explicitly use the local checkout
as the working directory for every tool command. The local-only storage rule
also appears in `AGENTS.md` to prevent creating another OneDrive-linked worktree.

## Integration checkpoint - 2026-09-06

This section supersedes older branch and production snapshots below.

Backlog follow-up: preserved the owner's P2.6 Portfolio Risk Board addition
as source-branch commit `ee0e4bf6` and merged it here. Corrected its description
of the existing popup integration and specified the dollar-risk calculation.
P2.6 remains Open; its batched route and portfolio grid are not implemented.
The unrelated `finish_claude_codex_merge.py` procedure has not been run or
authorized for application by this integration checkpoint.

- Local integration branch: `codex/integrate-production`.
- Combined `codex/scorecard-redesign-compare` at `ef83231e` and
  `codex/fix-responsive-ignition` at `76811a26` in a separate worktree.
- Preserved the scorecard redesign, password reset, local helper, sell-side risk
  levels and completed-candle chart, measurement gates, and all durable databases.
- Resolved five merge conflicts. Adapted the redesign to withheld statistics:
  missing rates remain unavailable, unmeasured categories cannot be ranked as
  dependable, and collection progress excludes older research outcomes.
- Fixed a Windows UTF-8 source-reading issue in the scanner-order tests.
- Frontend build and 482 tests pass; backend verification covers 546 runnable
  tests with 65 legacy/provider-dependent tests skipped. Guardrails, shell syntax,
  workflow YAML, and nine live production smoke probes pass.
- Replaced the obsolete Render/Vercel smoke workflow with Railway and Cloudflare
  checks. Run `python scripts/production_smoke.py` locally or dispatch the workflow
  after deployment. It checks current availability, not the deployed commit.
- This is a local checkpoint before pushing, as requested. No push, `main` merge,
  production deployment, or cloud setting change was made in this session.

### Verified production wiring

- GitHub: `https://github.com/tgpetrie/moonwalking`, remote `main` at `e629c22c`.
- Railway project: `bhabit-mooners` (`0613ba85-3821-4efc-b377-1a0354bbe406`).
- Production service: `85a66fda-a402-4f41-bac0-3b387bf76c9c`.
- GitHub source is already connected to `main`; automatic deployment is enabled.
  Wait for CI is currently off. The older "autodeploy unavailable" note is stale.
- Active deployment: `3957426c-901a-4613-bc2e-d30c91c3a68d`, labelled
  `deploy sell-side risk levels 6235e2d2`, deployed via CLI. Production is therefore
  ahead of `main`; redeploying the old `main` would remove newer features.
- Railway origin: `https://bhabit-mooners-production.up.railway.app` on port 8080.
- Both `bhabit.net` and `www.bhabit.net` are attached to this service and Railway
  detects Cloudflare proxying. Frontend, health, and board APIs return HTTP 200
  through the origin and both custom domains.
- One replica, attached volume, serverless disabled, Dockerfile builder, and
  `/api/health` deployment check are configured.
- Cloudflare dashboard requires sign-in; account-level DNS/TLS/cache settings
  have not been audited. Public DNS delegates to Cloudflare and HTTPS works.
- The Railway UI says existing `railway.json` configuration continues working
  until 2026-12-01. Plan its replacement before then; this merge does not change
  the running infrastructure.

Next: review the local combined branch, push it for review, integrate into `main`,
then verify Railway deploys that exact commit and rerun production smoke checks.
Do not redeploy the old `main` while this checkpoint remains local.

## Snapshot

- Date: 2026-07-20
- Branch: `main` at `478288ad` (all feature branches merged)
- Repository: `tgpetrie/moonwalking` on GitHub
- Product: BHABIT — personal crypto trading assistant dashboard at https://bhabit.net
- Owner: Tom (tgpetrie), solo operator. This is an information-only tool, NOT autonomous trading.

## Production

- **Live at https://bhabit.net** — Cloudflare DNS/TLS → Railway container
- **Deploy config**: `railway.json` (Dockerfile builder pointing at `backend/Dockerfile`)
- **GitHub repo connected** to Railway (`tgpetrie/moonwalking`, branch `main`). Auto-deploy shows "unavailable" — may need manual deploy trigger from Railway Deployments tab.
- **Health check**: `/api/health` with 300s timeout
- **Current deploy gap**: GitHub `main` has all features pushed (including Event Evolution, Portfolio Mode, notification priority). Production may still be running an older build — trigger a deploy from Railway dashboard to pick up new code.

## Architecture

```
Frontend (React/Vite)          Backend (Flask, single process)
  localhost:5173        →        localhost:5003
                                   ├── Coinbase WS ticker feed (live prices)
                                   ├── Alert engine (coin pressure detection)
                                   ├── Event Evolution (signal grouping)
                                   ├── Signal/Board outcome grading
                                   ├── Portfolio Mode (read-only Coinbase CDP)
                                   └── Notification dispatch (SMTP/Telegram/Discord)

Sentiment Service (FastAPI)
  localhost:8003         ←     proxied via Flask at /api/sentiment/*
```

### Key files and line counts

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app.py` | ~14,000 | Main Flask app — routes, background workers, data pipeline |
| `backend/alert_events.py` | 685 | Event Evolution: groups raw alerts → Signals with state transitions |
| `backend/signal_outcomes.py` | 309 | Tracks signal accuracy at 5m/15m/30m/60m checkpoints |
| `backend/board_outcomes.py` | 706 | Tracks mover-board accuracy with Wilson confidence intervals |
| `backend/portfolio_mode.py` | 699 | Read-only Coinbase CDP API client, permission enforcement |
| `backend/alert_delivery.py` | 273 | Notification dispatch (SMTP, Telegram, Discord, browser) |
| `backend/coinbase_ws.py` | 365 | WebSocket ticker feed with reconnect/backoff |
| `backend/alerts_engine.py` | ~150 | Raw coin pressure detection (feeds into Event Evolution) |
| `backend/watchlist.py` | ~900 | SQLite-backed user accounts, auth, session handling |
| `backend/sentiment_api.py` | ~570 | FastAPI sentiment service (Alternative.me + CoinGecko) |

### Frontend components (React/JSX)

- `DashboardShell.jsx` — main layout, tab routing
- `TokenRowUnified.jsx` — board row with pressure cues
- `AlertsTab.jsx` / `AlertsDock.jsx` — Signals/Pulse alert display
- `SentimentPopupAdvanced.jsx` — coin detail popup with Quick Buy Read
- `TopBannerScroll.jsx` / `VolumeBannerScroll.jsx` — scrolling ticker banners
- `AuthPanel.jsx` / `WatchlistPanel.jsx` — login/signup, watchlist management
- `PortfolioModePage.jsx` — portfolio holdings display (in `frontend/src/mvp/`)

## What's built and working

### 1. Live price board
Real-time crypto prices via Coinbase WebSocket feed (`coinbase_ws.py`). Falls back to REST polling for products without WS ticks. Board shows 1m/3m gainers/losers with pressure indicators.

### 2. Alert engine → Event Evolution pipeline
Raw alerts from `alerts_engine.py` (volume spikes, momentum shifts, divergences) feed into `alert_events.py` which groups them into per-coin **Events** with:
- State machine: `Building → Strengthening → Confirmed → Weakening → Fading`
- Confidence scores (0-100)
- Direction classification (up/down/neutral)
- "The Read" — human-readable interpretation (e.g., `BUY WATCH`, `TRAP RISK`, `NO CHASE`)
- Transition history with timestamps

### 3. Signal outcome tracking (PARTIALLY COMPLETE — see "What's next")
Two SQLite-backed stores run in parallel:

**SignalOutcomeStore** (`signal_outcomes.py`):
- Records entry price when a signal is created
- Measures directional returns at 5m, 15m, 30m, 60m
- Tracks max favorable and max adverse excursion
- Grades outcome as `followed_through` (hit +2% target before -1% stop) or `did_not_follow_through`
- `history_for(event)` returns historical win rate for same signal type+direction
- API: `/api/signals/outcomes/status`

**BoardOutcomeStore** (`board_outcomes.py`):
- Same checkpoint structure for mover-board entries
- Adds Wilson confidence intervals for small-sample stats
- Tracks by board type (ignition_1m, confirmation_3m_up, confirmation_3m_down)
- API: `/api/boards/outcomes/status`

**Both are wired into the main loop** at `app.py:13026` and `app.py:13127` — `observe()` is called every tick with current prices.

### 4. Portfolio Mode (read-only Coinbase integration)
- Coinbase CDP API with JWT auth (`portfolio_mode.py`)
- **Permission enforcement**: refuses keys with `can_trade` or `can_transfer` — view-only enforced in code
- Shows holdings, cost basis, allocation
- `get_held_symbols()` feeds into notification priority
- Needs 3 Railway env vars to activate: `COINBASE_API_KEY_NAME`, `COINBASE_API_KEY_SECRET`, `MW_PORTFOLIO_OWNER_TOKEN`

### 5. Portfolio-aware notification priority
- Coins you hold qualify for notifications at confidence 65+ (vs standard 85+)
- Implemented in `alert_events.py:notification_candidates()` and wired in `app.py`
- Tags elevated notifications with `priority: "holding"` and `notify_reason: "holding_priority"`
- 8 tests in `backend/tests/test_priority_notifications.py`

### 6. Coinbase OAuth integration
- Full OAuth 2.0 flow in `backend/coinbase_oauth.py` (250 lines)
- 4 routes in `app.py`: authorize, callback, disconnect, status
- CSRF state validation, token refresh with persistence to SQLite
- `portfolio_mode.py` tries OAuth first, falls back to env-var CDP keys
- Schema migration in `watchlist.py` adds token columns to users table
- For single-user: just set `COINBASE_PORTFOLIO_OWNER_EMAIL` env var (simpler path)

### 7. Position Intelligence
- `backend/position_intel.py` enriches portfolio with signal context
- API: `/api/portfolio/intel` — portfolio snapshot + per-holding signal data
- Per-holding: current signal state, posture (favorable/adverse/fading/developing), historical outcome stats
- Per-order: stop-loss/take-profit classification, distance from current, signal-aware context ("Signal weakening — consider tightening stop")
- Cross-references 29K+ graded outcomes from `signal_outcomes.py`
- 8 tests in `backend/tests/test_position_intel.py`
- **DECISION (2026-07-22): `/api/portfolio/intel` is intentionally env-var owner-only for now, NOT OAuth-aware.** Unlike `/api/portfolio` (which tries the user's OAuth token first), the intel route still gates on `COINBASE_PORTFOLIO_OWNER_EMAIL` and builds the client from static CDP keys. Rationale: no frontend consumes `/api/portfolio/intel` yet, so opening it to all OAuth users would be a speculative multi-user feature with no UI to validate against. Extending OAuth is a ~20-line refactor (lift the OAuth-lookup block from `portfolio_snapshot()` into a shared helper both routes call) — defer it to whenever the intel UI is actually built, and wire both in one stroke.

### 8. Notification delivery channels
`alert_delivery.py` supports SMTP email, Telegram bot, Discord webhook, and browser push. Per-symbol cooldowns and hourly caps. All channels disabled until credentials are set.

### 9. Cross-device watchlist with auth
SQLite-backed accounts (`watchlist.py`), session cookies (HttpOnly/Secure/SameSite), CORS with credentials. Guest watchlist migrates to account on signup.

## What's NOT built yet (the gaps)

### A. Outcome scorecard UI (HIGH PRIORITY)
The outcome data is **collecting in SQLite** but there's **no dashboard to view it**. Need:
- Aggregate accuracy panel: "Bullish Breakout signals followed through 62% over 200 samples"
- Per-signal-type breakdown with win rates, median favorable/adverse moves
- Time-series view showing whether accuracy is improving or degrading
- Per-coin history (currently `history_for()` groups by type+direction, not by individual coin)

### B. Feedback loop to auto-tune thresholds
Outcome data doesn't feed back to adjust:
- Confidence thresholds for notifications (hardcoded 85% standard, 65% held)
- Alert engine sensitivity parameters
- Which signal types should even generate notifications vs just log

### C. Notification outcome tracking
Signals are graded, but there's no separate tracking of "did notifications I *received* lead to useful action?" — the ultimate quality metric for the trading assistant use case.

### D. Notification channel activation
SMTP, Telegram, Discord, browser push are coded but need credentials configured:
- `MW_SMTP_HOST`, `MW_SMTP_USER`, `MW_SMTP_PASS`, `MW_NOTIFY_EMAIL_TO`
- `MW_TELEGRAM_BOT_TOKEN`, `MW_TELEGRAM_CHAT_ID`
- `MW_DISCORD_WEBHOOK_URL`

### E. Portfolio Mode activation
Needs Coinbase CDP API key (view-only!) created at https://portal.cdp.coinbase.com and set in Railway:
- `COINBASE_API_KEY_NAME`
- `COINBASE_API_KEY_SECRET`
- `MW_PORTFOLIO_OWNER_TOKEN` (any secret string, used to gate the endpoint)

### F. Production deploy verification
GitHub→Railway connection is set up but auto-deploy shows "unavailable". Current production may be running old code. Need to:
1. Trigger manual deploy from Railway Deployments tab
2. Verify `/api/alerts/recent` returns `signals` and `pulse` fields
3. Verify `/api/signals/outcomes/status` is reachable
4. Verify `/api/boards/outcomes/status` is reachable

## Environment variables (production)

Required:
- `SECRET_KEY` — session encryption (Railway generateValue handles this)
- `FLASK_ENV=production`
- `SESSION_COOKIE_SECURE=1`
- `CORS_ORIGINS=https://bhabit.net`
- `SERVE_FRONTEND_DIST=1` — serves built frontend from Flask

Optional (enable features):
- `ENABLE_COINBASE_WS=1` (default on) — live WebSocket prices
- `COINBASE_API_KEY_NAME` / `COINBASE_API_KEY_SECRET` — portfolio mode
- `MW_PORTFOLIO_OWNER_TOKEN` — gates portfolio API access
- `MW_SMTP_*` / `MW_TELEGRAM_*` / `MW_DISCORD_*` — notification channels
- `WATCHLIST_DB_PATH` — SQLite location (Railway persistent disk)
- `MW_SIGNAL_OUTCOMES_DB` / `MW_BOARD_OUTCOMES_DB` — outcome store location

## Local development

```bash
./start_app.sh          # starts Flask (5003) + sentiment (8003) + Vite (5173)
# OR
./dev.sh                # alternative dev script
```

### Tests
```bash
.venv/bin/python -m pytest -q backend/tests    # ~52 pass, 65 legacy skipped
cd frontend && npm run verify                  # 26 frontend tests
```

### Pre-commit hooks
- `black` (Python formatting) — auto-fixes, re-stage and retry
- `trailing-whitespace`, `end-of-file-fixer` — same pattern
- `detect-secrets` — use `# pragma: allowlist secret` for test fixtures
- `eslint` — **BROKEN** (ESLint 10 needs flat config, repo has none). Use `SKIP=eslint git commit` for all commits.

### Runtime gotcha: `cdp-sdk` must be installed in the interpreter the server actually runs (2026-07-22)

**Symptom:** `/api/portfolio` and `/api/portfolio/intel` return 503
`"Coinbase authentication support is not installed on this server."`
(`PortfolioDependencyMissing`, raised in `portfolio_mode.CoinbaseAdvancedTradeClient._jwt`).

**Cause:** the JWT signer does a lazy `from cdp.auth.utils.jwt import JwtOptions, generate_jwt`.
`cdp-sdk>=1.28,<2` is in `requirements.txt`, but on 2026-07-22 the running Flask
process was launched with **system Python 3.13** (`/Library/Frameworks/Python.framework/...`),
not the project `.venv` (3.12) — and neither interpreter had `cdp-sdk` installed. Result:
owner is authenticated, keys are loaded, but every Coinbase call fails at import.

**Fix (no restart needed):** the import is lazy, so installing into the *running*
interpreter is picked up on the next request without losing in-memory keys:
`<that-interpreter>/python3 -m pip install 'cdp-sdk>=1.28,<2'`.
Cleaner long-term: install `requirements.txt` into the `.venv` and launch the server
from it (`start_app.sh`) so the interpreter is deterministic.

**Watch out:** `cdp-sdk` pulls heavy deps (web3, solana, eth-*) and bumps `pydantic`
to 2.13.x, which conflicts with `gradio` (`<2.12`). Installing into a **venv** (not the
global framework Python) avoids polluting other tools; pin `pydantic` if gradio is needed.

## Dependencies

Python: Flask 3.1, flask-cors, flask-socketio, gunicorn, requests, websocket-client, cdp-sdk, FastAPI, uvicorn, sentry-sdk, numpy, pandas, feedparser, vaderSentiment, transformers, torch, PyYAML, beautifulsoup4, redis (Phase 3 cache, not active)

Frontend: React, Vite, standard JS toolchain

## Git branch state

All feature work is merged to `main`. Legacy branches exist but are stale:
- `codex/event-evolution` — merged to main
- `codex/portfolio-mode` — merged to main
- `codex/ai-ml-next-step-plan` — older planning branch
- `collab/claude-codex-coin-pressure-20260714` — earlier pressure work

## Session 2026-07-22 (part 2): three Portfolio-card threads shipped

All three are code-complete + unit-tested (backend 150 pass, frontend 48 pass); **not yet live-verified in a browser** (intel endpoint needs the owner-auth + CDP chain up). Nothing pushed.

1. **Confidence tiers** — the binary "not enough proof" gates are gone. `describeEvidenceTier(sampleSize)` in `portfolioSignals.js` grades comparable-outcome history into a ladder: None → Emerging (1–9, rate not quoted) → Building (10–29) → Solid (30–99) → Strong (100+). Used on the intel history line, the "Historical plan" cell, the plan-lock banner, and the page-footer calibration section (graded on `outcome_db_size`). Thresholds live in `EVIDENCE_TIERS` — tune there.
2. **Cost-basis entry** — unlocks P&L on partial/unavailable holdings. Storage: `manual_cost_basis` table + `set/get/delete_manual_cost_basis()` in `watchlist.py`. Overlay: `portfolio_mode.apply_manual_cost_basis()` (pure) blends known fills + manual avg for the unknown qty (status→`blended`) or defines the whole position (status→`manual`); **`complete` fills are never overwritten**; recomputes summary P&L + coverage. Owner-gated write routes `POST/DELETE /api/portfolio/cost-basis`. UI: `CostBasisEntry` inline form on each partial/unavailable card. Overlay is applied in the intel route before enrich.
3. **Descriptive levels (targets/protection, not-yet-outcome-validated)** — `position_levels.compute_levels()` (pure) derives swing support/resistance, an ATR(14) band, range position, volatility, 1h momentum, and volume trend from public Coinbase candles (`_fetch_coinbase_candles`, no auth). Route helper `_gather_levels_for_symbols()` caches raw candles per product (TTL `MW_LEVELS_CANDLE_TTL_S`=300s, 1h granularity ×50), fetches on demand with bounded concurrency (6 workers), capped `MW_LEVELS_FETCH_PER_REQUEST`=30/request so a big portfolio warms progressively. Attached as `holding["levels"]`; enriches the descriptive read with a range phrase. UI: `HoldingLevels` block with an S↔R track + marker, labeled "not yet outcome-validated", replacing the old hard plan-lock.

New tests: `test_manual_cost_basis.py` (8), `test_position_levels.py` (9), +4 in `test_position_intel.py`, +cost-basis/levels/tier cases in the frontend suite.

## Session 2026-08-11: Posture fix + per-coin history WIP

### What shipped (committed + ready to push)

Two commits on `main`, not yet pushed to remote:

| Hash | Subject |
|---|---|
| `5acf4f89` | fix(alerts): make early posture risk-aware |
| `9bd2acfb` | fix(posture): hoist nowMs declaration above signalFlags useMemo |

**What the posture fix does** (`SentimentPopupAdvanced.jsx` + new `coinPosture.test.js`):
- Replaced age-blind inline `signalFlags` object with `computeSignalFlags(coinAlerts, nowMs)` — freshness-gated: reversal/fakeout/exhaustion only count while the alert is still active (< 5 min or `expires_at` not yet passed)
- Removed `signalFlags.hasExhaustion` from `hardRisk` veto — exhaustion is caution, not a hard stop; it still surfaces in WHAT BLOCKS IT via `computeRiskBlocker`
- Made Event Evolution "Reversal Risk" currentness-aware: `isReversalRiskCurrent(coinPriorityEntry)` checks `noConfirmMs < PRIORITY_FADING_MS` (3.5 min) instead of checking `stateLabel === 'Reversal Risk'` blindly (which was circular — stale entries push the score up, triggering the label, then the label vetoed new setups)
- Added `EARLY SETUP` posture state between WAIT and WATCH CLOSE: `score >= 55 && shortTermUp (1m > 0 && 3m > 0) && volumeConfirms && breakoutUp && !hardRisk` — 1h alignment NOT required
- Relabeled `BULL` → `TAPE UP`, `BEAR` → `TAPE DOWN`; "Fast tape is pushing up." → "Short-term tape is pushing up."
- Score/rank display: `#X of Y · S/100` → `Tape rank #X/Y · Tape strength S/100`
- **TDZ fix** (second commit): `const nowMs = Date.now()` was declared 190 lines after the `signalFlags` useMemo that referenced it in its dependency array. Moving it above the useMemo was required — the app crashed on every popup open before this fix.
- 51 tests in `frontend/src/components/coinPosture.test.js` cover all 5 exported pure functions

**Verified live in browser**: WAIT posture (high score but alignment missing), STAY CLEAR (score < 42), TAPE UP label, TAPE RANK/STRENGTH format, zero React console errors.

### What's paused (WIP draft commit — NOT ready to deploy)

The per-coin outcome history feature is committed as a **draft/WIP** (`wip(coin-history): per-coin outcome history — paused, do not deploy`).

**To resume on a new machine:**
```bash
git pull
git reset HEAD~1   # un-commits the WIP, restores it as unstaged changes
                   # do NOT git reset --hard (that would discard the WIP)
```

After `reset`, `git status` should show the same unstaged+untracked state as before:
```
 M backend/app.py
 M backend/signal_outcomes.py
 M backend/tests/test_scorecard.py
 M frontend/src/components/SentimentPopupAdvanced.jsx
 M frontend/src/styles/sentiment-popup-advanced.css
?? backend/tests/test_coin_history_route.py
?? frontend/src/components/SentimentPopupAdvanced.test.jsx
```

**What the WIP contains:**

*Backend (all in `backend/`)*:
- `signal_outcomes.py` — extracted `_med()`, `_build_signal_card()`, `_cards_from_rows()` as static methods; added `coin_scorecard(product_id)` using shared `_cards_from_rows()`; added `ix_signal_outcomes_product (product_id, complete)` index in `ensure_db()`
- `app.py` — added `GET /api/coin-history/<product_id>` route; normalizes bare symbols (BTC → BTC-USD)
- `tests/test_scorecard.py` — 5 new `coin_scorecard` tests
- `tests/test_coin_history_route.py` (untracked) — 4 route tests: live status, bare symbol normalization, no history, degraded on exception

*Frontend (all in `frontend/src/`)*:
- `components/SentimentPopupAdvanced.jsx` — `CoinOutcomeHistoryCard`, `CoinOutcomeHistory` exported component, `coinHistory`/`coinHistoryLoading`/`coinHistoryError` useState, `useEffect` for `/api/coin-history/` fetch, `<CoinOutcomeHistory>` render, `import { describeEvidenceTier }`
- `styles/sentiment-popup-advanced.css` — `.coh-*` CSS block for `CoinOutcomeHistory`
- `components/SentimentPopupAdvanced.test.jsx` (untracked) — 19 tests for `CoinOutcomeHistory` exported component

**IMPORTANT — UX spec changed** since the test file was written. The tests in `SentimentPopupAdvanced.test.jsx` still reference `describeEvidenceTier` tier label strings (Strong/Solid/Building/Emerging). The actual spec is:
- **≥ 20 outcomes**: show count + follow-through rate (e.g., `"150 comparable outcomes"` + `"21% followed through"`)
- **< 20 outcomes**: show count + `"Not enough history for a measured rate"`
- **No history**: `"No comparable historical outcomes yet."`
- **No tier labels shown in the popup** (tier labels are used internally in the card component but not as primary display)

The test file needs to be updated to match this spec before staging and committing the WIP.

### Constraints that must survive the handoff

- Do NOT push to production without the Railway deploy being intentional (Railway auto-deploy is "unavailable")
- `alignedDown` magnitude sensitivity — deferred, do NOT implement without explicit user instruction
- Do NOT redesign the posture ladder further; do NOT introduce portfolio language like PROTECT GAIN
- ESLint pre-commit hook is broken — always use `SKIP=eslint git commit` for all commits

## Recommended next actions (priority order)

1. **Build the outcome scorecard UI** — 29K+ graded signals in SQLite, surface accuracy stats per signal type so Tom can see which alerts are actually predictive
2. **~~Wire position intelligence into the Portfolio UI~~ — DONE (2026-07-22)** — `PortfolioModePage` now fetches `/api/portfolio/intel` (progressive enhancement: falls back to `/api/portfolio` on 403/503), renders posture chip + board momentum + historical follow-through per holding, context rows under open orders, and a signal-coverage chip. Live-verified against real data (81 holdings, e.g. ARX "Pressure adverse · 78"). ~~NEXT: raise coverage~~ — **DONE (2026-07-22)**: `position_intel._descriptive_read()` now derives a plain-language 24h read (bands: <2% "Quiet today", 2–8% "Up/Down today", >8% "Up/Down big today") from `price_change_24h_pct` for any held symbol without a live Event Evolution signal, so all 81 cards show content. Reads are marked `read_source="descriptive"` and rendered with a dashed "24h price read" tag so they're visibly distinct from real signals. **Signal coverage stat stays pure** (counts only `read_source=="signal"`, ~9/81); a separate `read_coverage_pct` (~100%) is shown alongside. 8 new backend tests + 1 frontend test. NOTE: not yet live-verified in a running browser — the intel endpoint needs the owner-auth + CDP chain up; logic and render are unit-test-verified.
3. **Add v2 API cost basis fallback** — CDP keys may support `/v2/accounts/{id}/transactions` for buy history on coins without Advanced Trade fills (most of Tom's 81 holdings show "partial cost basis")
4. **Set up Telegram bot** for notification delivery (simplest channel to activate)
5. **Add per-coin outcome history** to `history_for()` so accuracy can be assessed per-asset
6. **Build feedback loop** — use accumulated outcome data to auto-tune notification thresholds

## Session 2026-08-29: sell-side intelligence + risk-level history

Current branch: `feat/feature-retention-snapshots`, three commits ahead of its
remote. The work immediately before this session was the signal-history
truthfulness pass (`7a03f914`, `a3546905`, `65146cea`): uncontrolled signal
rates are withheld, the UI says it is collecting, and the control dry-run data
now persists on Railway.

This session adds an uncommitted, tested vertical slice for sell-side decision
support:

- `backend/sell_side_intelligence.py` builds `sell_levels_v1` from the existing
  50-hour Coinbase candle structure. It separates a stop trigger from the
  lower sell-limit price, explains the ATR/support buffer, identifies the first
  resistance/trim area, shows a support/re-entry-watch zone, and combines range
  position, momentum, volume, and canonical reversal/fading context into a
  clearly labeled top-risk state. It never places an order.
- `backend/sell_plan_outcomes.py` records at most one displayed plan per
  product/hour and observes whether the target, stop, or neither is reached
  first within 24 hours. The API/UI shows raw counts; `target_first_rate` stays
  null because no controlled predictive methodology exists yet.
- `GET /api/risk-levels/<symbol>` returns the current plan and that coin's plan
  history. `GET /api/risk-levels/status` exposes ledger health. The live price
  loop grades open plans without being allowed to interrupt the canonical
  price-tape persistence path.
- `SentimentPopupAdvanced` has a prominent compact sell-side block on the Coin
  tab and a dedicated `Risk Levels` tab with stop trigger, sell limit,
  invalidation, trim area, support zone, reasons, execution-risk disclosure,
  and recorded outcomes.
- Railway's entrypoint persists the new ledger through
  `MW_SELL_PLAN_OUTCOMES_DB` on the mounted data volume.

Verification: 69 focused backend tests passed, including route integration and
existing scorecard/portfolio regressions. Frontend production build passed and
all 413 frontend tests passed. The feature has not yet been visually checked in
a running browser or deployed to production.

For resuming this exact work on the owner's Windows AI PC—including the
read-only boundary, formulas, coverage limits, PowerShell/WSL setup, and transfer
state—read `WINDOWS_AI_PC_HANDOFF.md` next.
