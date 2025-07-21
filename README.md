Here is your **refined README** with **all emojis removed** and replaced with natural, professional language **wherever it makes sense**, while retaining the BHABIT rabbit logo as an intentional stylistic element:

---

# 🐰 BHABIT MOONWALKING - Cryptocurrency Tracker

> Real-time cryptocurrency market tracking with live data on top gainers and losers

![BHABIT Logo](frontend/public/bhabit-logo.png)

---

## Overview

**BHABIT CBMOONERS** is a live cryptocurrency tracking platform that displays real-time market data, highlighting the biggest gainers and losers across various timeframes. The app features a modern React-based frontend styled with Tailwind CSS and powered by a fast Flask backend that handles all data processing.

---

## Features

* **Live Market Updates** — Cryptocurrency prices updated every 30 seconds
* **Top Movers** — Displays the largest gainers and losers in real time
* **Multiple Timeframes** — Includes 1-minute, 3-minute, and hourly metrics
* **Polished User Interface** — Built with Tailwind CSS and smooth animations
* **Fully Responsive** — Optimized for both desktop and mobile experiences
* **Automatic Refresh** — Data updates with visual countdown timers
* **Ready for Deployment** — Easily deploy to platforms like Vercel and Render

---

## Architecture

```
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
   cd "BHABIT CBMOONERS 2"
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. **Install backend dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
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
   cp backend/.env.example backend/.env.development

   # Frontend
   cp frontend/.env.example frontend/.env
   ```

---

## Running the Application

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

   Runs on: `http://localhost:5001`

2. **Start the frontend server**

   ```bash
   cd frontend
   npm run dev
   ```

   Runs on: `http://localhost:5173`

---

## Development Scripts

Available utility commands:

```bash
./dev.sh setup        # One-time setup
./dev.sh start        # Launch backend and frontend
./dev.sh backend      # Start backend only
./dev.sh frontend     # Start frontend only
./dev.sh test         # Run full test suite
./dev.sh build        # Build frontend for production
./dev.sh clean        # Remove build artifacts
./dev.sh health       # Check system status
./dev.sh help         # View all available commands
```

---

## Technology Stack

### Frontend

* React 18.2 (with hooks)
* Vite 5.4 (fast dev server)
* Tailwind CSS 3.4 (utility-first styling)
* React Icons (icon library)
* Axios (HTTP requests)
* Socket.IO Client (real-time updates)

### Backend

* Flask 3.1 (Python web framework)
* Flask-CORS (cross-origin support)
* Flask-SocketIO (WebSocket support)
* Requests (HTTP API client)
* Gunicorn (production WSGI server)
* Sentry (error monitoring)
* Flask-Limiter (rate limiting)

---

## Configuration

### Backend

Edit `backend/.env.development`:

```env
FLASK_ENV=development
FLASK_DEBUG=True
API_RATE_LIMIT=100
SENTRY_DSN=your_sentry_dsn_here
```

### Frontend

Edit `frontend/.env`:

```env
VITE_API_URL=http://localhost:5001
```

---

## API Endpoints

| Endpoint            | Method | Description                |
| ------------------- | ------ | -------------------------- |
| `/api`              | GET    | Health check               |
| `/api/gainers`      | GET    | Top crypto gainers         |
| `/api/losers`       | GET    | Top crypto losers          |
| `/api/gainers-1min` | GET    | 1-minute timeframe gainers |
| `/health`           | GET    | Full system health status  |

---

## Deployment

### Frontend (Vercel)

1. Link your repository to Vercel
2. Set the following build settings:

   * **Build Command**: `cd frontend && npm run build`
   * **Output Directory**: `frontend/dist`
   * **Install Command**: `cd frontend && npm install`

### Backend (Render)

1. Link your repository to Render
2. Configure settings as follows:

   * **Build Command**: `pip install -r backend/requirements.txt`
   * **Start Command**: `cd backend && gunicorn app:app`

---

## Testing

### Backend Tests

```bash
source .venv/bin/activate
cd backend
pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

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

-
