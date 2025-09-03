#!/usr/bin/env bash
# Codemod: replace fragile Tailwind palette classes with locked color utilities
# Usage: from repo root: ./scripts/lock-colors-codemod.sh
set -euo pipefail

# Map of patterns -> replacements (simple sed-friendly mapping)
declare -A MAP=(
  ["text-cyan-400"]="text-lock-aqua"
  ["text-teal-400"]="text-lock-teal"
  ["text-pink-400"]="text-lock-pink"
  ["bg-cyan-400"]="bg-lock-aqua"
  ["bg-teal-400"]="bg-lock-teal"
  ["bg-pink-400"]="bg-lock-pink"
  ["text-blue-900"]="text-lock-blue-dark"
  ["bg-blue-900"]="bg-lock-blue-dark"
)

FILES=$(rg --hidden --glob '!node_modules' --glob '!dist' -l "text-(cyan|teal|pink|blue)-[0-9]{2,3}|bg-(cyan|teal|pink|blue)-[0-9]{2,3}" || true)
if [ -z "$FILES" ]; then
  echo "No matching files found."
  exit 0
fi

echo "Patching ${#MAP[@]} token mappings across files..."
for f in $FILES; do
  tmp="$f.tmp"
  cp "$f" "$tmp"
  for k in "${!MAP[@]}"; do
    sed -i '' "s/${k}/${MAP[$k]}/g" "$tmp" || true
  done
  mv "$tmp" "$f"
done

echo "Codemod completed. Run git status to review changes." 
*** End Patch
