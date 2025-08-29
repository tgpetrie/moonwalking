#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m venv .venv
source .venv/bin/activate
# If requirements.txt exists, install it
if [[ -f requirements.txt ]]; then pip install -r requirements.txt; fi
# Prefer flask app if available, otherwise app.py
if [[ -f app.py ]]; then
  export FLASK_APP=app:app
  flask --debug run --port 5001 || python app.py
else
  echo "No app.py found in backend/"
  exit 1
fi
