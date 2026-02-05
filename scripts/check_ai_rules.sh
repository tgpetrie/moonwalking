#!/usr/bin/env bash
set -euo pipefail

# Lightweight enforcement: prevent starting local dev when on an "AI" branch
# unless only files under docs/ai/ have been changed (staged, unstaged, untracked, or committed).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[check_ai_rules] Not a git repo — skipping AI-branch enforcement."
  exit 0
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ -z "$BRANCH" ]; then
  echo "[check_ai_rules] Could not determine git branch — skipping enforcement."
  exit 0
fi

# Detect AI-style branch names: prefix 'ai', or path segment '-ai-' or '/ai/' or 'ai-' at start.
if ! echo "$BRANCH" | grep -Ei '(^ai$|^ai[-_/]|[-_/]ai[-_/]|[-_/]ai$|/ai/)' >/dev/null; then
  # Not an AI branch — nothing to enforce
  exit 0
fi

echo "[check_ai_rules] Detected AI branch: '$BRANCH' — enforcing docs-only change rule."

# Gather changed files: untracked, staged, unstaged, and committed differences against main
changed_files=()

# untracked
while IFS= read -r f; do
  changed_files+=("$f")
done < <(git ls-files --others --exclude-standard)

# unstaged
while IFS= read -r f; do
  changed_files+=("$f")
done < <(git diff --name-only)

# staged
while IFS= read -r f; do
  changed_files+=("$f")
done < <(git diff --name-only --cached)

# committed vs main (if main exists)
if git show-ref --verify --quiet refs/heads/main; then
  base=$(git merge-base HEAD main)
  while IFS= read -r f; do
    changed_files+=("$f")
  done < <(git diff --name-only "$base"..HEAD)
elif git ls-remote --heads origin main >/dev/null 2>&1; then
  # try comparing to origin/main
  base=$(git merge-base HEAD origin/main || true)
  if [ -n "$base" ]; then
    while IFS= read -r f; do
      changed_files+=("$f")
    done < <(git diff --name-only "$base"..HEAD)
  fi
fi

# Deduplicate
unique_files=()
declare -A seen
for f in "${changed_files[@]}"; do
  [ -z "$f" ] && continue
  if [ -z "${seen[$f]:-}" ]; then
    seen[$f]=1
    unique_files+=("$f")
  fi
done

if [ ${#unique_files[@]} -eq 0 ]; then
  echo "[check_ai_rules] No changed files detected — nothing to enforce."
  exit 0
fi

offenders=()
for f in "${unique_files[@]}"; do
  # allow files under docs/ai/
  case "$f" in
    docs/ai/*) ;; # allowed
    docs/ai) ;;
    docs/*.md) ;; # allow top-level docs markdown edits (e.g., FRONTEND_UI_RULES.md)
    # deny others
    *) offenders+=("$f") ;;
  esac
done

if [ ${#offenders[@]} -gt 0 ]; then
  echo "[check_ai_rules] ERROR: AI branch may only change files under 'docs/ai/'. Found other changes:" >&2
  for o in "${offenders[@]}"; do
    echo "  - $o" >&2
  done
  echo "Aborting start. Commit or move non-doc changes to a non-AI branch, or rename branch." >&2
  exit 2
fi

echo "[check_ai_rules] Only docs/ai changes detected — OK to proceed."
exit 0
