# Reader queue overflow: offline diagnosis and next PC check

The November 10 Windows Asia attempt ended in a transport error before
warmup. Review the
[verified result](results/instant_reader_overflow_20261110/ASIA_01_VERIFIED.json)
before planning another capture.

The verified remote `origin/codex/instant-radar-20261028` tip was
`fca475e014bab94549fdda7816390a4169b58f7d`, identical to the supplied checkpoint.
There was no newer work on that branch to review. Implementation is
`cfa4aff44aa017de704b7fa8c641dcf7389ef159`, on isolated branch
`codex/instant-radar-overflow-diagnosis-20261110`.

This work satisfies MW_SPEC 0.1 (measured evidence and explicit missingness)
and 0.2 (targeted changes): only research reader/capture diagnostics, offline
tests and checkpoint documentation change. Queue sizes, batch sizes, capture
bounds, causal clocks, journal schema, scoring and production are unchanged.
No socket capture, historical discovery, locked validation or fitting ran.

## What the US evidence establishes

[US_01_VERIFIED.json](results/instant_live_timing_20261109/US_01_VERIFIED.json)
reports `queue_overflow`, a finished segment, SQLite quick check `ok`, 302,679
verified packet records, 302,677 verified batch-ingress clocks, zero pending
ingress frames and zero publications or local delivery observations. The
portable checkpoint records 2,943.474 seconds (49m 03.474s) from full ACK to the
last committed reader receipt. That is before the 62-minute warmup.
All 20 planned timing cohorts were unreached. Zero observations is not a
latency measurement, readiness measurement or evidence of successful delivery.

The full Windows capture/report/stdout was not available in this cloud checkout.
The committed verifier summary contains neither contemporaneous arrival counts
nor writer-phase state. No new claim about that capture's initiating cause can
be recovered from this summary. The earlier successful four-product session
and synthetic capacity trials do not establish six-product US capacity.

## What the old logs can distinguish

| Evidence before this change | Supported conclusion | Remaining ambiguity |
| --- | --- | --- |
| Stop reason and error text | Queue frame cap versus an oversized frame | No burst/stall attribution |
| Received/delivered/high-water counts | Local returns exceeded delivered frames and the queue saturated | Failed enqueue and undelivered backlog are not committed packets |
| Aggregate reader-to-writer latency | Committed frames waited locally | Lost tail is unmeasured; no failure-time ordering |
| Aggregate callback-through-commit timing | A completed journal callback was slow | Processing, SQLite, CPU scheduling and storage delay share the metric |
| Progress/after-commit hooks | Possibly long gaps between progress lines | Hook duration is absent from callback latency; no live phase at overflow |

The test pair reproduces the same old counts (257 received, zero delivered,
256 high-water) with a 257-frame rapid return burst and with paced returns
while the writer is held. The journal integration cases also show that a
blocked post-commit hook can fill the queue while the old callback duration
stays zero under the controlled clock. A journal persistence stall appears in
that old duration once the callback finally completes. Thus the logs contain
some timing hints, but do not uniquely identify the failure-time mechanism.

## Additive instrumentation

`QueuedSocket` retains at most 257 monotonic return timestamps. There is no
per-frame disk log or payload copy. On failed enqueue it freezes one
`instant-reader-overflow-v1` snapshot with:

- Distinct `queue_full` / `frame_bytes_exceeded` reasons, wall receipt label,
  queue capacity/depth, received/delivered counts and oldest queued-frame age.
- Counts of socket returns in the trailing 100ms and 1s, retained sample span
  and `lower_bound` flags when the bounded ring cannot prove an exact count.
  The rejected frame is included in the return count, never in the queue.
- Active owner phase (`journal_callback`, `after_commit`, or
  `between_callbacks`), phase elapsed time, batch frame count and last
  completed owner activity. `between_callbacks` includes uninstrumented
  setup, lifecycle, progress and loop work; it is not proof of an idle CPU.

The reader immediately emits one `READER_OVERFLOW {json}` line to stderr,
before the owner resumes. A completed pilot also stores the same frozen
snapshot at `REPORT.json -> reader[i].overflow`. The healthy instrumented
control has `overflow: null`. The report returns copies, so later shutdown,
writer recovery or caller mutation cannot alter failure-time evidence.
Stderr emission is best effort, not a durable journal receipt; retain it
separately if the owner never completes a final report.

Counts and queue depth are local samples around failed enqueue, not an atomic
transaction with the consumer's queue removal. Arrival windows measure local
`recv()` returns, not exchange sends or physical network ingress. Large counts
can mean exchange traffic, network/OS/socket buffering or local scheduling.
A long `journal_callback` identifies the occupied phase, not disk versus CPU
versus descheduling. A burst and a writer stall can occur together; no automatic
single-cause classifier or capacity recommendation is justified.

## Reproduce offline

From the repository root with the research Python environment:

```powershell
python -m pytest -q tests/test_instant_reader_overflow.py tests/test_instant_real_indexed_pilot.py tests/test_instant_source_pilot.py tests/test_instant_stream_journal.py tests/test_instant_timing_attempt_verifier.py
python -m pytest -q tests/test_instant*.py
bash scripts/validate_mw_guardrails.sh
```

Use Bash for shell glob expansion in the second command, or pass the explicit
file list from your runner on Windows. The unattended saved-attempt runner now
includes `test_instant_reader_overflow.py` as well.

The new 11 cases use Events and a controlled monotonic arrival clock, with
bounded real-time waits only to fail deadlocks. No test depends on thread speed
or an actual sleep. They cover 4- and 256-frame queues, burst and paced input,
a blocked real indexed journal persistence operation, a blocked post-commit
hook, immediate stderr emission before recovery, frozen report copies,
FIFO/no-loss control, oversized-frame distinction, SQLite integrity and the
explicit queue-loss barrier. The writer stall is an injected persistence gate,
not a measurement of actual Windows disk behavior.

In the controlled 256-frame case, 257 returns span 25.6ms for a burst versus
5,120ms for paced arrivals. The latter shows the writer phase occupied for
5,140ms when the failed enqueue occurs. These are declared synthetic durations,
not capacity or real-world latency results. All 1,243 Instant Radar tests pass
on Linux Python 3.12.14 / pytest 8.3.5. Black 24.8.0, repository guardrails and
`git diff --check` pass. See [checks](results/instant_reader_overflow_20261110/CHECKS.json).

## Copy-ready next bounded PC pilot

This is a future, manually started engineering check, not authorization for an
unattended cloud capture. Preserve the old US attempt unchanged. Run one fresh
Asia attempt under the existing [protocol](INSTANT_LIVE_TIMING_PILOT_PROTOCOL_20261109.md)
(00:00–06:00 UTC, starting by 04:52 UTC to leave the documented full duration
and connection allowance). Substitute `europe` only under that protocol's
07:00–13:00 UTC window and reversed schedule; do not silently retry a failed run.
The CLI enforces its start window. This copy-ready PowerShell block uses a new
detached checkout of the pushed diagnosis branch and the existing research
venv. It does not touch the always-on collector or port 5003.

```powershell
$repo = Join-Path $env:USERPROFILE 'Projects\Moonwalking-InstantRadar'
$work = Join-Path $env:USERPROFILE 'Projects\Moonwalking-InstantRadarOverflow-20261110'
$branch = 'codex/instant-radar-overflow-diagnosis-20261110'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Existing research Python venv is required.' }
git -C $repo fetch origin "refs/heads/${branch}:refs/remotes/origin/${branch}"
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed.' }
git -C $repo worktree add --detach $work "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Worktree not created; preserve any existing directory.' }
Set-Location $work
git rev-parse HEAD
$base = Join-Path $env:USERPROFILE '.moonwalking\analysis\instant_reader_overflow_20261110'
New-Item -ItemType Directory -Force $base | Out-Null
$attempt = Join-Path $base ('asia-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
w32tm /stripchart /computer:time.windows.com /dataonly /samples:5 > "${attempt}-clock-before.txt"
if ($LASTEXITCODE -ne 0) { throw 'Pre-pilot clock check failed.' }
& $python scripts/scoring_experiment/instant_real_indexed_pilot.py --profile eligibility-timing-256 --window asia --out-dir $attempt 1> "${attempt}-stdout.txt" 2> "${attempt}-stderr.txt"
$pilotExit = $LASTEXITCODE
w32tm /stripchart /computer:time.windows.com /dataonly /samples:5 > "${attempt}-clock-after.txt"
$clockExit = $LASTEXITCODE
if ($pilotExit -ne 0 -or $clockExit -ne 0) { throw 'Preserve logs; pilot or post-clock check failed. Do not retry automatically.' }
$planSha = (Get-FileHash (Join-Path $attempt 'PLAN.json') -Algorithm SHA256).Hash.ToLowerInvariant()
& $python scripts/scoring_experiment/verify_instant_timing_attempt.py $attempt --plan-sha256 $planSha 1> "${attempt}-VERIFIED.json" 2> "${attempt}-verify-stderr.txt"
if ($LASTEXITCODE -ne 0) { throw 'Verifier failed; preserve the attempt and verifier logs.' }
Get-Content (Join-Path $attempt 'REPORT.json')
```

Check both checkout and common Git storage are outside OneDrive/synced folders
before using this block. The same-session plan digest above checks consistency;
it is not an independently pre-pinned plan. Preserve PLAN.json and its digest
before interpreting the results. The CLI writes the plan before connecting.
The code commit printed above can be followed by a documentation-only commit.
The Windows block is documented for PC execution, not executed or certified
from Linux. If the process remains blocked, retain stderr's overflow snapshot
and the recoverable journal prefix; do not claim a clean final report.

Success criteria for the next check:

1. Unchanged six-product roster, one connection, 256 queued frames, at most
   16 per batch, 67-minute duration after ACK and original packet/byte caps.
   Both clock checks succeed; retain command, commit, PLAN/digest and logs.
2. Engineering completion: `stop=duration`, finished valid SQLite journal,
   no queue overflow, no pending ingress, all 20 cohorts complete and 240 local
   observations independently verified (120 per schedule). Report missing
   readiness and within-bound counts separately for every product and schedule;
   do not require or imply every product is ready or on time.
3. If it overflows: treat capacity/delivery completion as failed, preserve the
   prefix, final report if available and exactly one `READER_OVERFLOW` line per
   failed connection. Inspect phase, elapsed time, queued age and bounded
   arrival counts together. That is diagnostic evidence, not pilot success.
4. Any pre-warmup stop has zero measured timing cohorts; do not impute results.
   No automatic retry, cap increase, product removal, tuning, fitting or live
   integration follows. Review the evidence before choosing another attempt.

No decision is needed to complete this offline task. The remaining decision is
when to run the one bounded PC check in a declared window; actual Windows
bottleneck attribution and live timing/readiness remain unmeasured here.
