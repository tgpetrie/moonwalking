# DATA_PIPELINES – CBMoovers / BHABIT Dashboard

Scope: Data contracts and fetching rules for the **home board**:

- 1h Price Change banner
- 1-min Gainers
- Top Gainers (3m)
- Top Losers (3m)
- Watchlist
- 1h Volume banner
- Sentiment / Info panel

If code disagrees with this document, **this document is correct**. Update the code, not the spec.

---

## 1. Backend Overview

The backend is a Flask app that:

- Polls public APIs on an interval (Coinbase REST, and optionally CoinGecko or others).
- Maintains rolling snapshots in memory to compute:
  - 1-minute price change
  - 3-minute price change
  - 1-hour price change
  - 1-hour volume change
- Exposes a normalized JSON payload via `/data` (canonical) and `/api/data` (alias).
- Exposes health status via `/api/health`.
- Optionally exposes sentiment endpoints for the info panel (see §5).

The board is **read-only** from the browser’s perspective: no writes from the SPA to the backend.

---

## 2. HTTP Endpoints

### 2.1 Health

- Method: `GET`
- Path: `/api/health`
- Returns: minimal JSON

```json
{
  "status": "ok"
}
```

Used only for smoke tests and basic monitoring.

⸻

2.2 Board Data (canonical + alias)

Two HTTP paths, one logical payload:
	•	Canonical (preferred, same-origin via Vite proxy):
	•	GET /data
	•	Alias / compatibility:
	•	GET /api/data → internally calls the same handler as /data.

The response is a single JSON object:

interface BoardData {
  // 1h banners
  banner_1h_price: BannerItem[];   // 1h price change
  banner_1h_volume: BannerItem[];  // 1h volume change

  // Core tables
  gainers_1m: WindowItem[];  // 1-min window
  gainers_3m: WindowItem[];  // 3-min gainers
  losers_3m: WindowItem[];   // 3-min losers (negative change_3m)

  // Latest snapshot per symbol (used for details / sentiment context)
  latest_by_symbol: {
    [symbol: string]: LatestSnapshot;
  };

  // Additional raw slices may exist (volume_1h, volume_1h_tokens, etc.).
  // Frontend must **not** read undocumented fields without updating this doc.
}

2.2.1 Types

interface BannerItem {
  symbol: string;          // e.g. "BTC-USD"
  name: string;            // human name, e.g. "Bitcoin"
  current_price: number;   // last trade price
  price_1h_ago?: number;   // optional, for 1h price banner
  volume_1h?: number;      // optional, for 1h volume banner
  change_1h: number;       // % change over 1 hour (positive or negative)
  rank: number;            // 1-based rank within the banner slice
  trade_url: string;       // Coinbase spot trade URL for the asset
}

interface WindowItem {
  symbol: string;          // consistent symbol key across payload
  name: string;

  current_price: number;   // last trade price

  // Window-specific historical anchors
  price_1m_ago?: number;   // for gainers_1m
  price_3m_ago?: number;   // for 3m slices

  change_1m?: number;      // % change over last 1 minute
  change_3m?: number;      // % change over last 3 minutes

  rank: number;            // 1-based, computed on backend
  trade_url: string;       // Coinbase price page URL
}

interface LatestSnapshot {
  symbol: string;
  name: string;
  current_price: number;
  last_updated: string;  // ISO timestamp
  volume_24h?: number;
  market_cap?: number;

  // Optional derivatives and metadata
  change_1m?: number;
  change_3m?: number;
  change_1h?: number;

  // Optional hooks for sentiment:
  base_asset?: string;   // e.g. "BTC"
  quote_asset?: string;  // e.g. "USD"
  coingecko_id?: string;
  funding_symbol?: string; // for futures funding lookup, if applicable

  trade_url: string;
}

Notes:
	•	The backend is responsible for computing rank in each slice.
	•	Change values MUST be numeric percentages, not formatted strings.
	•	The frontend is responsible for formatting (e.g. toFixed where appropriate).
	•	The frontend must not assume optional fields exist; it should defend against undefined.

⸻

3. Frontend Data Access

All data access for the board goes through two layers:
	1.	`frontend/src/api.js` – HTTP helper
	2.	`frontend/src/hooks/*` – SWR hooks

No table or component should call fetch directly.

3.1 API Helper (api.js)

Canonical helper for the board:

// Pseudocode, actual implementation may differ slightly
const API_BASE = ""; // relative – Vite proxy handles backend host/port

export async function fetchJson(path: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    credentials: "omit",
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`);
  }
  return res.json();
}

export async function fetchBoardData() {
  // Primary path
  try {
    return await fetchJson("/data");
  } catch (err) {
    // Fallback alias if configured: /api/data
    // Only used when explicitly enabled, do not reintroduce hard-coded hosts.
    return await fetchJson("/api/data");
  }
}

Rules:
	•	Use relative paths (/data, /api/data) so that:
	•	Dev: Vite proxy forwards to http://127.0.0.1:5001.
	•	Prod: same-origin path via reverse proxy (nginx, Caddy, Cloudflare, etc.).
	•	Do not hard-code http://127.0.0.1:5001 or any host/port in React components.

⸻

3.2 SWR Hooks

Primary hook for home board data (exact filename can vary):

// e.g. frontend/src/hooks/useBoardData.js
import useSWR from "swr";
import { fetchBoardData } from "../api";

export function useBoardData() {
  const { data, error, isLoading } = useSWR(
    "board-data",
    fetchBoardData,
    {
      refreshInterval: 10_000,   // 10s; can be tuned
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  return {
    data,
    error,
    isLoading,
  };
}

Rules:
	•	All board components (banners, 1m table, 3m tables, watchlist) must read from this hook (or the agreed canonical one, e.g. useDataFeed).
	•	Do not create per-component SWR keys that re-fetch the same payload.
	•	If the data shape is changed:
	•	Update this hook.
	•	Update DATA_PIPELINES.md.
	•	Update any tests.

⸻

4. How Each Board Section Maps to Data

4.1 1h Price Banner
	•	Component: BannerTicker or TopBannerScroll (depending on file names)
	•	Source: data.banner_1h_price: BannerItem[]

Display:
	•	Horizontal auto-scrolling chips.
	•	Each chip uses:
	•	rank (number, color-coded by sign of change_1h)
	•	symbol, name
	•	current_price
	•	change_1h (formatted to a suitable number of decimals)
	•	Chip click:
	•	Uses trade_url from BannerItem.

⸻

4.2 1-min Gainers
	•	Component: GainersTable1Min.jsx
	•	Source: data.gainers_1m: WindowItem[]

Rules:
	•	Layout:
	•	items.length <= 4 → one full-width table (see FRONTEND_UI_RULES.md).
	•	items.length > 4 → left/right two-column split, aligned with 3m losers.
	•	Fields:
	•	current_price → used as “now” price.
	•	price_1m_ago (if present) → used as previous price.
	•	change_1m → used for color/sign and value.
	•	rank → displayed in the first column.
	•	All rows rendered via TokenRow / AnimatedTokenRow with .bh-row grid.

Backend contract:
	•	Backend must ensure gainers_1m is sorted descending by change_1m.
	•	Backend may cap the list length (e.g. top N gainers); if so, document N here.

⸻

4.3 Top Gainers (3m) / Top Losers (3m)
	•	Components:
	•	GainersTable3Min.jsx
	•	Losers3m.jsx
	•	Sources:
	•	data.gainers_3m: WindowItem[]
	•	data.losers_3m: WindowItem[]

Rules:
	•	3m tables share a single .bh-board-row-halves wrapper.
	•	They both use .bh-row grid, same columns, same vertical rhythm.
	•	Fields:
	•	current_price
	•	price_3m_ago (if present)
	•	change_3m
	•	rank
	•	Backend:
	•	gainers_3m sorted descending by change_3m.
	•	losers_3m sorted ascending by change_3m (most negative first).

⸻

4.4 Watchlist
	•	Component: WatchlistPanel.jsx
	•	Source:
	•	Watchlist symbols from WatchlistContext (frontend state).
	•	Price/details from data.latest_by_symbol[symbol].

Rules:
	•	No separate endpoint for watchlist prices.
	•	The watchlist is purely a view over latest_by_symbol scoped to user-selected symbols.
	•	If a symbol is watchlisted but missing from latest_by_symbol, show a graceful “no data yet” row.

⸻

4.5 1h Volume Banner
	•	Component: shared BannerTicker / VolumeBannerScroll.jsx.
	•	Source: data.banner_1h_volume: BannerItem[] (or the agreed alias).

Fields:
	•	symbol, name
	•	volume_1h
	•	change_1h if available (volume change, not price)
	•	rank, trade_url

Display:
	•	Same chip layout as 1h price, but showing volume metrics.
	•	No visible pill outline, styling follows BHABIT spec.

⸻

5. Sentiment Pipeline (Info Panel)

The info icon in each row opens a sentiment/details panel.

5.1 Frontend Flow
	•	Row click handler (in TokenRow or parent):

onInfo(symbol) {
  // Uses context hook; do not fetch directly here
  sentimentContext.open(symbol);
}

	•	Context/hook (e.g. useSentiment or SentimentContext):

// Pseudocode
export async function fetchSentiment(symbol: string) {
  return fetchJson(`/api/sentiment/${encodeURIComponent(symbol)}`);
}

export function useSentiment(symbol: string | null) {
  const { data, error, isLoading } = useSWR(
    symbol ? ["sentiment", symbol] : null,
    () => fetchSentiment(symbol),
    { refreshInterval: 60_000 } // or null if only on open
  );
  return { data, error, isLoading };
}

Rules:
	•	Rows never call fetch directly.
	•	Sentiment fetch goes through the API helper and SWR.
	•	The sentiment panel reads from the sentiment hook only.

5.2 Sentiment Endpoint Contract
	•	Method: GET
	•	Path: /api/sentiment/<symbol>

interface SentimentPayload {
  symbol: string;            // e.g. "BTC-USD"
  base_asset: string;        // "BTC"
  quote_asset: string;       // "USD"

  // Aggregate scores
  score: number;             // -1..+1 or 0..100 normalized score
  bias_label: string;        // e.g. "bullish", "bearish", "neutral"

  // Futures / funding
  funding_rate?: number;
  funding_trend?: "rising" | "falling" | "flat";

  // Open interest
  open_interest_change_24h?: number;
  open_interest_trend?: "rising" | "falling" | "flat";

  // Social / narrative
  social_buzz_score?: number;
  social_trend?: "spiking" | "elevated" | "calm";

  // Raw sources (optional)
  sources?: {
    name: string;
    url?: string;
    weight?: number;
    snippet?: string;
  }[];

  last_updated: string;
}

If the backend has different exact fields, they must be reflected here and in any type/interface stubs.

⸻

6. CORS, Proxying, and Fallbacks

6.1 Normal Path (preferred)
	•	Dev:
	•	Browser → http://127.0.0.1:5173 (Vite).
	•	All board calls → fetch("/data").
	•	Vite dev server proxies /data → http://127.0.0.1:5001/data.
	•	Prod:
	•	Browser → https://<domain> (reverse proxy).
	•	Reverse proxy routes /data → Flask backend.
	•	No CORS in this path; same origin.

6.2 Fallback Path
	•	/api/data exists for compatibility.
	•	Backend may have liberal CORS for local dev; that is not an excuse to hard-code hosts in React.
	•	Only the backend and proxy layer should worry about CORS.

⸻

7. Changing the Contract

When you change the data shape or add a new field:
	1. Update this file: docs/DATA_PIPELINES.md.
	2. Update:
	•	Backend handler for /data (and /api/data alias).
	•	frontend/src/api.js helper.
	•	The SWR hook (useBoardData / useDataFeed).
	•	Any tests consuming the board data.
	3. Only then should you update board components.

If you cannot make your change while respecting this document and FRONTEND_UI_RULES.md, do not change the data contract.

---
