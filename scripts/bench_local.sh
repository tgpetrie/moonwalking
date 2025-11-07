#!/usr/bin/env bash
set -euo pipefail

PROMPT_SHORT="Summarize BHABIT dashboard layout in one sentence."
PROMPT_CODE="Write a single React function that trims '-USD' from a symbol and returns ticker-only."
MODELS=("phi3:mini" "qwen:1.5b" "llama3:8b")

run_test () {
  local model="$1" prompt="$2" label="$3"
  echo "---- ${label} on ${model} ----"
  local start
  start=$(python3 - <<'PY'
import time; print(int(time.time()*1000))
PY
)
  # Limit output to avoid huge dumps; stop on first ~1200 chars
  # (Ollama CLI doesn't always expose num_predict; keep it readable.)
  if ! command -v ollama >/dev/null 2>&1; then
    echo "ollama not found on PATH; skipping run." >&2
    return 0
  fi
  ollama run "$model" -p "$prompt" | head -c 1200 || true
  echo
  local end
  end=$(python3 - <<'PY'
import time; print(int(time.time()*1000))
PY
)
  echo "Elapsed: $((end - start)) ms"
  echo
}

echo "🔎 Checking local models..."
for m in "${MODELS[@]}"; do
  if ! command -v ollama >/dev/null 2>&1; then
    echo "  • Ollama CLI not found — install from https://ollama.ai and retry."
    break
  fi
  if ! ollama list | awk '{print $1}' | grep -q "^${m}$"; then
    echo "  • Missing $m — skipping"
    continue
  fi
  run_test "$m" "$PROMPT_SHORT" "Short"
  run_test "$m" "$PROMPT_CODE" "Code"
done
echo "✅ Done."
