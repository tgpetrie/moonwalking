#!/usr/bin/env bash
set -euo pipefail

# restore_ui.sh
# Backup selected frontend assets, restore UI files from a backup branch,
# and (optionally) restart the dev environment.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
branch="fingers-backup-97105a0"
stamp="$(date +%Y%m%d_%H%M%S)"
backup_dir="$repo_root/backups_ui_$stamp"

echo "[restore_ui] repo_root=$repo_root"
echo "[restore_ui] branch=$branch"
echo "[restore_ui] creating backup dir $backup_dir"
mkdir -p "$backup_dir"

echo "[restore_ui] backing up existing frontend files (if present)"
cp -a "$repo_root/frontend/public" "$backup_dir/public" 2>/dev/null || true
cp -a "$repo_root/frontend/src/index.css" "$backup_dir/index.css" 2>/dev/null || true
cp -a "$repo_root/frontend/src/app.jsx" "$backup_dir/app.jsx" 2>/dev/null || true
cp -a "$repo_root/frontend/src/components" "$backup_dir/components" 2>/dev/null || true

echo "[restore_ui] verifying backup branch exists..."
if ! git -C "$repo_root" rev-parse --verify --quiet "$branch" >/dev/null; then
  echo "[restore_ui] ERROR: branch '$branch' not found in repository at $repo_root"
  echo "[restore_ui] aborting; backup kept at $backup_dir"
  exit 1
fi

echo "[restore_ui] restoring files from branch '$branch' into working tree"
git -C "$repo_root" restore --source="$branch" --worktree -- \
  frontend/public \
  frontend/src/index.css \
  frontend/src/app.jsx \
  frontend/src/components/GainersTable1Min.jsx \
  frontend/src/components/GainersTable.jsx \
  frontend/src/components/LosersTable.jsx \
  frontend/src/components/Watchlist.jsx \
  frontend/src/components/TopBannerScroll.jsx \
  frontend/src/components/BottomBannerScroll.jsx \
  frontend/src/components/AlertsIndicator.jsx \
  frontend/src/components/TopMoversBar.jsx

echo "[restore_ui] restore complete. Backup directory: $backup_dir"

if [ -x "$repo_root/scripts/restart_dev.sh" ]; then
  echo "[restore_ui] launching $repo_root/scripts/restart_dev.sh to restart dev servers"
  "$repo_root/scripts/restart_dev.sh"
else
  echo "[restore_ui] notice: $repo_root/scripts/restart_dev.sh not present or not executable."
  echo "[restore_ui] To restart dev servers, run:"
  echo "    $repo_root/scripts/restart_dev.sh"
fi

echo "[restore_ui] done"
