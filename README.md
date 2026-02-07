# BHABIT MOONWALKING – Cryptocurrency Tracker

Real-time crypto tracking with stable 1‑minute movers, accurate 1‑hour price/volume trends, and alert hygiene.

![BHABIT Logo](frontend/public/bhabit-logo.png)

---

## 📋 Documentation

**For comprehensive documentation**, see the **[Documentation Hub](docs/README.md)** with organized guides:
- 📘 **[User Guides](docs/user-guides/)** - Quick start and setup guides
- 👨‍💻 **[Developer Documentation](docs/developer/)** - Architecture, API integration, React components
- 🧪 **[Testing Documentation](docs/testing/)** - Verification and testing procedures

Operational runbooks:
- [Alerts – Operational Use Guide](docs/user-guides/ALERTS_USE_GUIDE.md)

**Before modifying the UI**, read the canonical specification:
- **[`docs/UI_HOME_DASHBOARD.md`](docs/UI_HOME_DASHBOARD.md)** – Authoritative UI layout, data contracts, and implementation paths

For AI assistance:
- **[`docs/ai/AI_INDEX.md`](docs/ai/AI_INDEX.md)** – Quick reference for AI agents

---

## Dev Checklist (top-level)

- `docs/UI_HOME_DASHBOARD.md`: canonical UI spec — read before changing the home dashboard.
- Layout order: **1-MIN hero (full-width)** → **3-MIN gainers (left)** / **3-MIN losers (right)** → **Watchlist under losers**.
- Percent formatting: backend provides percentages; use `formatPct` with dynamic decimals (abs < 1 → 3, else 2).
- Watchlist model: store `{ symbol, baseline, current }` and compute `deltaPct = ((current - baseline)/baseline)*100`.
- `TokenRow` requirement: parent must pass `changeKey` (`price_change_percentage_1min` or `_3min`) and actions must be stacked (star above info).
- Insights wiring: clicking the % cell or info button opens `InsightsTabbed` with symbol/row context.
- CSS invariants: update the authoritative block in `frontend/src/index.css` — `.one-min-grid`, `.bh-token-actions`, `.bh-insight-float`.
- Data hook: use `useData` (SWR-style) that returns `data` and `bySymbol`; mutate on refresh.
- Do NOT reintroduce the legacy header or alerts bar ("BHABIT Crypto Dashboard / Alerts 25 NEW").
- If backend contract or insights change, edit `docs/UI_HOME_DASHBOARD.md` first, then implement code changes.

## Overview

BHABIT CBMOONERS shows live market data with server‑ordered top movers across 1‑minute and 3‑minute windows, plus 1‑hour price and volume trend banners. The React + Vite frontend stays smooth via WebSocket with REST fallback; the Flask backend owns ranking, hysteresis/peak‑hold, and streak‑based alerts.

---

## Features

* Server‑ordered top movers (no client resorting)
* 1‑minute table stability: hysteresis + dwell + 60s peak‑hold
* Trend metrics across scopes: direction, streak, score
* True 1‑hour volume deltas (with price‑based fallback)
* Alert hygiene: streak thresholds with cooldowns; recent alerts API
* Smooth UI: tiny sparklines, trend‑strength arrows, WS + adaptive polling fallback

---

## Architecture

```text
BHABIT CBMOONERS/
├── frontend/             # React + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/   # React UI components
│   │   ├── utils/        # Frontend utility functions
│   │   └── api.js        # API integration logic
│   └── public/           # Static files
├── backend/              # Flask API server
│   ├── app.py            # Main Flask app
│   ├── config.py         # App configuration
│   ├── requirements.txt  # Python package list
│   └── utils.py          # Backend helper functions
└── docs/                 # Additional documentation
```

---

## Quick Start

### Prerequisites

* Python 3.13 or newer
* Node.js 22.17 or newer
* Git

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd "BHABIT CBMOONERS 4"
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. **Install backend dependencies**

   ```bash
   python3 -m venv .venv
   ".venv/bin/python" -m ensurepip --upgrade
   ".venv/bin/python" -m pip install -U pip setuptools wheel
   ".venv/bin/python" -m pip install -r backend/requirements.txt
   ```

4. **Install frontend dependencies**

   ```bash
   cd frontend
   npm install
   cd ..
   ```

5. **Set up environment variables**

   ```bash
   # Backend
   [ -f backend/.env.example ] && cp backend/.env.example backend/.env.development || true

   # Frontend
   [ -f frontend/.env.example ] && cp frontend/.env.example frontend/.env || true

   # Sentiment API base (defaults to the FastAPI dev server)
   echo "VITE_SENTIMENT_API_BASE=http://127.0.0.1:8001" >> frontend/.env
   ```

---

## Running the Application

## Repo Workflow (MW_SPEC)

- Rules: see `MW_SPEC.md` (ports, contracts, UI rules, truth rules).
- Tasks: see `MW_BACKLOG.md` (living queue).
- Any change proposal must cite which `MW_SPEC` rules it satisfies.
- Any completed change must update `MW_BACKLOG` status and record Verification.

### Recommended (All-in-One Setup)

**First-time setup:**

```bash
./setup_dev.sh
```

**Start the application:**

```bash
./start_app.sh
```

**Optional utility script:**

```bash
./dev.sh setup     # First-time setup
./dev.sh start     # Start backend and frontend
```

### Manual Mode

1. **Start the backend server**

   ```bash
   source .venv/bin/activate
   cd backend
   python app.py
   ```

   Runs on: `http://127.0.0.1:5003`

2. **Start the frontend server**

   ```bash
   cd frontend
   npm run dev
   ```

   Runs on: `http://localhost:5173`

---

### Quick API Checks

```bash
curl http://127.0.0.1:5003/api/sentiment-basic
curl http://127.0.0.1:5003/api/alerts
```

---

## Development Scripts

Available utility commands:

```bash
./dev.sh setup        # One-time setup
./dev.sh start        # Launch backend and frontend
./dev.sh backend      # Start backend only
./dev.sh frontend     # Start frontend only
./dev.sh test         # Run full backend tests (pytest)
./dev.sh smoke        # Run backend smoke test against a base URL
./dev.sh build        # Build frontend for production
./dev.sh clean        # Remove build artifacts
./dev.sh health       # Check system status
./dev.sh help         # View all available commands
```

---

## Technology Stack

### Frontend

* React 18 (with hooks)
* Vite 5.4 (fast dev server)
* Tailwind CSS 3.4 (utility-first styling)
* React Icons (icon library)
* Axios (HTTP requests)
* Socket.IO Client (real-time updates)

### Backend

* Flask 3.1 (API)
* Flask-CORS (cross-origin support)
* Flask-SocketIO (WebSocket support)
* Requests (HTTP API client)
* Gunicorn (production WSGI server)
* Sentry (error monitoring)
* Flask-Limiter (rate limiting)

---

## Configuration

### Backend config

Key backend environment variables (all optional, defaults applied when absent):

```env
# 1‑minute table smoothing
ONE_MIN_ENTER_THRESHOLD=0.8         # pct to enter list
ONE_MIN_STAY_THRESHOLD=0.5          # pct to remain
ONE_MIN_DWELL_SECONDS=25            # minimum dwell time
ONE_MIN_REFRESH_SECONDS=45          # recompute cadence
ONE_MIN_MAX_COINS=10                # cap list size

# Alerts
ALERTS_COOLDOWN_SECONDS=300         # per symbol/scope
ALERTS_STREAK_THRESHOLDS=3,5        # trigger streak levels

# Monitoring (optional)
SENTRY_DSN=
```

### Frontend config

Frontend `frontend/.env`:

```env
VITE_API_URL=http://127.0.0.1:5003
# Optional WS override; when omitted, components auto‑detect
# VITE_WS_URL=ws://127.0.0.1:5003
# 1‑min WS render throttle (ms). Defaults to 7000 when omitted.
VITE_ONE_MIN_WS_THROTTLE_MS=7000
# Alerts poll cadence (ms). Defaults to 30000; min 5000.
VITE_ALERTS_POLL_MS=30000
```

---

## API Endpoints

| Endpoint                               | Method | Description                            |
| -------------------------------------- | ------ | -------------------------------------- |
| `/`                                    | GET    | Root info (component endpoints)        |
| `/health`                              | GET    | Basic health                           |
| `/api/component/top-banner-scroll`     | GET    | 1‑hour price trend banner              |
| `/api/component/bottom-banner-scroll`  | GET    | 1‑hour volume trend banner (true delta)|
| `/api/component/gainers-table`         | GET    | 3‑minute gainers                       |
| `/api/component/losers-table`          | GET    | 3‑minute losers                        |
| `/api/component/gainers-table-1min`    | GET    | 1‑minute gainers (hysteresis/peak‑hold)|
| `/api/alerts/recent`                   | GET    | Recent streak‑based alerts             |
| `/api/watchlist`                       | GET    | Current watchlist                      |
| `/api/watchlist/insights`              | GET    | Watchlist insights and recent alerts   |

---

## Deployment

### Frontend (Vercel)

1. Link your repository to Vercel
2. Set the following build settings:

   * **Build Command**: `cd frontend && npm run build`
   * **Output Directory**: `frontend/dist`
   * **Install Command**: `cd frontend && npm install`

3. Routes/Env (already in `vercel.json`):
   * Rewrites API: `/api/(.*)` → `https://moonwalker.onrender.com/api/$1`
   * SPA fallback enabled
   * Build env: `VITE_API_URL=https://moonwalker.onrender.com/`

### Backend (Render)

1. Link your repository to Render
2. Configure settings as follows:

   * **Build Command**: `pip install -r backend/requirements.txt`
   * **Start Command**: `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT`
   * **Environment** (Render Blueprint `render.yaml`):

```yaml
services:
   - type: web
      name: bhabit-backend
      runtime: python
      buildCommand: pip install -r backend/requirements.txt
      startCommand: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT
      healthCheckPath: /api/server-info
      envVars:
         - key: FLASK_ENV
            value: production
         - key: FLASK_DEBUG
            value: "false"
         - key: HOST
            value: 0.0.0.0
         - key: CORS_ALLOWED_ORIGINS
            value: "*"
         - key: API_RATE_LIMIT
            value: "1000"
         - key: CACHE_TTL
            value: "60"
```

1. Health Check: set to `/api/server-info` in the Render service settings (if not using blueprint).
2. CORS: `CORS_ALLOWED_ORIGINS="*"` is permissive; tighten it to your Vercel origin in production.

---

## Testing

### Backend Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```

### Smoke Test (Backend)

```bash
SMOKE_BASE_URL="http://127.0.0.1:5003" \
   ".venv/bin/python" backend/smoke_test.py
```

Exit 0 indicates pass; failures list missing/invalid endpoints.

---

## Contributing

1. Fork the repository
2. Create a new branch
   `git checkout -b feature/my-feature`
3. Make your changes and commit
   `git commit -m "Add my feature"`
4. Push to your fork
   `git push origin feature/my-feature`
5. Submit a Pull Request for review

---

## License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for full details.

---

## Troubleshooting and Support

If you’re having issues:

1. Check the GitHub Issues page
2. Verify all dependencies are installed
3. Confirm environment variables are correctly set
4. Make sure both frontend and backend servers are running

---

## Acknowledgments

* Created by Tom Petrie
* Inspired by the need for real-time crypto visibility

---

**BHABIT — Profits Buy Impulse**
**by Tom Petrie | GUISAN DESIGN**
