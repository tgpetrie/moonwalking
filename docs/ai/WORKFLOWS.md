# Dev Workflows
Start:
  backend :5001 → python app.py
  bridge  :5100 → node server.js
  frontend:5173 → npx vite --host 127.0.0.1 --port 5173 --strictPort
Health: /api/health → {"ok":true} • UI at :5173
Policy: `main.jsx` must render `<Dashboard/>`; keep `index.html` stock; guard arrays & numbers.
