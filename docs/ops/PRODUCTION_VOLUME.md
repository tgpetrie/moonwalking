# Production volume: keeping it from filling

Railway Hobby caps a volume at 5 GB. On 2026-10-18 the production volume
(`/var/lib/moonwalking`, 4.6 GB) was 100% full: 28 MB free.

| File | Size | Why it grew |
|---|---|---|
| `signal_outcomes.sqlite` | 2.4 GB | ~1.1 GB of it is `feature_snapshot_json`, write-only research context; also holds `board_outcomes_v2` |
| `control_dry_run.sqlite` | 2.3 GB | had no pruning at all |
| `price_snapshots`, `volume_1h` | ~40 MB each | pruned already |

Growth was about 26 MB/day. A bigger plan only delays the problem, so the code
now bounds itself (branch `claude/storage-retention`).

## What the code limits (environment variables)

| Variable | Default | Effect |
|---|---|---|
| `MW_FEATURE_SNAPSHOT_RETENTION_DAYS` | 14 | Blank `feature_snapshot_json` on **finished** signal and board rows older than this. Returns, outcomes and every published statistic are unchanged (nothing reads the JSON back). `0` disables. |
| `MW_CONTROL_DRY_RUN_RETENTION_DAYS` | 30 | Delete dry-run observations older than this. `0` disables. |
| `MW_SIGNAL_OUTCOME_RETENTION_DAYS` | 0 (off) | Delete whole finished signal rows older than this (minimum 30). Off by default because the scorecard counts them. |
| `MW_BOARD_OUTCOME_RETENTION_DAYS` | 180 | Already existed. |

Clearing runs in batches of 20,000 rows once a minute, so the first catch-up
takes about an hour and never holds the write lock for long.

## One-time recovery (needs a person; production is changed)

Order matters. Do not delete anything before the backup is verified.

1. **Back up** (read-only on production):
   `.\scripts\prod_backup.ps1 -Files control_dry_run`
   Confirm it prints `integrity: ok`.
2. **Move the dry-run store to a fresh file.** In Railway, Variables: set
   `MW_CONTROL_DRY_RUN_DB=/var/lib/moonwalking/control_dry_run_v2.sqlite` (if a
   different path is already set there, keep its folder and change only the
   file name). Railway redeploys. Wait for `/api/health` to return ok.
   The dry-run report restarts from zero; history is in the backup.
3. **Free the space.** Once healthy, remove the old file and its sidecars:
   `railway ssh -i <key> -- sh -c 'rm -f /var/lib/moonwalking/control_dry_run.sqlite*'`
   then `railway ssh -i <key> -- df -h /var/lib/moonwalking` should show about 2.3 GB free.
4. **Deploy the retention code** (this branch). After about an hour the old
   feature snapshots are cleared and the file stops growing for weeks.

Headroom after step 3 is roughly 2.3 GB at about 14 MB/day for signal rows
without snapshots, so months, and it plateaus once the limits are running.

## Check it worked

`df -h /var/lib/moonwalking` stays well under 100%, and
`signal_outcomes.sqlite` stops growing day over day. If either is not true,
lower `MW_FEATURE_SNAPSHOT_RETENTION_DAYS` or set
`MW_SIGNAL_OUTCOME_RETENTION_DAYS`.
