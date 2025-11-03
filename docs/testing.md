# Testing: Unit vs Integration

This document explains how to run unit and integration tests for the project.

Unit tests (fast, hermetic)
- Backend: `export DISABLE_TALISMAN=1 && pytest -q`
- Frontend: `npm --prefix frontend test --silent`

Notes:
- Unit tests are intentionally hermetic. The frontend unit tests run with `NODE_ENV=test` / `import.meta.env.MODE==='test'` and the app short-circuits network calls (no calls to `127.0.0.1:5173`).
- WebSockets are disabled by default in unit tests; to enable live WS behavior, run integration tests below.

Integration tests (opt-in, talk to live backend)
- Backend integration (pytest marker): `LIVE_DATA=1 DISABLE_TALISMAN=1 pytest -m integration -q`
- Frontend integration: run a live backend on port 5001 and then:

  ```bash
  cd frontend
  VITE_API_URL=http://127.0.0.1:5001 VITE_ENABLE_WS=1 npm run test:integration
  ```

These commands let the frontend tests use a real backend for end-to-end verification. Integration runs should be run intentionally (they are not hermetic) and usually require a running backend.

If you want tests completely silent during CI, run the unit tests in their default modes (the repo already sets test-mode short-circuits).