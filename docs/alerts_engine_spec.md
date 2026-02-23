# Alerts Engine Spec (Runtime Source: `backend/alerts_engine.py`)

This document describes alert behavior and payload contracts used by the UI.
The executable source of truth is `backend/alerts_engine.py`, wired from `backend/app.py`.

## Runtime topology

- Frontend renders alerts:
  - `frontend/src/components/SentimentPopupAdvanced.jsx`
  - `frontend/src/components/AlertsTab.jsx`
- Backend computes alerts:
  - `backend/alerts_engine.py`
  - Called from `backend/app.py` via `compute_alerts(..., include_impulse=True)`

## Where alerts are emitted

- `/api/alerts`
  - Canonical contract endpoint.
  - Returns:
    - `active`: deduped/ranked active alerts within TTL window
    - `recent`: recent stream items
    - `meta`: stream/input freshness metadata
- `/api/alerts/recent`
  - Returns `{ count, limit, alerts, meta }`.
- `/data`
  - Includes `alerts` in the combined payload for dashboard consumers.

## Alert contract

### Engine-produced shape (from `backend/alerts_engine.py`)

Each alert emitted by `_make_alert(...)` includes:

- `id`
- `ts`, `ts_ms`
- `event_ts`, `event_ts_ms`
- `symbol` (product-style, e.g. `PEPE-USD`)
- `type` (e.g. `moonshot`, `whale_move`, `breakout`)
- `severity` (e.g. `critical`, `high`, `medium`, `low`, `info`)
- `title`
- `message`
- `direction`
- `evidence` (dict)
- `ttl_seconds`
- `expires_at`
- `trade_url`

### Stream-boundary normalization (in `backend/app.py`)

`_ensure_alert_contract(...)` canonicalizes stream alerts and guarantees at least:

- `symbol`
- `type_key` (lowercase; derived from `type` when missing)
- `severity` (lowercase; default `info`)
- `event_ts_ms` (int; synthesized if missing)
- `id` (synthesized if missing)
- `evidence` (dict; default `{}`)

## Classification and thresholds

Core families (Coinbase-only):

- `whale_move`
- `stealth_move`
- `moonshot`
- `crater`
- `breakout`
- `dump`
- `divergence`
- `fomo_alert`
- `fear_alert`

Thresholds and cooldown/dedupe parameters live in:

- `backend/alerts_engine.py` (`DEFAULT_THRESHOLDS`)

## Cooldown / dedupe

Engine-level dedupe:

- In-process state via `AlertEngineState.last_fired`
- Per-key cooldowns + dedupe delta + direction flip allowance

Stream-level dedupe:

- Final boundary dedupe in `backend/app.py` (`_append_alerts_deduped`, `_alert_stream_key`)

## UI contract guidance

- UI should classify/render from structured fields (`type`, `type_key`, `severity`, `symbol`, `event_ts_ms`, `evidence`), not by parsing message text.
- `message` is presentation text and may change without contract changes.
- Numeric evidence should remain numeric when present (no string parsing requirement in UI).

## Validation endpoint

- `/api/alerts/proof`
  - Validates engine-family evidence presence.
  - Tri-state:
    - `state = warming` when no engine-family alerts yet (`ok = null`)
    - `state = pass` when engine-family alerts have required evidence
    - `state = fail` when evidence is missing

## Testing expectations

- Fixed snapshots -> deterministic outputs.
- Boundary tests around thresholds (below / at / above).
- Contract tests ensure required fields survive normalization.

## Changelog notes

When updating thresholds or schema fields, add a short note here with:

- Date
- What changed
- Why
- Expected impact on alert mix/noise
