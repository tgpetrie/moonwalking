#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
DOC="$ROOT/docs/ai/AI_INDEX.md"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'dirty')"
DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf "\n\n_Repo_: \`%s\` • _SHA_: \`%s\` • _Updated_: \`%s\`\n" "$(basename "$ROOT")" "$SHA" "$DATE" >> "$DOC"
echo "Updated $DOC"
