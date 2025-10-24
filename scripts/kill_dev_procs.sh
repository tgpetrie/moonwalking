#!/usr/bin/env bash
set -euo pipefail
PATTERNS=("vite" "node .*vite" "flask run" "gunicorn .*app:app" "python .*app.py" "uvicorn")
for pat in "${PATTERNS[@]}"; do pkill -f "$pat" 2>/dev/null || true; done
echo "[+] Dev processes terminated (best effort)."
