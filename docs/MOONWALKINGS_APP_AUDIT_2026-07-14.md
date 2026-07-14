# Moonwalkings App Audit

Date: 2026-07-14

Scope: design, UX, information hierarchy, efficiency/performance, architecture, reliability, security, data quality, and missing/weak features. This is recommendation-only; no audit recommendations were implemented in this pass.

## Executive summary

Moonwalkings has a strong real-time board concept and a useful “coin pressure” popup, but the app is carrying too many parallel implementations: multiple sentiment paths, duplicate components, legacy docs, overlapping launch scripts, and mixed public/private product directions. The most important fixes are consolidation and truth-state clarity, not more visual effects or more data sources.

## Must-fix

| Area | Issue | Impact | Effort | Recommendation |
|---|---|---:|---:|---|
| Runtime | Startup depends on several scripts and ports, and failures can look like partial success. | High | Medium | Keep `./start_app.sh` as the only supported local launcher. Add a single health summary that checks Flask, FastAPI sentiment, Vite, and key proxied endpoints. |
| Sentiment architecture | Multiple sentiment code paths still exist: FastAPI `/sentiment/latest`, Flask proxy, local tape heat, legacy hooks, context provider, and coin-intel. | High | High | Designate one canonical frontend hook and one canonical backend proxy. Deprecate or quarantine legacy `useSentiment*` paths after current UI is stable. |
| Data truth | Some UI copy still risks making context/proxy metrics feel like true social sentiment. | High | Medium | Use labels like “market-wide”, “coin context”, “attention proxy”, “unavailable”, and “stale” everywhere sentiment appears. |
| Secrets | Local `.env` files should never be inspected or printed during normal diagnostics. | High | Low | Add a script/checklist rule: never `rg` or print `.env*`; use `.env.example` for docs. Rotate any exposed local keys if they were real. |
| Source catalog | Catalog entries can be mistaken for active coverage. | High | Low | Keep `implemented`, `access`, and `scope` fields, and have docs state that catalog metadata is not active coverage. |
| Repo hygiene | Many generated/cache/database artifacts live inside the repo tree. | Medium | Medium | Move runtime DBs/logs to `var/` or `.local/`, update `.gitignore`, and document which files are safe to delete. |

## High-impact improvements

| Area | Issue | Impact | Effort | Recommendation |
|---|---|---:|---:|---|
| UI hierarchy | The board, banners, watchlist, alerts, and sentiment popup compete for attention. | High | Medium | Define one primary scan path: market banners → 1m movers → 3m gainers/losers → watchlist → coin popup. Reduce decorative status chips unless they answer a decision. |
| Rabbit/row effect | The intended natural row-film reveal is fragile and spread through CSS overrides. | Medium | Medium | Keep the rabbit fixed and make one documented final CSS block for row film/rail/content stacking. Add a Playwright visual smoke screenshot for empty-row hover. |
| Performance | Large React component surface plus frequent polling risks unnecessary renders. | Medium | Medium | Profile the dashboard with React DevTools; memoize row components and stabilize array identities from data hooks. |
| Error states | Offline/degraded states exist but are not yet consistently presented as a user-readable diagnosis. | Medium | Low | Add compact status text per data domain: price tape, sentiment, coin-intel, watchlist persistence. |
| Tests | Backend truth tests exist, but end-to-end runtime verification is still manual. | Medium | Medium | Add a smoke test that starts services, checks `/data`, `/api/sentiment/latest`, `/api/coin-intel?symbol=BTC`, and captures the UI. |

## Design and UX recommendations

- Preserve the dark board identity, but reduce simultaneous glow systems. The rabbit hover should be subtle and spatial; sentiment/status alerts should be semantic.
- Empty rows are valuable tuning surfaces. If empty-row hover cannot reveal the rabbit, the film layer is not strong enough or the stacking context is wrong.
- Make “ⓘ” behavior consistent: it should always mean coin details/pressure, not a different sentiment route depending on component.
- Use “market-wide sentiment” near Fear & Greed so users do not assume BTC/SOL-specific sentiment.
- Consider a small source drawer inside the popup showing source, timestamp, freshness, and access type.

## Architecture recommendations

- Collapse sentiment UI entrypoints to one hook with a normalized shape.
- Keep FastAPI sentiment as the external-source service and Flask as the app proxy/orchestrator.
- Keep `/api/coin-intel` as coin context, not the market-wide sentiment endpoint.
- Remove retired fabricated routes after all imports are verified, or keep them returning explicit 410/503 with tests.
- Prefer explicit adapter tests over UI components reading raw snake_case API payloads.

## Reliability and data quality recommendations

- Apply bounded cache TTLs per source and surface `stale_age_seconds`.
- Treat 429/rate-limit separately from generic offline.
- Keep unsupported providers unavailable instead of substituting zeros or 50/50 neutral values.
- Add a small source registry endpoint that distinguishes `configured`, `implemented`, `enabled`, and `contributing`.

## Security recommendations

- Add `.env*` to diagnostic exclusions and document secret-handling rules.
- Review CORS before deployment; `allow_origins=["*"]` is acceptable for local development but not production.
- Avoid scraping/platform gray areas until official API access and terms are reviewed.
- Ensure frontend never receives provider API keys.

## Feature gaps / future ideas

- User-facing “why this moved” summary tied to local tape, alerts, and external context.
- Watchlist-specific alert history with exact add price, current price, and elapsed time.
- Source confidence badges: “1 live source”, “stale fallback”, “proxy attention only”.
- Visual regression screenshots for board hover, modal open/close, empty/warming states, and stale/offline states.
- Optional paid-provider setup wizard for LunarCrush or CoinMarketCap if richer social sentiment becomes important.
