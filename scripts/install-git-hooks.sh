#!/usr/bin/env bash
set -euo pipefail

# Installs tracked hooks from .githooks/ into .git/hooks/
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$ROOT_DIR/.githooks"
GIT_HOOKS_DIR="$ROOT_DIR/.git/hooks"

if [ ! -d "$ROOT_DIR/.git" ]; then
  echo "[install-git-hooks] Not a git repository; cannot install hooks." >&2
  exit 1
fi

if [ ! -d "$HOOKS_DIR" ]; then
  echo "[install-git-hooks] No .githooks directory found; nothing to install." >&2
  exit 0
fi

echo "[install-git-hooks] Installing hooks from $HOOKS_DIR to $GIT_HOOKS_DIR"
mkdir -p "$GIT_HOOKS_DIR"
for hook in "$HOOKS_DIR"/*; do
  name=$(basename "$hook")
  dest="$GIT_HOOKS_DIR/$name"
  echo " - installing $name"
  cp "$hook" "$dest"
  chmod +x "$dest"
done

echo "[install-git-hooks] Done."
exit 0
