#!/bin/sh
set -eu

DATA_DIR="${RAILWAY_VOLUME_MOUNT_PATH:-${MW_DATA_DIR:-/var/lib/moonwalking}}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R moonwalking:moonwalking "$DATA_DIR"
  exec gosu moonwalking "$0" "$@"
fi

mkdir -p "$DATA_DIR"

export WATCHLIST_DB_PATH="${WATCHLIST_DB_PATH:-$DATA_DIR/watchlists.sqlite}"
export MOONWALKING_PRICE_DB="${MOONWALKING_PRICE_DB:-$DATA_DIR/price_snapshots.sqlite}"
export MW_VOLUME_1H_DB="${MW_VOLUME_1H_DB:-$DATA_DIR/volume_1h.sqlite}"
export MW_SIGNAL_OUTCOMES_DB="${MW_SIGNAL_OUTCOMES_DB:-$DATA_DIR/signal_outcomes.sqlite}"
export MW_BOARD_OUTCOMES_DB="${MW_BOARD_OUTCOMES_DB:-$DATA_DIR/signal_outcomes.sqlite}"
export MW_CONTROL_DRY_RUN_DB="${MW_CONTROL_DRY_RUN_DB:-$DATA_DIR/control_dry_run.sqlite}"
export PRICE_DB_RETENTION_SECONDS="${PRICE_DB_RETENTION_SECONDS:-86400}"
export SENTIMENT_HOST="127.0.0.1"
export SENTIMENT_PORT="${SENTIMENT_PORT:-8003}"

cd /app
python -m backend.sentiment_api \
  --host "$SENTIMENT_HOST" \
  --port "$SENTIMENT_PORT" \
  --log-level "${SENTIMENT_LOG_LEVEL:-warning}" &

cd /app/backend
exec gunicorn app:app \
  --bind "0.0.0.0:${PORT:-5003}" \
  --workers 1 \
  --threads "${GUNICORN_THREADS:-8}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
