# Asia disconnect review: saved evidence and offline probes

The remote overflow-diagnosis branch was verified at
`598fba0bc7d6c2fc754f6bb22cbeedce2f79b394`, matching the Windows checkpoint.
Verification checkpoint is `975234ed44c6708a28ccce1df11ed671258cd46c`.
That newer commit was reviewed before starting isolated branch
`codex/instant-radar-disconnect-diagnosis-20261111`. It preserves the Asia
attempt and changes documentation, not reader implementation.

This review follows MW_SPEC 0.1 (measured evidence, explicit missingness) and
0.2 (targeted changes). Ten offline regression probes and the saved-attempt
test runner change; no reader or capture runtime fix is warranted by the
reproductions below. No live capture, capacity change, reconnect change,
production change, historical validation or fitting ran.

## Evidence and limits

[ASIA_01_VERIFIED.json](results/instant_reader_overflow_20261110/ASIA_01_VERIFIED.json)
is the committed evidence. The original full capture and logs remain on Windows;
this cloud review did not independently reopen that capture.

- The verifier reports 167,407 journal records, 167,405 verified batch-ingress
  clocks, SQLite quick check `ok`, a finished segment and no pending ingress.
- The PC reader returned and delivered 167,405 frames; sampled high water was
  231 of 256, `overflow` was null, and stderr was empty. A disconnect is not
  evidence of queue saturation, and delivered frames are not a proof that no
  exchange messages were missed before reaching the local socket.
- Full ACK was at `1794356673393`; the last reader receipt was
  `1794359028291` (2026-11-11 01:03:48.291 UTC / November 10 17:03:48.291 Pacific).
  Their difference is 39m 14.898s, before the 62-minute warmup. This timestamps
  the last successful frame, not the exact instant of socket failure.
- `stop=transport_error`, with text `Connection to remote host was lost.`
  All 20 cohorts were unreached. Zero publications/observations means timing
  and readiness remain unmeasured, not zero latency or a successful pilot.
- The immediate post-run `time.windows.com` clock probe reported DNS failure
  `0x80072AF9`. A separate retry returned five samples. Preserve both results:
  the retry does not turn the original check into a pass. Their relation to
  the earlier already-established Coinbase connection is unknown.

The verifier proves the recorded prefix and denominators under its checks. It
does not diagnose the network, certify clock synchronization through a DNS
failure, or identify who terminated a socket.

## What the reader does on disconnect

The new `tests/test_instant_reader_disconnect.py` probes use a finished-reader
barrier and simulated receipt clocks. They test single-frame and 16-frame
journal paths with the actual `QueuedSocket` and indexed SQLite journal:

| Input | Verified behavior |
| --- | --- |
| WebSocket connection-lost exception | Retains exception, drains every queued frame in FIFO order, then rethrows; capture reports `transport_error` and journals `audit_transport_error` |
| Socket reset exception | Same prefix/barrier behavior; saves the exception's string |
| Empty return from `recv()` | Drains the prefix, then reports `remote_close` and journals `connection_closed` |
| WebSocket timeout followed by valid data | Retries the timeout; no permanent failure and no invented frame |
| Disconnect before any frame | Rethrows the same exception with zero received/delivered frames |
| Library socket EOF versus protocol close | websocket-client 1.9.0 maps empty socket reads to the connection-lost exception; a valid close-1000 frame makes its `recv()` return an empty string |

All queued-prefix cases verify source equality, one connection, no reconnect,
no pending ingress, SQLite integrity, zero publications and explicit final
barriers. The capture uses its declared one-connection bound. No tested path
lost a locally received frame or suppressed a transport exception while draining
below the capture's duration/budget stops. These probes do not establish every
possible boundary/race or actual Windows network behavior.

The library probe reproduces the error text with a fake byte stream, without
opening a network socket. It demonstrates a possible origin of the message,
not the actual cause on the PC. Coinbase, an intermediary, local network
conditions and scheduling cannot be distinguished from that text alone.

## What is missing at failure

The reader retains the exception object in memory. After the queue drains,
`capture()` saves its string in `REPORT.json -> attempts[i].error`, with a stop
reason and optional close errors. It does not persist the exception class,
structured errno/winerror, traceback/cause chain, reader-side failure timestamp,
or transport-time queue/writer snapshot. The immediate stderr record added for
overflow is not emitted for ordinary transport loss. Empty stderr here is
consistent with implementation, not evidence that no failure happened.

The journal's final transport barrier has the owner's actual observation/commit
clock, after draining and any intervening work. The tests deliberately delay
the owner and confirm that the barrier timestamp is later than reader failure.
It must not be relabelled as an exact socket-failure time. The `recv()` API also
discards a WebSocket close frame's status/reason in the normal empty-return case.

These are diagnostic limits; no causal timestamp is invented and no runtime
patch is made merely to speculate about this historical disconnect.

## Exact next Windows action: collect existing evidence

Do this before another pilot. Preserve the old attempt and its logs unchanged.
The block below makes a new local review folder, copies only PLAN/REPORT and
small sibling logs, writes hashes/metadata, and queries retained Windows events.
It does not copy the 174MB capture, restart a service, make a network request,
change event-log settings or run another capture. Execute in PowerShell:

```powershell
$base = Join-Path $env:USERPROFILE '.moonwalking\analysis\instant_reader_overflow_20261110'
$name = 'asia-20261110-162344'
$attempt = Join-Path $base $name
$out = Join-Path $base ('asia-disconnect-review-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
if (-not (Test-Path (Join-Path $attempt 'REPORT.json'))) { throw 'Original final REPORT.json is required.' }
New-Item -ItemType Directory $out -ErrorAction Stop | Out-Null
Copy-Item (Join-Path $attempt 'PLAN.json') $out -ErrorAction Stop
Copy-Item (Join-Path $attempt 'REPORT.json') $out -ErrorAction Stop
$report = Get-Content (Join-Path $attempt 'REPORT.json') -Raw | ConvertFrom-Json
$report | Select-Object stop,first_ack_ts_ms,last_reader_receipt_ts_ms,attempts,reader,diagnostic_cohorts | ConvertTo-Json -Depth 12 | Set-Content (Join-Path $out 'FAILURE_CONTEXT.json') -Encoding UTF8
Get-ChildItem $base -File | Where-Object { $_.Name -like "$name-*" -and $_.Extension -in '.txt','.log','.json' } | ForEach-Object { Copy-Item $_.FullName $out -ErrorAction Stop }
Get-ChildItem $base -File | Where-Object { $_.Name -match 'clock|retry|asia' } | Select-Object Name,Length,CreationTimeUtc,LastWriteTimeUtc | ConvertTo-Json | Set-Content (Join-Path $out 'SIBLING_LOG_METADATA.json') -Encoding UTF8
# Last successful frame, not a claimed failure instant; retain a broad interval.
$anchor = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$report.last_reader_receipt_ts_ms)
$start = $anchor.UtcDateTime.AddMinutes(-5).ToLocalTime()
$end = $anchor.UtcDateTime.AddMinutes(15).ToLocalTime()
$logs = @('System','Microsoft-Windows-NetworkProfile/Operational','Microsoft-Windows-WLAN-AutoConfig/Operational','Microsoft-Windows-DNS-Client/Operational')
foreach ($log in $logs) {
    $safe = $log -replace '[/\\]','_'
    try {
        Get-WinEvent -FilterHashtable @{LogName=$log;StartTime=$start;EndTime=$end} -ErrorAction Stop | Select-Object @{Name='TimeUtc';Expression={$_.TimeCreated.ToUniversalTime().ToString('o')}},Id,ProviderName,LevelDisplayName,Message | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $out "$safe.json") -Encoding UTF8
    } catch {
        $_.Exception.Message | Set-Content (Join-Path $out "$safe-unavailable.txt") -Encoding UTF8
    }
}
$hashes = Get-ChildItem $out -File | Get-FileHash -Algorithm SHA256 | Select-Object Path,Hash
$hashes | ConvertTo-Json | Set-Content (Join-Path $out 'HASHES.json') -Encoding UTF8
Write-Output $out
```

Include the following with that folder when continuing on Windows:

1. The original `REPORT.json` attempt fields, especially any
   `socket_close_error`, and the original `${name}-stdout.txt` /
   `${name}-stderr.txt`. Their paths are siblings of the attempt, not inside it.
2. Raw `${name}-clock-before.txt`, `${name}-clock-after.txt`, the separately
   retried clock output (whatever filename was used), and the exact retry time
   and command if the retry was only shown in the terminal. The block lists
   sibling filenames but cannot discover a retry stored elsewhere. Do not
   replace or rename the failed check as a successful check.
3. Retained System/network/WLAN/DNS events around the disconnect and the later
   failed clock check. If the check occurred outside the extraction's 20-minute
   interval, query its actual time separately. Disabled, absent or unreadable
   event logs mean unavailable evidence, not a healthy network.

A socket close/reset, interface disconnect, sleep/resume or driver event near
01:03:48 UTC could explain the transport failure. DNS-client events at the
actual clock-check time could explain that separate failure. A shared interface
outage spanning both would support a link; coincident event times alone do not
prove one. If those events and lower-level socket traces were not retained,
no saved log can reconstruct the exact historical initiating cause. That is an
explicit unresolved result, not a reason to guess or silently repeat the run.
The PowerShell block is provided for Windows and was not executed on Linux.

## Pilot decision and checks

A new PC timing pilot is not yet justified by this review: the tested reader
behavior is correct and the existing local error/events have not been inspected.
The immediate next command collects existing evidence rather than repeating
67 minutes with the same diagnostic limits. The earlier copy-ready pilot
command is historical and is not a recommendation to launch again now.

If local logs remain inconclusive and a future diagnostic capture is separately
chosen, first predeclare measurement of reader-side error type/errno/cause and
UTC/monotonic detection time, any protocol close code/reason, and time-aligned
Windows link/DNS observations. A short startup success alone would not resolve
a failure after 39 minutes. A useful bounded attempt would either complete
warmup and all 20 cohorts with 240 independently verified local observations,
or supply enough failure-time transport/link evidence to distinguish a mechanism.
No reconnect across an interrupted warmup, cap increase, schedule change or
claim of useful timing follows automatically.

Verification uses offline synthetic tests only. The new ten probes are included
in `run_instant_offline_checks.py`, so future saved-attempt checks exercise them.
See [checks](results/instant_reader_disconnect_20261111/CHECKS.json) for commands,
counts and runtime versions. Historical Asia/US evidence, other agent review
statuses and the original runtime implementation remain unchanged.
