# Ask Bhabit Backend Contract

Scope: first validation loop only. Public market evidence is separate from private
position and thesis context. Missing values are `null`, never `0`.

## Endpoints

- `GET /api/ask-bhabit/position`
- `POST|PUT|PATCH /api/ask-bhabit/position`
- `GET /api/ask-bhabit/thesis`
- `POST|PUT|PATCH /api/ask-bhabit/thesis`
- `GET /api/ask-bhabit/evidence`
- `POST /api/ask-bhabit/analyze`
- `GET /api/ask-bhabit/analysis/latest`
- `GET /api/ask-bhabit/snapshots`
- `GET /api/ask-bhabit/what-changed`

All responses use:

```json
{
  "success": true,
  "data": {}
}
```

Errors use:

```json
{
  "success": false,
  "error": {
    "code": "position_required",
    "message": "Create a manual position first."
  }
}
```

## Manual Position Payload

```json
{
  "asset_id": "SOL",
  "quantity": 2.5,
  "entry_price": 125.4,
  "total_cost_basis": 313.5,
  "acquisition_date": "2026-07-01",
  "note": "Manual beta position"
}
```

`entry_price` or `total_cost_basis` is enough. If both are present, the backend
preserves both.

## Thesis Payload

```json
{
  "why_entered": "Solana app activity is improving.",
  "reconsider_if": "Fees or active users roll over for multiple weeks.",
  "time_horizon": "weeks",
  "tags": ["infra", "beta"]
}
```

All thesis fields are optional.

## Evidence Statuses

Every signal-like section supports:

- `available`
- `unavailable`
- `unsupported`
- `not_configured`
- `stale`
- `provider_error`
- `conflicting`

Frontend should display `missing_data_reason`, `provider_error`, `conflicts`,
`source`, `retrieved_at`, and `freshness` whenever present.

## Evidence Packet Shape

```json
{
  "packet_id": "evidence-...",
  "schema_version": "ask_bhabit.evidence.v1",
  "retrieved_at": "2026-07-24T00:00:00Z",
  "asset_id": "solana:So11111111111111111111111111111111111111112",
  "asset_symbol": "SOL",
  "public_market_evidence": {
    "asset_identity": {},
    "price": {},
    "movement": {
      "short_window": {},
      "longer_window": {}
    },
    "volume_liquidity": {
      "volume": {},
      "liquidity": {}
    },
    "derivatives": {
      "funding": {},
      "open_interest": {},
      "liquidations": {},
      "trader_positioning": {}
    },
    "sentiment": {}
  },
  "private_context": {
    "position": {},
    "thesis": {}
  },
  "confidence": {
    "level": "low",
    "reasons": []
  }
}
```

Confidence levels are `high`, `medium`, `low`, and
`insufficient_evidence`. There is no percentage score.

## Analysis Snapshot

`POST /api/ask-bhabit/analyze` persists:

- `evidence_packet`
- deterministic `comparison`
- generated or unavailable `analysis`
- `position_ref`
- `thesis_ref`

When no founder/server LLM key is configured, `analysis.status` is
`not_configured`; the evidence packet and comparison are still saved.

## What Changed

`GET /api/ask-bhabit/what-changed` returns deterministic categories:

- `only_price_changed`
- `market_structure_changed`
- `evidence_quality_changed`
- `thesis_evidence_changed`
- `insufficient_evidence`

It also returns numeric/status changes with `from`, `to`, and percent change
where meaningful.
