#!/usr/bin/env bash
set -euo pipefail

# Helper: create/switch to branch 9030, stage all changes, commit (if any), and push
# Safe to run multiple times.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH=9030
MSG="first commit"

echo "Repo: $REPO_ROOT"
current_branch=$(git rev-parse --abbrev-ref HEAD || echo "(no branch)")
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  echo "Checking out existing branch $BRANCH"
  git checkout "$BRANCH"
else
  echo "Creating and switching to branch $BRANCH"
  git checkout -b "$BRANCH"
fi

echo "Staging all changes..."
git add -A

if git diff --cached --quiet; then
  echo "No changes to commit. (Nothing staged)"
else
  echo "Committing with message: $MSG"
  git commit -m "$MSG"
fi

echo "Pushing branch $BRANCH to origin..."
# Attempt to push; if push fails, show remote info for debugging
if git push -u origin "$BRANCH"; then
  echo "Pushed branch $BRANCH to origin successfully."
else
  echo "Push failed. Showing 'git remote -v':";
  git remote -v
  echo "Please check your git permissions/remotes and try again."
  exit 1
fi

echo "Done. Current branch: $(git rev-parse --abbrev-ref HEAD)"
