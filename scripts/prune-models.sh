#!/usr/bin/env bash
set -euo pipefail

# Prune Ollama models by size threshold or interactive selection.
# Usage:
#   ./scripts/prune-models.sh            # lists models and prompts for removal interactively
#   ./scripts/prune-models.sh --threshold 2000   # removes models larger than 2000 MB after confirm

THRESHOLD_MB=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --threshold)
      THRESHOLD_MB="$2"; shift 2;;
    -y|--yes)
      AUTO_YES=1; shift;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

echo "Fetching installed Ollama models..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama CLI not found on PATH. Install Ollama and retry." >&2
  exit 1
fi

# Print table: NAME, SIZE_MB, MODIFIED
ollama list --no-trunc | awk 'NR==1{next} {print $0}'

if [[ "$THRESHOLD_MB" -gt 0 ]]; then
  echo "\nPruning models larger than ${THRESHOLD_MB} MB"
  # Loop through model names and sizes
  ollama list | tail -n +2 | while read -r name id size rest; do
    # Size may be human-readable; reuse ollama inspect if available
    size_bytes=$(ollama inspect "$name" 2>/dev/null | grep -i 'size' | head -n1 | awk '{print $2}' || echo 0)
    # If size_bytes not numeric, skip
    if [[ "$size_bytes" =~ ^[0-9]+$ ]]; then
      size_mb=$((size_bytes/1024/1024))
    else
      size_mb=0
    fi
    if [[ "$size_mb" -ge "$THRESHOLD_MB" ]]; then
      echo "Will remove $name ($size_mb MB)"
      if [[ -n "${AUTO_YES:-}" ]]; then
        ollama rm "$name"
      else
        read -rp "Remove $name ($size_mb MB)? [y/N] " yn
        if [[ "$yn" =~ ^[Yy] ]]; then
          ollama rm "$name"
        fi
      fi
    fi
  done
  exit 0
fi

echo "Interactive prune — choose models to remove." 
echo "Run with --threshold <MB> to auto-select by size."
while true; do
  echo
  ollama list
  echo
  read -rp "Enter exact model name to remove (or blank to exit): " mdl
  if [[ -z "$mdl" ]]; then
    echo "Done."; exit 0
  fi
  read -rp "Confirm remove $mdl? [y/N] " yn
  if [[ "$yn" =~ ^[Yy] ]]; then
    ollama rm "$mdl"
  fi
done
