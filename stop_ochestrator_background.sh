# stop orchestrator background run if used earlier
kill $(cat /tmp/bhabit_start.pid) 2>/dev/null || true
# stop backend/frontend processes (if needed)
pkill -f 'python3 app.py --kill-port --port 5001' || true
pkill -f 'vite --host 127.0.0.1' || true