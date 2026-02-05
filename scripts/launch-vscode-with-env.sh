#!/usr/bin/env bash
set -euo pipefail

# Launch VS Code with environment variables loaded from a local .env file
# Usage: ./scripts/launch-vscode-with-env.sh [path]

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
  echo "Loading environment from $ENV_FILE"
  # Export all variables from .env (simple approach). Keep .env out of git.
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "No .env found at $ENV_FILE — launching without loading env file"
fi

# Launch VS Code so the GUI process inherits the environment we just exported
exec code "${1:-$REPO_ROOT}"
