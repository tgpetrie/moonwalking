# Local Run Verification

This file contains artifacts captured when running the app locally from branch `feature/mobile-api-alignment`.

Files included:
- `server-info.json` — JSON returned by `GET /api/server-info` on the backend.
- `bhabit-logo-headers.txt` — HTTP HEAD result for `/bhabit-logo-main.svg` from the frontend.
- `backend-tail.log` — last 200 lines of `backend.log` at capture time.
- `frontend-tail.log` — last 200 lines of `frontend.log` at capture time.

Commands used to capture these artifacts:

```bash
curl -sS http://127.0.0.1:5001/api/server-info -o server-info.json
curl -s -I http://127.0.0.1:5173/bhabit-logo-main.svg > bhabit-logo-headers.txt
tail -n 200 backend.log > backend-tail.log
tail -n 200 frontend.log > frontend-tail.log
```

Quick notes:
- Backend reported `port: 5001` and `status: running` in `server-info.json`.
- The frontend served `/bhabit-logo-main.svg` with `Content-Type: image/svg+xml` (HTTP 200).
- Logs show the background price fetcher active and component endpoints returning 200; some transient 429/503 were observed during external API rate limiting.

