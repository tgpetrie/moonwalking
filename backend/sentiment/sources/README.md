# Sentiment Source Catalog

This folder keeps the reproducible list of upstream inputs that power the `/sentiment/latest` API.
Each JSON file represents one tier and contains a versioned object with a `sources` array. The loader
stitches all files together at runtime so the backend never depends on secrets or files that live
outside the repo.

## Files

- `tier1.json` – implemented public/official market-wide and local market-data sources.
- `tier2.json` – implemented coin-context providers used by `/api/coin-intel`.
- `tier3.json` – optional credentialed social providers; these must report unavailable until configured.
- `fringe.json` – intentionally empty. Scraping/noisy boards are not part of the current supported product contract.

## Schema (v1)

Top-level file shape:

```json
{
  "schema_version": 1,
  "tier": "tier1 | tier2 | tier3 | fringe",
  "sources": [ /* array of source objects */ ]
}
```

Source object keys:

| key                 | type        | required | notes |
|---------------------|-------------|----------|-------|
| `name`              | string      | yes      | Human label used in the UI |
| `description`       | string      | yes      | Short explanation for docs/tooltips |
| `tier`              | string      | no       | Defaults to the file name (tier1, tier2, tier3, fringe) |
| `weight`            | number      | yes      | Trust weighting used by the engine |
| `update_frequency`  | number      | yes      | Seconds between refreshes |
| `type`              | string      | yes      | `api`, `rss`, etc. Do not add scrape/social sources unless a compliant provider implementation exists. |
| `endpoint`/`subreddit`/`channels` | varies | optional | Transport-specific config |
| `region`            | string      | optional | Use ISO country codes if applicable |
| `coverage`          | array       | optional | List of tickers, sectors, or tags |
| `documentation`     | string      | recommended | Primary documentation URL |
| `access`            | string      | recommended | `free_public`, `free_public_demo_or_pro_key`, `requires_api_key`, etc. |
| `implemented`       | boolean     | recommended | Whether production code currently fetches this source |
| `scope`             | string      | recommended | `market_wide`, `local_price_tape`, `coin_context`, or `coin_context_social` |

Catalog entries are not active coverage by themselves. A source only counts as active coverage when a backend provider contributes live or stale data with provenance in the API response.

Unknown schema versions are rejected by the loader so we can evolve the shape safely later. The
loader is forgiving about additional keys: they are passed through untouched so future pipelines can
extend the metadata without touching the callers.

## Adding a new source

1. Pick the right file for the trust tier.
2. Add your source to the `sources` array following the schema above.
3. Commit the change along with any pipeline adjustments.

The FastAPI service will automatically expose the new source counts and metadata on the next boot.
