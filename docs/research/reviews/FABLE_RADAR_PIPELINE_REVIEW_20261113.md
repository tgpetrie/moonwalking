# Instant Radar pipeline review: receipt to outcome (Claude Fable, November 13–14, 2026)

Codex integration note: the accepted snapshot field is `recv_returned_empty`.
An empty return also fits a zero-length data frame. Healthy local samples
leave the cause of EOF unresolved, and an uncorrelated reset or abort does
not identify the origin. The protocol below preserves Fable's proposal.

**Scope.** This review follows a decision through the pipeline: receipt, causal decision, local publication and later outcome. It also covers the November 11 Asia transport loss. It was done against pin `257be69e6058cd2addc04dc1c191d7cdf3b25c4e` on `claude/instant-radar-pipeline-review-20261113`, in the prepared Windows worktree. Reader runtime `cfa4aff` and offline verification `975234e` are the baselines named in the assignment. The accepted V2, offline, coverage, book/publication, reconciliation, association, directional and input-evidence reviews are treated as settled. This review does not repeat them. It tests where their stages join.

**Result in one paragraph.** I found two small correctness defects in the research pilot and verifier and fixed both. Each was reproduced on unmodified code first. One is a latent same-millisecond freeze race that would make an entire attempt unreportable. The other makes the verifier crash on a torn final observer line. Neither changes any recorded result: the preserved Asia attempt re-verifies identically. I also added reader-side transport-failure instrumentation, which is the evidence the last attempt lacked. From the preserved Asia journal I could bracket the failure: the reader failed between 0 and about 582 ms after the last frame. The error text, read against the pinned library, identifies a zero-byte read: a TCP FIN or TLS end-of-stream. It was not a reset, not a local abort, not a WebSocket close frame and not queue pressure. The Windows VPN-adapter disconnect at +102 ms falls inside that bracket. That supports a local network transition but does not prove it. The bridge from a delayed decision to the accepted directional and association reporters is still missing. That gap is a design and policy question, not a code defect. Nothing here measures public delivery, grades a real outcome or supports fitting.

## What I could read and run

- **Packet.** SHA-256 `c1cebf9f…5f97`, 924,385 bytes, matching the manifest. All **111** source bodies match their Git blobs at `257be69`, by object ID, byte length, SHA-256 and packet byte offset (script output: `mismatches: []`). Pinned assignment doc: `docs/ai/FABLE_RADAR_PIPELINE_ASSIGNMENT_20261113.md` is on `codex/instant-radar-research-restart-20261113`, not in the pinned tree. I worked from the pasted copy.
- **Checkout.** `git fetch --prune` was clean. The remote is `tgpetrie/moonwalking`. The branch tracked `origin/claude/instant-radar-pipeline-review-20261113` at exactly `257be69`, with a clean status. Toplevel and common Git dir are both under `C:/Users/tgpet/Projects` (outside OneDrive). The sparse checkout (`backend docs frontend/src scripts tests`) was preserved, and the Windows-invalid tracked image stayed skipped.
- **Runtime.** Windows 11, Python 3.12.10, pytest 8.3.5, SQLite 3.49.1, websocket-client 1.9.0 (`Projects/Moonwalking/.venv`). Black 24.8.0 ran from `~/.moonwalking/venv`.
- **Baseline.** `python -m pytest -q tests/test_instant*.py` → **1,253 passed** at the pin. This reproduces the stated prior result on Windows.
- **Preserved Asia attempt.** I read it **read-only** on this PC, at `~/.moonwalking/analysis/instant_reader_overflow_20261110/asia-20261110-162344`. The journal was opened with `mode=ro&immutable=1`. The SHA-256 of the journal, PLAN and REPORT were identical before and after (`592cf1b4…`). Only timing fields, message types and product IDs were read. No payload values, network identities or event logs were read.
- **Not available or not done.** I did not see the raw Windows NetworkProfile and System events or Codex's private evidence folder; I used only the sanitized November 13 summary. The US journal and its failure-time detail are not available. No capture, network request, authenticated call, system, VPN or event-log change, fit, tuning or historical validation took place.

## Findings, by severity

### F1 — Medium (latent, confirmed, fixed): a cohort could freeze while its as-of millisecond was still open

**Path.** `instant_real_indexed_pilot.DiagnosticCohorts.after_commit` froze decisions once `utc_ms() >= asof`. Evidence views are inclusive: `EvidenceIndex.prefix_at` and every `_before/_span` uses `available_ts_ms <= asof`. A packet's `available_ts_ms` is `max(processing_completed, receipt+1)`. So a frame the reader stamped before the as-of, but which the owner finished while the wall clock still read the as-of millisecond, joins the as-of view *after* the decision was frozen. The core APIs accept the same open view, because `build_timed_baseline` only rejects `asof > now`.

**Minimal reproducers (unmodified pin)**, kept in the scratchpad and encoded as probes:

| Case | Observed before the fix |
| --- | --- |
| A1: recorder, decision at clock == as-of, then a queued frame stamped 29,900 completes at 31,500 | Prefix count 73 → 74, digest changed, cutoff quote bid `99` → `109`, `observe_publication` raised `decision and recorder evidence prefix differ` |
| A2: journal + offline verifier, same shape | `verify()` raised `decision prefix differs from the journal`. The whole attempt is unverifiable, not just one row |
| A3: actual `DiagnosticCohorts.after_commit` | 12 rows frozen at clock == as-of; the same-millisecond frame then gets `available == asof`; `_timing_readiness` raised `decision and recorder evidence prefix differ`, so `main()` would stop before writing `REPORT.json` |

**Reachability, stated plainly.** In the live pilot the owner is single-threaded. No frame is ingested during a cohort, and a cohort takes hundreds of milliseconds (decision preparation p95 was 70 ms per row in the November 8 run). So the race needs the entire cohort to finish inside one wall-clock millisecond. That is not reachable at the measured speeds. On this PC, Python's wall clock advances in about 1 ms steps (2,104 distinct readings in 2 s; median step 1.0 ms; resolution reported as 15.6 ms). The real risk is in other callers and in faster future code, and the cost is all-or-nothing: the report and verification fail for the whole attempt. That justifies the fix.

**Fix (smallest).** In `after_commit`, `if now < asof: return` becomes `if now <= asof: return`. Freezing waits until the as-of millisecond has closed. That costs at most 1 ms and needs no clock, schedule or contract change. One existing assertion in `test_staggered_cohorts_use_their_own_asof_and_actual_observer_clock` now advances the synthetic clock to `as-of + 1`. **After:** `test_cohort_waits_until_its_asof_has_closed_before_freezing` passes. No rows are frozen at the as-of. The same-millisecond frame enters the prefix (count 2), the rows freeze at `as-of + 1`, and `_timing_readiness` completes.

**Not changed (policy for Codex).** `prepare_decision`, `build_timed_baseline`, `grade_publication`, `assess_cohort` and `component_evidence` still accept `asof == now`. Requiring `asof < now` in the library would change hashed module sources, so it should be a separately versioned decision. The new limitation probe records the open-view behavior.

### F2 — Medium-low (confirmed, fixed): a torn final observer line made the whole attempt unverifiable

**Path.** `verify_instant_timing_attempt.verify` parsed every `observed.jsonl` line with `json.loads`. The observer appends and flushes one line per receipt. `DiagnosticCohorts.stop_observer` calls `terminate()` (Windows TerminateProcess) if the observer has not exited 6 s after the stop file appears. A crash or power loss can also cut the last append short. The in-process `_observation_report` already counts unreadable lines as discrepancies, so the two consumers of the same file disagreed.

**Before (unmodified pin):** with one valid receipt plus a partial second line, `verify()` raised `JSONDecodeError: Unterminated string starting at: line 1 column 26`. No result was produced. **Fix:** the verifier tolerates only an unterminated final line, meaning an interrupted append, and counts it as `torn_final_observation_lines`. That row stays in the denominator as unobserved. Any other unreadable line is an explicit `ValueError("unreadable local observation at line N")`. **After:** `torn_final_observation_lines == 1`, `local_observations_verified == 1`, and the slow arm shows `observed: 0` with its row still planned. A damaged complete line still fails. **Real-data regression:** re-verifying the preserved Asia attempt with the patched verifier gives every committed `ASIA_01_VERIFIED.json` field identical, plus the new field at 0. Input hashes were unchanged.

### F3 — Diagnostic gap (instrumented, not a defect): no failure-time context for ordinary transport loss

At `cfa4aff`, only overflow produced a frozen snapshot. A transport exception kept only `str(exc)` in `REPORT.json -> attempts[i].error`. There was no exception class, errno or winerror, no reader detection time, no queue or writer state and no stderr record. The journal barrier is the owner's later observation. **Added (additive, offline-tested):** `QueuedSocket` now freezes one `instant-reader-transport-v1` snapshot when it detects transport loss. This happens before the failure flag is set and before draining. It covers both an exception and an empty return, and is skipped when the reader is stopping or has overflowed. Fields:

- reader `detected_ts_ms` (UTC) and `detected_monotonic_ns` (same `perf_counter` clock as frame `receipt_ns`)
- `last_return_age_ms`, and `timeouts_since_last_return`, which counts the 1 s socket timeouts since data last arrived
- queue capacity, depth and oldest queued age; received and delivered counts; the 100 ms and 1 s return windows (shared with the overflow snapshot)
- active writer phase and elapsed time, and the last completed writer phase
- up to four links of the exception/cause chain, each with qualified type, `errno`, `winerror` and a message truncated to 200 characters
- `close_frame_returned`, plus an explicit `close_status: null` with `close_status_reason: "not_exposed_by_websocket_recv"`

The snapshot is emitted once to stderr as `READER_TRANSPORT {json}` and stored at `REPORT.json -> reader[i].transport`. No limits, stops, reconnect behavior, journal schema or hashed evidence modules changed. The pilot module is not in the journal's provenance hashes. The accepted disconnect probe's assertions that the transport field was absent and stderr empty now assert the snapshot instead. Its prefix, barrier and integrity assertions are unchanged. Before the change, each of the seven new transport probes failed with `KeyError: 'transport'`.

### Limitations and policy decisions (behavior verified, not defects)

1. **Per-feature readiness can describe a book the reader had already superseded.** A newer pre-cutoff book update was stamped at cutoff −4 s but was still queued at an early as-of. At that as-of, F1, F4, F5 and the anchor quote are `ready` on the *older* book: 9 s old, bid 100, versus 4 s old, bid 109 at the final as-of. F1 even changes sign (≈ −2.35 → +6.16). F3 is also `ready`. Nothing records that received input was still unprocessed. **The complete vector held:** F2's cutoff-closing trade proof needs a post-cutoff heartbeat. Ingestion is FIFO, so that proof cannot be known before the earlier queued frames are processed. `complete_vector_candidate` was `False` early and `True` at the final as-of. This is causal; no later data leaks in. But per-feature readiness counts are not comparable across queue lag. *Policy:* record the reader's queued-not-processed count and oldest queued receipt with each frozen cohort. Alternatively, define feature readiness to require that product's cutoff-closing heartbeat.
2. **Waiting versus permanently ungradable is indistinguishable.** At `asof == end` (proof not yet arrived), and 10 minutes after a mid-horizon continuity break, the grade is the same: `unavailable / trade_coverage_not_yet_proven / outcome_trade_window`. A caller cannot tell when to stop re-grading. Neither case becomes a negative or edits the row; that held. *Policy:* add a declared proof grace after horizon end, after which a missing proof becomes final with its epoch-break reason.
3. **Outcomes are anchored to the decision cutoff, not to the publication price.** A row first observed after its whole favorable move still grades `cutoff_verified_forward: True`. A row published after its horizon ended still grades `ready`. `publication_before_horizon_end: False` is its only flag. Both behaviors are correct for the declared `offline_cutoff_outcome_diagnostic` scope. A hypothetical action at a post-publication price needs its own versioned grade. It must not be read from this one.
4. **No executable bridge from a delayed decision to the accepted reporters.** A grade row lacks six association label keys (`anchor_ts_ms`, `contract_sha256`, `contract_version`, `evaluator_sha256`, `label_maturity_ts_ms`, `verified_forward`), so `association_report` raises `malformed label row`. Directional exposure requires `available_ts_ms <= ts_ms`, so it rejects every delayed eligibility row, which by design becomes known at +1.5 s or +5 s, with `eligibility must be known by its cutoff`. Per-board exposure therefore cannot yet be computed for the pipeline under study. *Policy:* define a versioned adapter that maps grade to label, and define whether exposure counts eligibility "known by cutoff + declared wait". Keep pointwise grades separate from retrospective association.
5. **The timing pilot cannot mature any outcome from its own journal.** Across 60 s of acknowledgment phases, the first cutoff sits 62:00–62:05 after acknowledgment. The earliest baseline input stays at least 20 s after acknowledgment, the last cohort as-of leaves at least 95 s before the 67-minute deadline, and the observer outlives the last as-of by 40 s. Those anchors held. But every first-cutoff 300 s horizon ends at or after the capture deadline. That is consistent with an outcome-blind pilot. Any grading study needs a longer capture.
6. **A backward wall-clock step ends the attempt.** `InputEvidenceRecorder._now` raises `processing clock regressed` and sets `failed` on even a 1 ms regression. Verified: `recorder.failed: True`. This fails closed, which is correct. But a Windows time-service step during 67 minutes would surface as `journal_failure`, so time-service events belong in the next run's evidence.
7. **Observer liveness is not recorded.** Rows committed after the observer exits are correctly retained as unobserved. But `observed.jsonl` has no start, heartbeat or stop record. An expired observer and a slow consumer therefore leave the same missing row; only the report's `process_exit_code` exists.
8. **Local observation is not public delivery.** The verifier binds the following:
   - the decision digest ↔ the journal row ↔ the observation
   - `commit_observed_ts_ms` ↔ the journal
   - `consumer_seen ≥ commit`
   - one row per slot, with `asof == cutoff + scheduled offset`
   - `asof ≤ feature completion ≤ decision completion ≤ commit requested`
   - each frozen prefix, rebuilt from the journal

   It does not bind any independent clock: the consumer uses the same host wall clock. It also does not bind the consumer's process identity or liveness, or anything after local SQLite visibility. `observe_publication`'s `published` remains a caller assertion, and `durable_publication_verified` is always `False`. The gap to public delivery is the entire network and recipient path.

## Controls that held (new probes, unmodified implementation)

- An in-flight 16-frame batch stamped before the as-of but processed after it stays outside the frozen prefix (`known_packet_count` 2), and the verifier rebuilds the same prefix.
- Missing slots are kept in both directions. Planned-but-never-journaled rows and journaled-but-unreported rows (`journal_only_publications`) remain in per-arm denominators. Report-only phantom rows, unscheduled cutoffs and rows on the wrong arm are rejected.
- Orphan, duplicate, wrong-decision, wrong-commit-clock and unreported-consumer-clock receipts are rejected. The consumer deadline is inclusive (2,500 within, 2,501 after). Late rows stay in denominators.
- Grading moves from `pending` (end −1) through `unavailable` (end, proof outstanding) to `ready` (end +1). It is graded in the row's own direction (up `True`, down `False` on the same path). A flat path is a valid negative `False` on both boards. Decision digest, publication ID and cutoff are preserved across every grade. A continuity break *after* the horizon does not invalidate a matured outcome; only the grading prefix digest changes.

## Asia transport loss: what the saved evidence can and cannot distinguish

**Timeline (read-only from the preserved journal; offsets are relative to the last reader receipt, 01:03:48.291 UTC).**

- All six products sent heartbeats at −141 ms. The next would have been due around +859 ms and never arrived.
- The last four frames (BTC match and ticker, SOL and AVAX l2update) share receipt +0. Their processing finished by +32 ms, and the queue was empty after them.
- Across the final 40 frames, receipt-to-processing ranged from 9 to 30 ms. The rate in the final 10 s was 62–101 frames per second. There was no backlog, no overflow and no pending ingress, and received equaled delivered at 167,405.
- The owner's barrier (`audit_transport_error`) is at **+582 ms**. The owner waits in `queue.get(timeout=0.5)`, which starts only after +32 ms. The barrier therefore means the reader had failed by about +582 ms.

**The reader detected the loss somewhere in (0, ≈582] ms.** The NetworkProfile VPN-adapter disconnect at +102 ms is inside that bracket. Both times come from the same Windows system clock, so the comparison involves no cross-host offset. The ±0.1 s `time.windows.com` offsets do not affect it.

**The error text identifies the socket-level event.** In websocket-client 1.9.0, `Connection to remote host was lost.` comes only from a zero-byte `sock.recv` (`_socket.py:141–143`). The pilot passes no `sslopt`, so `suppress_ragged_eofs=True` (`_http.py:318`). A TCP FIN without TLS close_notify therefore produces the same text as a clean TLS close. The offline probes show the alternatives produce different results:

| Socket-level event | What the reader records |
| --- | --- |
| Reset | `ConnectionResetError`, errno 10054 |
| Local abort | `ConnectionAbortedError`, errno 10053 |
| Unsuppressed ragged TLS EOF | `SSLEOFError` |
| WebSocket close frame | Empty return, so `remote_close` / `connection_closed`, not `transport_error` |
| Read timeout | Retried |

| Hypothesis | Saved evidence |
| --- | --- |
| Local link transition (VPN adapter) | **Consistent**: the disconnect falls inside the bracket, and the end was an EOF rather than 15 s of idle timeouts, which a pure blackhole would produce. **Not proven**: the adapter event could be a consequence of the same upstream change. |
| WebSocket protocol close | **Excluded**: it would have stopped `remote_close`. |
| TCP reset / local abort | **Excluded by the text**: those would carry WinError 10054 or 10053. |
| Owner/batch stall or burst pressure | **Not supported at failure**: the queue was drained within about 32 ms and nothing overflowed. A local stall cannot produce a zero-byte read. The run's sampled high water of 231/256 is a separate capacity risk, related to the US overflow. |
| Peer or intermediary orderly close | **Not excluded**: a FIN from Coinbase, a CDN or the tunnel looks identical in these logs. |

**Still missing.** The exact detection instant (now instrumented). Whether the FIN arrived during flowing data or after silence (now instrumented by `last_return_age_ms` and `timeouts_since_last_return`). Clean versus ragged TLS end. Which host sent the FIN; that needs a packet trace, which is out of scope. DNS-client events, because that log is disabled. Exchange-side logs. And for the US attempt, everything at failure time.

## Proposed bounded diagnostic (for Codex review before any execution)

**One attempt** of the unchanged `eligibility-timing-256` protocol, at a commit containing this review's accepted fixes and transport snapshot. It keeps the six-product roster, one connection with no reconnect, a 256-frame queue, 16-frame batches, 67 minutes after acknowledgment, the existing packet/byte caps and both timing schedules, and a single uninterrupted 62-minute warmup. It is outcome-blind; no returns are examined.

**Preconditions, all recorded in PLAN or adjacent files before connecting.**

- Codex has reviewed and integrated this branch, the full Instant suite passes on the PC, and the commit is recorded.
- Checkout and Git storage are outside OneDrive. No planned VPN or network change, and no sleep, during the window.
- Five-sample `w32tm` stripchart before and after, retained even on failure. Any retry is kept separately and never relabelled.
- Decide, as Codex's or the user's choice since each is a declared change, two optional additions:
  - **(a)** passing `sslopt={"suppress_ragged_eofs": False}` so a ragged TLS EOF is distinguishable from a clean close. Only the exception class changes; the stop reason stays `transport_error`.
  - **(b)** enabling the DNS-Client operational log. That is a system logging setting, which this review did not change.

  If either is declined, record that evidence as explicitly unavailable.
- A read-only sidecar process, started before the socket, that once per second appends `utc_ms`, `perf_counter_ns`, the count of up adapters, whether an IPv4 default route exists, and a salted hash of the default-route interface. No names, GUIDs or addresses. Wall-minus-monotonic jumps over 50 ms flag a clock step. Optionally, every 10 s, it records only the success/failure, error code and latency of resolving the public feed hostname, never the addresses.

**Clocks measured.**

- Reader receipt wall time and `perf_counter` per frame (existing).
- Transport snapshot `detected_ts_ms` / `detected_monotonic_ns` and last-return age.
- The owner barrier.
- Sidecar wall time and `perf_counter` per second.
- Windows event times (same system clock).
- `w32tm` offsets.

**Trigger.** The first transport snapshot, the first overflow snapshot, or normal completion. No retry in any case.

**Artifacts (raw files private on the PC; a sanitized summary is committed).**

- PLAN and its digest, REPORT (`reader[i].transport` / `overflow`), stderr (`READER_TRANSPORT` / `READER_OVERFLOW`), the journal, `observed.jsonl`, the sidecar JSONL and the clock files.
- A redacted export, for the window from 5 minutes before to 15 minutes after the last frame, of System, NetworkProfile/Operational, WLAN, DNS-Client (if enabled) and Time-Service events.
- SHA-256 of every file.

**Limits.** One attempt and one extra local process polling once per second, with bounded output (about 4,000 lines). No payload logging, no authenticated calls and no change to caps or timing candidates.

**Decision rules.**

- **Complete.** `stop=duration`, 20 cohorts and 240 verified observations: interpret under the existing timing protocol. The transport snapshot is null.
- **EOF (zero-byte read) with an adapter-down or route-loss sample, or event, between last return and detection.** Classify as *local link transition coincident with EOF*: supported, not proven. The next step is a network-environment decision by the user, not another capture.
- **EOF with sidecar, DNS and events all healthy within ±2 s.** Classify as *peer or intermediary orderly close*. The next step is protocol-level close evidence (control-frame receipt), not a retry.
- **Reset or abort errno.** If aligned with a link event, local; otherwise remote reset.
- **Empty return.** A protocol close. The code is unavailable, so the next step is to expose close frames.
- **`timeouts_since_last_return ≥ 1` or `last_return_age_ms ≥ 1000`.** Silence preceded the loss (blackhole or stall), as opposed to a loss during flowing data.
- **Overflow.** Apply the existing overflow rules, using writer phase, elapsed time and arrival windows.
- **A clock step, or a recorder `clock regressed` failure.** Record a time-service event; the attempt is invalid for timing.

**Stop without retry.** After any early stop, or if a precondition fails before connecting. Another attempt requires Codex and user review of these artifacts.

**What would still be missing even then.** Which host sent a FIN; that needs a packet trace, which is excluded. Exchange-side state. And, if (a) or (b) is declined, the TLS close type or DNS-client causes.

## Commands actually run (Windows, from the review worktree unless noted)

```text
git fetch --prune origin; git status --short --branch; git rev-parse HEAD; git worktree list; git remote -v
git rev-parse --show-toplevel --absolute-git-dir --git-common-dir; git sparse-checkout list
sha256sum <packet>                                   -> c1cebf9f…5f97, 924385 bytes
python -I <manifest check: git cat-file vs packet offsets>   -> 111 sources, mismatches: []
python -m pytest -q -p no:cacheprovider tests/test_instant*.py       -> 1253 passed (pin)
python <scratch repro_a_shared_ms.py>, <repro_a3.py>  (unmodified)  -> A1/A2/A3 failures above
git archive 257be69 scripts/scoring_experiment tests docs/research | tar -x -C <scratch>/pin257
  + new probe file; pytest tests/test_instant_pipeline_boundary_review.py  -> 8 failed, 25 passed
    (asof freeze; torn line JSONDecodeError; 6 transport KeyError 'transport'; before the TLS-EOF case was added)
python -I <scratch asia_tail.py> <preserved attempt>  -> read-only tail; journal sha unchanged
python scripts/scoring_experiment/verify_instant_timing_attempt.py <preserved Asia> --plan-sha256 <PLAN.sha256>
                                                     -> all committed fields equal; +torn_final_observation_lines 0
python -m pytest -q -p no:cacheprovider tests/test_instant*.py       -> 1287 passed (after)
python -m pytest -q <7 focused reader/pilot/verifier/journal/probe files>  -> 94 passed
python -m black --check <7 changed files>  (24.8.0)  -> unchanged
bash scripts/validate_mw_guardrails.sh               -> All guardrails passed
git diff --check                                     -> clean
```

The 1,287 total is the 1,253 baseline plus 34 new probes. Checks are recorded in [CHECKS.json](../results/fable_radar_pipeline_review_20261113/CHECKS.json), including before and after hashes of every changed file.

## Evidence limitations

All probes are synthetic, with injected clocks. The library-mapping probes feed bytes to the real websocket-client parser; they do not open a socket. They show what each socket-level event *would* record, not what happened in Asia. The Asia bracket depends on the owner's 0.5 s queue poll and on the hook taking about 50 ms, both inferred from code and the barrier timestamp. I did not inspect the raw Windows events; the +102 ms offset comes from Codex's sanitized summary. Reachability of F1 was argued from single-threaded structure and measured preparation times, not observed live. No full repository suite, native Mac, cloud or live execution is claimed. The pre-existing seed-fixture failure is outside `tests/test_instant*` and was not run.

## Not changed

Codex's `RESUME_HERE.md`, `ACTIVE_WORK.json`, restart handoff and review packets are unchanged. This deliberately departs from AGENTS.md handoff step 5, per the assignment; Codex owns those files. Also unchanged:

- historical evidence, contracts, targets, monitor, book, input, journal, index, decision, publication and association sources, and their hashes
- queue, batch and capture limits; timing candidates; warmup
- production, backend and frontend

## Single decisive next action

**Codex reviews and integrates this branch's offline changes: the as-of freeze fix, the torn-line verifier fix and the `instant-reader-transport-v1` snapshot. In the same review, Codex decides on the two optional diagnostic additions, ragged-EOF exposure and DNS-client logging, and on the read-only sidecar.** Another attempt without the transport snapshot would reproduce the same unresolvable Asia evidence. With it, one bounded attempt under the rules above can classify the next transport loss without guessing.
