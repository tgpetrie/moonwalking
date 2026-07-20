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
    - `pulse`: raw recent detector output for fast-scanner use
    - `signals`: symbol-grouped events with state evolution
    - `notify`: newly high-conviction or confirmed-risk event candidates
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
- `rule_version`
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
- `rule_version` (current executable rule-set identifier when missing)
- `evidence` (dict; default `{}`)

## Classification and thresholds

User-facing grouping and delivery are defined in `docs/ALERT_EVENT_EVOLUTION.md`. Detector output remains available and is not discarded when the event layer combines several detections.

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

## Operator meaning

Alerts should be treated as scan/attention signals. The UI translates alert families into quick-read trading intent:

| Alert family | UI intent | Notes |
|---|---|---|
| `moonshot`, `breakout`, `coin_squeeze_break`, `coin_persistent_gainer`, `coin_fomo` | `RECONFIRM` | Strong move, but high chase risk. Needs fresh hold/retest/volume. |
| `coin_breadth_thrust`, `coin_trend_break_up` | `BUY WATCH` | Better setup quality because breadth or trend structure supports the move. |
| `whale_move`, `stealth_move`, `coin_liquidity_shock` | `WATCH` | Participation/volume smoke before clean direction. Not a standalone buy signal. |
| `coin_fakeout`, `divergence`, `coin_exhaustion_*` | `NO CHASE` / `TRAP RISK` / `PROTECT` | Risk-control families. Avoid buying extension until reclaim. |
| `crater`, `dump`, `coin_breadth_failure`, `coin_trend_break_down`, `coin_persistent_loser`, `coin_reversal_down` | `AVOID LONG` | Downside pressure or failed support. |

The UI may downgrade a bullish family from `BUY WATCH` to `RECONFIRM` when freshness, volume, or breadth is missing. It must not promote proxy social data to real coin sentiment.

## Default threshold summary

These defaults are the current `v0.2-evolution-2026-07-14` rules. They describe executable behavior but have not been validated as optimal through a recorded forward-outcome backtest. The proposed relative calibration layer is documented in `docs/SIGNAL_SYSTEM_V1_PROPOSAL.md`.

Every canonical alert exposes this identifier as `rule_version`. A future threshold or detector-definition change must publish a new identifier rather than silently changing the meaning of an existing version.

These are current defaults from `DEFAULT_THRESHOLDS`:

| Key | Default |
|---|---:|
| `moonshot_1m_pct` | `1.00` |
| `moonshot_3m_pct` | `2.60` |
| `breakout_1m_pct` | `0.55` |
| `breakout_3m_pct` | `1.90` |
| `impulse_1m_pct` | `1.25` |
| `impulse_3m_pct` | `2.0` |
| `whale_z_score` | `3.0` |
| `whale_cluster_z` | `2.5` |
| `whale_candle_pct` | `0.3` |
| `whale_surge_1h_pct` | `150.0` |
| `whale_min_quote_1m_usd` / `whale_min_quote_cluster_usd` | `$25,000` / `$50,000` |
| `whale_min_quote_1h_usd` | `$250,000` |
| `stealth_vol_min_pct` | `110.0` |
| `stealth_price_max_abs_pct` | `1.2` |
| `divergence_1m_threshold` / `divergence_3m_threshold` | `0.65` |
| `coin_fomo_mpi_min` | `72` |
| `coin_fomo_pct3m_min` / `coin_fomo_pct1m_min` | `1.8` / `0.6` |
| `coin_thrust_breadth_min` | `0.65` |
| `coin_failure_breadth_max` | `0.35` |
| `persist_min_streak` | `3` |
| `liq_shock_z_min` | `2.6` |
| `liq_shock_min_latest_quote_usd` | `$10,000` |
| `squeeze_break_pct_1m_min` | `0.8` |
| `exhaustion_min_streak` | `4` |
| `alerts_max_total` / `alerts_max_per_symbol` | `24` / `2` |

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

## Remaining v0.2 limitations

- Fixed percent thresholds are not adjusted to per-asset volatility or liquidity.
- USD notional gates are bootstrap values pending historical calibration by liquidity cohort.
- The engine now samples return-history and EMA detectors once per wall-clock minute, but full recorded replay remains required to validate their thresholds.
- Full-universe 1m/3m returns now feed breadth before board selection; stablecoin/wrapped-asset cohort exclusions remain to be formalized.
- Alert expiry is canonical when supplied; legacy alerts without expiry still use the endpoint fallback TTL.
- Browser notifications require explicit user opt-in and are available only while a compatible browser profile permits them; they are not a native mobile push service.
- Email, Telegram, and Discord delivery require channel credentials and remain disabled by default.
- Raw detector telemetry remains intentionally frequent and is exposed as `pulse`; only grouped, confidence-gated event transitions enter `notify`.

## Changelog notes

When updating thresholds or schema fields, add a short note here with:

- Date
- What changed
- Why
- Expected impact on alert mix/noise
