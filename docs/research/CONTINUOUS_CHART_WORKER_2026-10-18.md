# Continuous local chart pilot — AMP-USD

Update 2026-10-19: bounded local narration is now connected; see
[LOCAL_CHART_NARRATION_2026-10-19.md](LOCAL_CHART_NARRATION_2026-10-19.md).
Earlier no-model statements below record the initial pilot stage and are superseded.

Tom authorized a continuous local pilot and assistance from Claude/Gemini, then
selected AMP. No FET or RENDER series is used as AMP history. Production, other
worktrees and existing owner data stores remain untouched.

## Running locally

`Moonwalking-Chart-AMP-USD` is a current-user, limited Windows scheduled task.
It checks hourly and at sign-in, starts missed work when available, permits
battery operation, ignores overlapping task instances, and stops a run after
20 minutes. It uses the installed windowless Python executable when available.
The task does not require this chat or a browser tab. Windows must be awake and
the configured user signed in; this is not a machine-wide service. No wake timer,
password, administrator elevation, firewall rule or new cloud service is added.

The first real request run obtained 1,957 completed AMP-USD daily candles through
2026-10-18, with zero internal missing daily intervals; 279 complete weekly bars
were calculated. Actual repeat runs reported unchanged daily prices/weekly
structure. An explicit run through Task Scheduler finished with result 0.

The final schedule boundary was verified as 2026-10-19T00:21:15-07:00, equivalent
to 07:21:15 UTC. A PowerShell regression was caught during setup: ConvertFrom-Json
can return DateTime rather than a string; parsing its implicit culture string
lost the UTC Kind and shifted the task seven hours. The installer now preserves
the DateTime instant and verifies the registered boundary to within one second.
Planned times in status remain estimates: sign-in/manual runs can precede the
hourly trigger, and sleep or execution duration can delay them.

```powershell
# One check; no browser or model required
python scripts/chart_worker.py --product AMP-USD
# Install/update only this checkout's own task (refuses unrelated same-name task)
./scripts/install_chart_worker.ps1 -Product AMP-USD
# Run the task now / inspect actual Windows task status
Start-ScheduledTask -TaskName 'Moonwalking-Chart-AMP-USD'
Get-ScheduledTaskInfo -TaskName 'Moonwalking-Chart-AMP-USD'
# Stop future scheduled checks; cache retained
./scripts/install_chart_worker.ps1 -Product AMP-USD -Remove
```

Open the local dev server at `/chart-map?worker=1`. The status panel polls only the
fixed local JSON file every 30 seconds. **Open worker chart** checks the exact file
SHA-256 and generation before parsing/opening AMP. It never automatically replaces
an active chart, replay cutoff or manual selection. The panel is absent from
production builds. The dev server must run to view the panel; the worker does
not depend on that server being open.

## Ownership and calculation

All worker writes are inside its new ignored directory
`frontend/.runtime/chart-worker/`: owner marker, `jobs.sqlite3`, `history.json`,
`evidence.json`, and `status.json`. It refuses to adopt an unowned nonempty
directory or a directory belonging to another product. SQLite is authoritative;
exports are disposable publications repaired from the committed SQLite state.
Only the newest snapshot and 100 compact run records are retained. No production
store is discovered, read or modified. A separately supplied `--seed` is read-only
and validated, but AMP was pulled independently without a seed.

Unsigned GETs go only to Coinbase Exchange public product/candle endpoints, with
at least 1.05 seconds after each response and up to three attempts for 429/503.
Retry-After is honored; requested pauses over two minutes stop the run rather
than retrying early. Bootstrap is bounded to 24 windows of 299 days. Later checks
refresh the last seven observed days and elapsed days. Historical corrections
older than that overlap are **not detected** by this pilot. Missing buckets are
reported, not filled; days omitted in the refreshed span are removed from that
span. Counts and up to ten revision examples are recorded.

Only complete UTC days enter the cache, with a five-minute settlement margin
around midnight. Provider metadata, timestamps, units, OHLCV and duplicate
conflicts are checked. A missing latest closed day produces a coverage warning,
even if the HTTP request succeeded. This is single-provider available venue
history; cryptographic consistency does not prove exchange truth, independent
validation, migration lineage or all-time coverage.

The existing Node evidence producer validates/aggregates the history. Its identity,
input SHA-256 and effective cutoff must match the worker input. Native daily data,
completed weekly evidence and calculation-engine fingerprints are separate.
Successful identical hourly checks retain the exact saved evidence when the UTC
cutoff/engine are also unchanged. A source timestamp alone cannot mean new chart
structure. Engine changes regenerate evidence even with unchanged candles.

The SQLite lease has a random ownership token and 30-minute expiry; a superseded
owner cannot commit. Publication holds a SQLite write transaction so an old
export cannot overwrite a newer generation. Files are atomically replaced, with
short Windows PermissionError retries; status publishes last. The UI rejects
mixed hashes/generations and keeps the current chart. Failed jobs retain previous
history/evidence and success time; failed/empty requests never report unchanged.

## Assistance and limits

[Claude](https://claude.ai/chat/febcde95-ad6f-4dbc-b29b-d48566b8d841) reviewed the
reliability brief. [Gemini](https://gemini.google.com/app/429b7d197fd4e397) reviewed
freshness and evidence-change pitfalls. They did not inspect or execute this code.
Their assignments initially named FET before Tom chose AMP; their system-level
reviews apply, but none of their FET figures are used by the AMP worker.

Accepted: lease fencing, crash-consistent publication, read-side checksums,
explicit UTC completion, separate daily/weekly/engine change keys, version
regeneration, failure preservation and confirmation-lag explanations. Existing
unit tests cover synthetic revisions, gaps and restarts. Not adopted: calling
hash consistency a guarantee of Coinbase's canonical truth; Gemini's Sunday
00:00 weekly-close example (our weeks close Monday 00:00 UTC); treating every
missing bucket as an HTTP failure or inventing its cause.

The UI and what-changed summaries are deterministic. No local LLM is connected,
no perpetual Claude/Gemini browser automation is installed, and no buy/sell,
price-arrival probability, notification delivery or trade execution is added.
The next stage is an optional local explanation model consuming the fixed evidence
packet with output validation. This worker is a functioning scheduled data and
calculation pipeline, not yet a model-driven analyst.

Remaining scope: additional coins, persistent chart selection, older revision
rescans, configurable settings, richer structural diffs, persistent scheduler
health reconciliation, SQLite backups and local model narration.

## Verification for this delivery

- Full frontend verify: 549 tests across 47 files, token/Figma sync, production build pass.
- Worker: 18 offline tests pass, including node timeout/nonzero/hash/cutoff rejection,
  engine-change regeneration, midnight margin, lease fencing and partial export repair.
- Evidence packet: 4 offline tests pass.
- Guardrails and diff whitespace checks pass. Existing Browserslist/bundle-size and
  AlertsPanelGlobal act warnings remain.
- Real AMP bootstrap, repeated unchanged checks, two explicit successful scheduled
  executions (result 0), registered UTC-equivalent boundary and browser checksum-open
  verified. Waiting a full hour was not required or performed.
- Runtime JSON, SQLite and screenshots remain ignored. No production deployment.
