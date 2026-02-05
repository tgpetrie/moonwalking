#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-moonwalkings}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
OUTDIR="dist/snap_${STAMP}"
mkdir -p "$OUTDIR"

# Detect git
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_SHA="$(git rev-parse --short HEAD || echo nogit)"
  GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD || echo nogit)"
else
  GIT_SHA="nogit"
  GIT_BRANCH="nogit"
fi

# -----------------------------
# 0) Snapshot manifest
# -----------------------------
cat > "$OUTDIR/MANIFEST.txt" <<EOF
Project: $PROJECT_NAME
Created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Git SHA: $GIT_SHA
Branch : $GIT_BRANCH
Host   : $(whoami)@$(hostname)
EOF

# -----------------------------
# 1) Working tree snapshot (no vendor)
#    - Includes untracked files
#    - Excludes heavy dirs by default
# -----------------------------
STAGE1=".snapshot_stage_1"
rm -rf "$STAGE1"; mkdir -p "$STAGE1"
# Allow the caller to include vendor folders via environment variables:
# - INCLUDE_VENDOR=true  => include both .venv and node_modules in the working-tree zip
# - INCLUDE_VENV=true    => include .venv (useful for Python-only reproducibility)
# - INCLUDE_NODE_MODULES=true => include node_modules
# Defaults: do NOT include vendor folders (they stay excluded to keep the snapshot small).
INCLUDE_VENDOR="${INCLUDE_VENDOR:-false}"
INCLUDE_VENV="${INCLUDE_VENV:-false}"
INCLUDE_NODE_MODULES="${INCLUDE_NODE_MODULES:-false}"

# If INCLUDE_VENDOR is true, turn on both
if [ "$INCLUDE_VENDOR" = "true" ]; then
  INCLUDE_VENV=true
  INCLUDE_NODE_MODULES=true
fi

EXCLUDES=(
  --exclude '.git'
  --exclude '.gitignore'
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '*.log'
  --exclude '.DS_Store'
  --exclude 'frontend/dist'
  --exclude '.cache'
  --exclude '.vite'
  --exclude '*/.vite'
  --exclude '.pytest_cache'
)

# Conditionally exclude node_modules and .venv unless the corresponding INCLUDE_* is true
if [ "$INCLUDE_NODE_MODULES" != "true" ]; then
  EXCLUDES+=( --exclude 'node_modules' --exclude '*/node_modules' )
fi
if [ "$INCLUDE_VENV" != "true" ]; then
  EXCLUDES+=( --exclude '.venv' --exclude 'venv' )
fi
# shellcheck disable=SC2068
rsync -a --delete ${EXCLUDES[@]} ./ "$STAGE1/"

echo "== creating working-tree archive (zip preferred, tar.gz fallback) =="
if zip -qr9 "$OUTDIR/${PROJECT_NAME}_working_tree_${STAMP}_${GIT_SHA}.zip" -x '*.zip' -x '*.zip.sha256' -x 'dist/*' "$STAGE1"/* 2>/dev/null; then
  echo "-> created $OUTDIR/${PROJECT_NAME}_working_tree_${STAMP}_${GIT_SHA}.zip"
else
  echo "zip failed, falling back to tar.gz"
  tar -C "$STAGE1" -czf "$OUTDIR/${PROJECT_NAME}_working_tree_${STAMP}_${GIT_SHA}.tar.gz" .
  echo "-> created $OUTDIR/${PROJECT_NAME}_working_tree_${STAMP}_${GIT_SHA}.tar.gz"
fi
rm -rf "$STAGE1"

# -----------------------------
# 2) Working tree FULL (with vendor)
#    - Everything on disk except .git
#    - Big, but self-contained
# -----------------------------
STAGE2=".snapshot_stage_2"
rm -rf "$STAGE2"; mkdir -p "$STAGE2"
rsync -a --delete --exclude '.git' ./ "$STAGE2/"

echo "== creating working-tree FULL archive (zip preferred, tar.gz fallback) =="
if zip -qr9 "$OUTDIR/${PROJECT_NAME}_working_tree_FULL_${STAMP}_${GIT_SHA}.zip" -x '*.zip' -x '*.zip.sha256' -x 'dist/*' "$STAGE2"/* 2>/dev/null; then
  echo "-> created $OUTDIR/${PROJECT_NAME}_working_tree_FULL_${STAMP}_${GIT_SHA}.zip"
else
  echo "zip failed, falling back to tar.gz"
  tar -C "$STAGE2" -czf "$OUTDIR/${PROJECT_NAME}_working_tree_FULL_${STAMP}_${GIT_SHA}.tar.gz" .
  echo "-> created $OUTDIR/${PROJECT_NAME}_working_tree_FULL_${STAMP}_${GIT_SHA}.tar.gz"
fi
rm -rf "$STAGE2"

# -----------------------------
# 3) Git bundle (history, branches, tags)
#    - Single-file, can be cloned later
# -----------------------------
if [ "$GIT_SHA" != "nogit" ]; then
  git bundle create "$OUTDIR/${PROJECT_NAME}_repo_${STAMP}_${GIT_SHA}.bundle" --all
fi

# -----------------------------
# 4) Git mirror tarball (alt to bundle)
#    - A bare mirror of .git directory
# -----------------------------
if [ "$GIT_SHA" != "nogit" ]; then
  TMP_MIRROR=".snapshot_mirror"
  rm -rf "$TMP_MIRROR"
  git clone --mirror . "$TMP_MIRROR" >/dev/null 2>&1
  tar -C "$TMP_MIRROR" -czf "$OUTDIR/${PROJECT_NAME}_repo_mirror_${STAMP}_${GIT_SHA}.tar.gz" .
  rm -rf "$TMP_MIRROR"
fi

# -----------------------------
# 5) Dependency lock capture (for rebuild)
# -----------------------------
{
  [ -f "frontend/package.json" ] && echo "== frontend/package.json ==" && cat frontend/package.json
  [ -f "frontend/package-lock.json" ] && echo "== frontend/package-lock.json ==" && cat frontend/package-lock.json
  [ -f "frontend/pnpm-lock.yaml" ] && echo "== frontend/pnpm-lock.yaml ==" && cat frontend/pnpm-lock.yaml
  [ -f "requirements.txt" ] && echo "== requirements.txt ==" && cat requirements.txt
  [ -f "backend/requirements.txt" ] && echo "== backend/requirements.txt ==" && cat backend/requirements.txt
} > "$OUTDIR/LOCKS.txt" || true

# -----------------------------
# 6) File inventory (so you can verify)
# -----------------------------
find . -maxdepth 6 -not -path './.git/*' -not -path './dist/*' -print | LC_ALL=C sort > "$OUTDIR/FILELIST.txt"

# -----------------------------
# 7) Checksums
# -----------------------------
( cd "$OUTDIR" && for f in *; do [ -f "$f" ] && shasum -a 256 "$f" > "$f.sha256"; done )

echo
echo "✅ Snapshot complete → $OUTDIR"
ls -lh "$OUTDIR" | sed '1d'
