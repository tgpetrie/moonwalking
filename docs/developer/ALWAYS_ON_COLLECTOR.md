# Always-on collector (Windows)

Moonwalking's research data (signal outcomes, board outcomes, control dry
runs, sell-plan grades, 1h volume, price snapshots, agent ledger) only
exists if a backend is running and collecting. On this PC that backend is a
dedicated, always-on process. It is not a dev server.

## Why it exists

Until 2026-10-12 the backend only ever ran as a child of a chat or coding
agent session. When that session ended, collection stopped with no error:
the main log ends mid-stream at 2026-10-05 11:22:54 and nothing was collected
until 2026-10-12. Each worktree also wrote to its own copy of every store,
so the data was split across folders.

## What runs

| Piece | Where |
| --- | --- |
| Scheduled task | `Moonwalking Collector` (Task Scheduler, current user, at logon + 5-minute backstop) |
| Launcher | `scripts\windows\run_collector.ps1`, supervises Python and restarts it if it exits |
| Code | `C:\Users\tgpet\Projects\Moonwalking-Runtime`, branch `runtime/collector` (its own worktree, so editing other worktrees never changes what's collecting) |
| Python | `%USERPROFILE%\.moonwalking\venv` (separate from any worktree `.venv`) |
| Data | `%USERPROFILE%\.moonwalking\data` (the canonical copy of every store, see below) |
| Logs | `%USERPROFILE%\.moonwalking\logs`: `server.log` (rotating app log), `collector-events.log` (starts/exits/restarts), `collector-stdout.log` / `collector-stderr.log` (current run, `.prev` = previous run) |
| Port | `5003`, serving the API and the built frontend (`SERVE_FRONTEND_DIST=1`) |

The launcher pins every store with an environment variable, so the
collector never writes into a worktree:

| Store | Variable | File |
| --- | --- | --- |
| Accounts and watchlists | `WATCHLIST_DB_PATH` | `watchlists.sqlite` |
| Signal outcomes | `MW_SIGNAL_OUTCOMES_DB` | `signal_outcomes.sqlite` |
| Board outcomes | `MW_BOARD_OUTCOMES_DB` | `signal_outcomes.sqlite` (same file by design) |
| Control dry runs | `MW_CONTROL_DRY_RUN_DB` | `control_dry_run.sqlite` |
| Sell-plan outcomes | `MW_SELL_PLAN_OUTCOMES_DB` | `sell_plan_outcomes.sqlite` |
| 1h volume | `MW_VOLUME_1H_DB` | `volume_1h.sqlite` |
| Price snapshots | `MOONWALKING_PRICE_DB` | `price_snapshots.db` |
| Agent ledger | `MW_AGENT_OBSERVATIONS_DB` | `agent_observations.sqlite` |

Environment variables set by the launcher win over `backend/.env`
(python-dotenv does not override existing variables).

## Rules for people and AI sessions

- **Don't stop the collector.** Don't kill the Python process on port 5003,
  don't stop or disable the `Moonwalking Collector` task, and never start a
  backend with `--kill-port` on 5003.
- **Dev backends use another port**, e.g. `python backend/app.py --port 5013`,
  and point Vite at it with `VITE_PROXY_TARGET=http://127.0.0.1:5013`. A dev
  backend left on its defaults collects into its own worktree's stores, which
  is the fragmentation this setup removed.
- If something else already holds 5003 when the collector starts, it collects
  on the next free port (`--auto-port`) instead of stopping. Check
  `collector-stdout.log` for the port it actually bound.
- **Don't develop in `Moonwalking-Runtime`.** Change code in a feature worktree,
  then update the runtime (below).
- Don't copy or merge stores by hand while the collector is running. Use the
  SQLite backup API on a stopped collector, and keep the originals.

## Check it

```powershell
Get-ScheduledTask -TaskName 'Moonwalking Collector' | Select-Object State
Get-Content $env:USERPROFILE\.moonwalking\logs\collector-events.log -Tail 5
Invoke-RestMethod http://127.0.0.1:5003/api/health
Invoke-RestMethod http://127.0.0.1:5003/api/agents/status | Select-Object db_path
```

`/api/agents/status` should report a `db_path` under
`%USERPROFILE%\.moonwalking\data`. File times in that folder should be a
minute or two old at most (except `watchlists.sqlite`, which only changes on
account or watchlist edits).

## Update what's running

```powershell
git -C C:\Users\tgpet\Projects\Moonwalking-Runtime fetch
git -C C:\Users\tgpet\Projects\Moonwalking-Runtime merge --ff-only <branch-or-commit>
cd C:\Users\tgpet\Projects\Moonwalking-Runtime\frontend; npm ci; npm run build
# Restart Python only; the launcher brings it straight back on the new code.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.ExecutablePath -like "$env:USERPROFILE\.moonwalking\venv\*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

If `requirements.txt` changed, update the runtime venv first:
`& $env:USERPROFILE\.moonwalking\venv\Scripts\python.exe -m pip install -r backend\requirements.txt`.

Changes to `run_collector.ps1` itself only take effect when the launcher
restarts: `Stop-ScheduledTask`, stop the Python process as above, then
`Start-ScheduledTask -TaskName 'Moonwalking Collector'`.

## Install or repair the task

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\tgpet\Projects\Moonwalking-Runtime\scripts\windows\install_collector_task.ps1
Start-ScheduledTask -TaskName 'Moonwalking Collector'
```

## Limits

- **Sleep pauses collection.** Task Scheduler can't collect while the PC is
  asleep; Python resumes on wake. Whether the PC sleeps is a power-settings
  decision for Tom.
- **It runs while Tom is logged on.** The task uses the interactive logon, so
  it starts at logon and stops at sign-out. Running with nobody logged on
  would need a stored password, which an AI session must not handle.
- **Secrets.** The runtime worktree has no `backend/.env`. Public market
  collection doesn't need one, but Coinbase sign-in, OAuth and a stable
  session key on port 5003 do. Setting that up is Tom's call.
- **Gaps stay gaps.** Anything rebuilt for a period the collector wasn't
  running (e.g. from exchange candles) must be labelled as replayed with its
  own methodology version, never mixed silently with live rows.
