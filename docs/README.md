# Moonwalkings Documentation

Welcome to the Moonwalkings documentation hub. This directory contains all technical documentation for the cryptocurrency sentiment analysis and tracking platform.

**Last Updated:** 2026-07-18
**Current System Version:** Real-source board + limited sentiment context

---

## Quick Navigation

### 📘 User Guides
Documentation for end-users and getting started quickly.

- **[Quick Start Guide](user-guides/README-QUICK-START.md)** - 5-minute setup guide for the sentiment popup feature
- **[Alerts – Operational Use Guide](user-guides/ALERTS_USE_GUIDE.md)** - Prove alerts are alive, understand thresholds, and interpret quick-buy labels.
- **[Sentiment Sources](SENTIMENT_SOURCES.md)** - Active public sources, optional credentialed providers, and unavailable sources.
- **[Private Portfolio Mode](PORTFOLIO_MODE.md)** - View-only Coinbase setup, security contract, cost-basis truth, and staged rollout.

### 👨‍💻 Developer Documentation
Technical guides for developers working on the platform.

- **[API Integration Guide](developer/API-INTEGRATION-GUIDE.md)** - Backend API design and FastAPI implementation
- **[Sentiment System Architecture](developer/SENTIMENT_ARCHITECTURE.md)** - Complete system architecture, data flow, and component details
- **[React Component Integration](developer/INTEGRATION-GUIDE.md)** - Frontend React component integration guide

### 🧪 Testing Documentation
Testing procedures and verification guides.

- **[Sentiment Upgrade Verification](testing/SENTIMENT_UPGRADE_VERIFICATION.md)** - Comprehensive testing and verification procedures
- **[Quick Smoke Tests](testing/TEST_SENTIMENT_FIX.md)** - Quick smoke test procedures for rapid verification

### 📦 Archive
Historical documentation and project status snapshots.

- [Implementation Complete](archive/IMPLEMENTATION_COMPLETE.md) - Status snapshot
- [Phase 1 Implementation Guide](archive/PHASE-1-IMPLEMENTATION-GUIDE.md) - Sprint plan archive
- [Phase 1 Complete Package](archive/PHASE-1-COMPLETE-PACKAGE.md) - Deliverables summary
- [Sentiment Popup Instructions](archive/SENTIMENT_POPUP_INSTRUCTIONS.md) - Legacy popup instructions
- [Deployment Checklist](archive/DEPLOYMENT-CHECKLIST.md) - Historical deployment checklist
- [Sentiment Integration Plan](archive/SENTIMENT_INTEGRATION_PLAN.md) - Historical integration strategy
- [Sentiment Upgrade Summary](archive/SENTIMENT_UPGRADE_SUMMARY.md) - Historical upgrade summary

---

## System Overview

The Moonwalkings platform is a cryptocurrency sentiment analysis and tracking system that combines:

- **Limited real-source sentiment** - Alternative.me and CoinGecko market context with explicit provenance.
- **Coin-specific context** - Coinbase tape, CoinPaprika events/timeline, CoinGecko community/trending proxy, and optional credentialed providers.
- **Quick-glance operator labels** - Coin Pressure maps alert families into `BUY WATCH`, `RECONFIRM`, `WATCH`, `NO CHASE`, `PROTECT`, and `AVOID LONG`.
- **Interactive Frontend** - React-based dashboard with charts and popups
- **Caching & Performance** - TTL-based caching with stale/offline states instead of fabricated fallback data.

### Key Features

✅ **Real-source context**
- Alternative.me Fear & Greed Index for market-wide sentiment
- CoinGecko global market data for market pulse
- Coinbase Exchange data for local tape, movers, price, and volume baselines
- CoinPaprika coin events/timeline for context
- CoinGecko community/trending data as an attention proxy

✅ **Advanced Analytics**
- Canonical alert engine with impulse, whale, stealth, divergence, breadth, reversal, fakeout, volatility, liquidity, trend-break, squeeze, and exhaustion families
- Coin Pressure quick-read interpretation for fast scanning
- Source provenance, timestamps, stale/offline states, and no invented sentiment values

✅ **Production-Ready Architecture**
- Async/await for parallel data fetching
- TTL-based caching (5-60 minute cache lifetimes)
- Graceful degradation with fallback data
- Error handling at source, aggregator, and API levels

---

## Tech Stack

### Backend
- **Framework:** Flask (Python)
- **Async:** aiohttp, asyncio
- **Sentiment Analysis:** Limited external metrics; no fabricated NLP score when no source exists
- **Data Sources:** requests/http clients for official/public APIs; optional credentialed providers only when configured
- **Configuration:** PyYAML

### Frontend
- **Framework:** React
- **Charts:** Chart.js
- **HTTP:** Axios
- **Build:** Vite

### Infrastructure
- **Caching:** In-memory TTL (Redis planned for Phase 3)
- **API Rate Limiting:** Source-level caching to respect free tiers

---

## Getting Started

### For End Users
1. Read the [Quick Start Guide](user-guides/README-QUICK-START.md)
2. Set up the sentiment popup in your application
3. Start tracking cryptocurrency sentiment!

### For Developers
1. Read the [Sentiment System Architecture](developer/SENTIMENT_ARCHITECTURE.md) for system overview
2. Review the [API Integration Guide](developer/API-INTEGRATION-GUIDE.md) for backend integration
3. Check the [React Component Integration](developer/INTEGRATION-GUIDE.md) for frontend work
4. Run tests using the [Testing Documentation](testing/)

### For Contributors
1. Review all developer documentation
2. Set up your development environment
3. Run the verification tests
4. Check the archive for historical context

---

## API Endpoints

### Primary Endpoints

**GET `/api/sentiment/latest?symbol=BTC`**
- Returns limited real-source sentiment context with provenance and data status.
- Market-wide values remain market-wide even when a coin symbol is supplied.

**GET `/api/sentiment?symbols=BTC,ETH`**
- Simple social sentiment format for multiple symbols

**GET `/api/sentiment-basic`**
- Lightweight payload for dashboard cards

---

## Development Roadmap

### ✅ Completed (Phase 1)
- Core sentiment aggregation engine
- Multi-tier source weighting system
- YAML-based configuration
- Frontend React components with charts
- Fear & Greed, CoinGecko, RSS, Reddit integration

### 🚧 In Progress (Phase 2)
- Comprehensive test suite (target: >80% coverage)
- Improved error handling and logging
- Sentiment history tracking
- Trending topics extraction
- Twitter/X API integration

### 📋 Planned (Phase 3+)
- Redis distributed caching
- Circuit breaker pattern for source failures
- Observability metrics (Prometheus)
- WebSocket real-time updates
- ML-based sentiment predictions (FinBERT)
- Per-symbol configuration overrides
- Sentiment alert webhooks

---

## Configuration

System configuration is externalized in `backend/sentiment_config.yaml`:

- **Cache TTLs** - Configurable cache lifetimes per source
- **Tier Weights** - Adjustable importance of Tier 1-3 sources
- **Source Enable/Disable** - Toggle individual data sources
- **Custom Lexicon** - Crypto-specific sentiment keywords
- **Divergence Thresholds** - Alert sensitivity settings

---

## Testing

### Quick Smoke Test
```bash
# From backend directory
python -m pytest tests/ -v
```

### Comprehensive Verification
See [Sentiment Upgrade Verification](testing/SENTIMENT_UPGRADE_VERIFICATION.md) for full testing procedures.

---

## Support & Questions

- **Technical Issues:** Check the [Testing Documentation](testing/) first
- **Integration Help:** See [Developer Documentation](developer/)
- **Quick Setup:** Start with the [Quick Start Guide](user-guides/README-QUICK-START.md)

---

## Document Status Legend

- 📘 **User Guide** - For end-users and customers
- 👨‍💻 **Developer Guide** - For technical implementation
- 🧪 **Testing** - For quality assurance and verification
- 📦 **Archived** - Historical reference, may be outdated

---

**Repository:** Moonwalkings
**Maintainer:** Development Team
**License:** Proprietary
