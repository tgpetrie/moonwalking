# 🐰 BHABIT MOONWALKING - Cryptocurrency Tracker

> *Real-time cryptocurrency market tracking with live gainers and losers data*

![BHABIT Logo](frontend/public/bhabit-logo.png)

## 📖 Overview

BHABIT CBMOONERS is a real-time cryptocurrency tracking application that provides live market data, focusing on the biggest gainers and losers in the crypto market. The application features a modern React frontend with a Python Flask backend that fetches and processes cryptocurrency data.

### ✨ Features

- 🚀 **Real-time Data**: Live cryptocurrency price tracking with 30-second updates
- 📈 **Gainers & Losers**: Track the biggest market movers
- ⚡ **Fast Updates**: 1-minute and standard timeframe data
- 🎨 **Modern UI**: Beautiful Tailwind CSS interface with smooth animations
- 📱 **Responsive Design**: Works seamlessly on desktop and mobile
- 🔄 **Auto-refresh**: Automatic data updates with countdown timer
- 🌐 **Production Ready**: Configured for deployment any way you please(easy Vercel, Render)

## 🏗️ Architecture

```
BHABIT CBMOONERS/
├── 🎨 frontend/          # React + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── utils/        # Utility functions
│   │   └── api.js        # API integration
│   └── public/           # Static assets
├── 🐍 backend/           # Python Flask API
│   ├── app.py           # Main Flask application
│   ├── config.py        # Configuration settings
│   ├── requirements.txt # Python dependencies
│   └── utils.py         # Backend utilities
└── 📝 docs/             # Documentation
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+** (with pip)
- **Node.js 22.17+** (with npm)
- **Git**

### 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "BHABIT CBMOONERS 2"
   ```

2. **Set up Python virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
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

5. **Configure environment variables**
   ```bash
   # Backend environment
   cp backend/.env.example backend/.env.development
   
   # Frontend environment
   cp frontend/.env.example frontend/.env
   ```

### 🏃‍♂️ Running the Application

#### Quick Start (Recommended)

**First time setup:**
```bash
./setup_dev.sh
```

**Start the application:**
```bash
./start_app.sh
```

**Alternative - Using the dev utility:**
```bash
./dev.sh setup    # First time setup
./dev.sh start    # Start both servers
```

#### Manual Development Mode

1. **Start the backend server**
   ```bash
   source .venv/bin/activate
   cd backend
   python app.py
   ```
   Backend will run on `http://localhost:5001`

2. **Start the frontend development server** (in a new terminal)
   ```bash
   cd frontend
   npm run dev
   ```
   Frontend will run on `http://localhost:5173`

#### Development Scripts

We provide several scripts to make development easier:

- `./setup_dev.sh` - Complete development environment setup
- `./start_app.sh` - Start both backend and frontend servers
- `./dev.sh` - Development utility with multiple commands

**Dev utility commands:**
```bash
./dev.sh setup        # Setup development environment
./dev.sh start        # Start both servers
./dev.sh backend      # Start only backend
./dev.sh frontend     # Start only frontend
./dev.sh test         # Run all tests
./dev.sh build        # Build for production
./dev.sh clean        # Clean build artifacts
./dev.sh health       # Check application health
./dev.sh help         # Show all commands
```

## 🛠️ Technology Stack

### Frontend
- **React 18.2** - Modern React with hooks
- **Vite 5.4** - Fast build tool and dev server
- **Tailwind CSS 3.4** - Utility-first CSS framework
- **React Icons** - Icon library
- **Axios** - HTTP client for API calls
- **Socket.IO Client** - Real-time communication

### Backend
- **Flask 3.1** - Lightweight Python web framework
- **Flask-CORS** - Cross-origin resource sharing
- **Flask-SocketIO** - Real-time WebSocket support
- **Requests** - HTTP library for external APIs
- **Gunicorn** - Production WSGI server
- **Sentry** - Error tracking and monitoring
- **Flask-Limiter** - Rate limiting

### DevOps & Deployment
- **Vercel** - Frontend deployment
- **Render** - Backend deployment
- **Docker** - Containerization support
- **pytest** - Testing framework

## 🔧 Configuration

### Backend Configuration

Edit `backend/.env.development`:
```env
FLASK_ENV=development
FLASK_DEBUG=True
API_RATE_LIMIT=100
SENTRY_DSN=your_sentry_dsn_here
```

### Frontend Configuration

Edit `frontend/.env`:
```env
VITE_API_URL=http://localhost:5001
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api` | GET | Health check |
| `/api/gainers` | GET | Top cryptocurrency gainers |
| `/api/losers` | GET | Top cryptocurrency losers |
| `/api/gainers-1min` | GET | 1-minute timeframe gainers |
| `/health` | GET | Application health status |

## 🚀 Deployment

### Frontend (Vercel)

1. Connect your repository to Vercel
2. Set build settings:
   - **Build Command**: `cd frontend && npm run build`
   - **Output Directory**: `frontend/dist`
   - **Install Command**: `cd frontend && npm install`

### Backend (Render)

1. Connect your repository to Render
2. Set build settings:
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && gunicorn app:app`

## 🧪 Testing

Run backend tests:
```bash
source .venv/bin/activate
cd backend
pytest
```

Run frontend tests:
```bash
cd frontend
npm test
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues:

1. Check the [Issues](issues) page
2. Ensure all dependencies are properly installed
3. Verify environment variables are correctly set
4. Check that both frontend and backend servers are running

## 🙏 Acknowledgments

- Built with ❤️ by the BHABIT team
- Special thanks to the cryptocurrency API providers
- Inspired by the need for real-time market tracking

---

**Made with 🐰 by Tom Petrie ** GUISAN DESIGN ** bhabit ** moonwalking
