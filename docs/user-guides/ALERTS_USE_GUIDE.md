# Alerts – 2-minute verification

This is not “wait 2 minutes.”

It means: in ~2 minutes, you can prove whether alerts are functioning, or exactly which layer is quiet/broken.

## What’s true now (implementation contract)

- The alerts shown in the UI and served by the API are **main alerts** derived from real mover computation (1m/3m).
- Trend/score alerts are debug-only and must not pollute the main stream.
- The critical chain is:

  `prices → baselines → 1m/3m movers → main alerts → UI`

If movers are empty, alerts will be empty — by design.

## Daily run

From repo root:

- Start: `./start_local.sh`
- Restart (after code/config changes): `./restart_dev.sh`

Backend default: `http://127.0.0.1:5003`

## One-command oracle (recommended)

If you want a single “tells the truth” command:

```bash
scripts/verify_alerts.sh
```

It prints:
- warmup flags (`warming_1m`, `warming_3m`)
- mover row counts (1m/3m)
- current impulse thresholds (from `/api/config`)
- recent alert count + a sample payload

## 2-minute verification loop

### 1) Check alerts endpoint (10 seconds)

```bash
curl -sS http://127.0.0.1:5003/api/alerts/recent | python3 -c '
import json,sys

d=json.load(sys.stdin)
a=d.get("alerts") or []
print("alerts:", len(a))
if a:
  print("sample:", a[0].get("type"), a[0].get("symbol"), a[0].get("meta",{}))
'
```

Expected:
- `alerts:` usually non-zero once the market has movement.
- You should see both `meta.direction: up` and `meta.direction: down` over time.

### 2) Check movers + warmup (10 seconds)

```bash
curl -sS http://127.0.0.1:5003/api/data | python3 -c '
import json,sys

d=json.load(sys.stdin)
meta=d.get("meta") or {}
print("warming_1m:", meta.get("warming_1m"), "warming_3m:", meta.get("warming_3m"))
for k in ["gainers_1m","gainers_3m","losers_3m"]:
  rows=d.get(k) or []
  print(k, "rows", len(rows))
'
```

Expected:
- 1m rows fluctuate.
- 3m rows exist after warmup.

If movers are empty, alerts will be empty.

### 3) Decide: correctly quiet vs broken quiet

Use this decision tree:

- If alerts are **non-zero** → alerts are alive.
- If alerts are **zero** AND movers are **non-empty** → regression: alert generation is disabled/miswired.
- If alerts are **zero** AND movers are **empty** AND `meta.warming_3m` is **True** → warmup/baseline window (not a bug yet).
- If alerts are **zero** AND movers are **empty** AND `meta.warming_3m` is **False** → something upstream broke (price fetch / baselines / mover computation). Check backend logs.

## Validation mode (force alerts to prove wiring)

Use this only to confirm the pipe when you suspect “alerts aren’t working”.

Restart with lower thresholds:

```bash
ALERT_IMPULSE_1M_PCT=0.2 ALERT_IMPULSE_3M_PCT=0.8 ./restart_dev.sh
```

Then check:

```bash
curl -sS http://127.0.0.1:5003/api/alerts/recent | python3 -c '
import json,sys
from collections import Counter

d=json.load(sys.stdin)
a=d.get("alerts") or []
print("recent:", len(a))
print("types:", dict(Counter([x.get("type") for x in a])))
for x in a[:5]:
  print(x.get("type"), x.get("symbol"), x.get("meta",{}).get("direction"), x.get("meta",{}).get("window"))
'
```

When confirmed, restart normally (no env vars):

```bash
./restart_dev.sh
```

## Live tuning via /api/config (no restart)

`/api/config` is safe to use for runtime tuning:
- It validates bounds and rejects non-finite floats (NaN/Inf).
- It returns the impulse keys both under `config` and also at the top-level (for easy one-liners).

Read current thresholds:

```bash
curl -sS http://127.0.0.1:5003/api/config | python3 -c '
import json,sys; d=json.load(sys.stdin)
print(d.get("ALERT_IMPULSE_1M_PCT"), d.get("ALERT_IMPULSE_3M_PCT"))
'
```

Temporarily lower the threshold (applies immediately):

```bash
curl -sS -X POST http://127.0.0.1:5003/api/config \
  -H 'Content-Type: application/json' \
  -d '{"ALERT_IMPULSE_1M_PCT": 0.5}' | python3 -m json.tool
```

Restore defaults:

```bash
curl -sS -X POST http://127.0.0.1:5003/api/config \
  -H 'Content-Type: application/json' \
  -d '{"ALERT_IMPULSE_1M_PCT": 1.25, "ALERT_IMPULSE_3M_PCT": 2.0}' | python3 -m json.tool
```

## How impulse alerts fire

An impulse alert is emitted when:
- A mover row has a computed percent change for the window (1m or 3m)
- Magnitude crosses the configured threshold
- It’s not suppressed by cooldown / magnitude-dedupe

Tuning knobs:
- `ALERT_IMPULSE_1M_PCT` (default 1.25)
- `ALERT_IMPULSE_3M_PCT` (default 2.0)

## Interpreting “quiet”

- Right after restart, it’s normal to see `alerts = 0` until baselines and movers exist.
- If movers exist for long periods and alerts stay at 0, that’s a regression — use the checks above to localize the layer.
