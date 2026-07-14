# Alerts – 2-minute verification

This is not “wait 2 minutes.”

It means: in ~2 minutes, you can prove whether alerts are functioning, or exactly which layer is quiet/broken.

## What’s true now (implementation contract)

- The alerts shown in the UI and served by the API are **main alerts** derived from real mover computation (1m/3m).
- Trend/score alerts are debug-only and must not pollute the main stream.
- The executable source of truth is `backend/alerts_engine.py`. Older alert files are historical unless the Flask app calls them.
- Alerts are **operator attention signals**, not automatic buy/sell orders. The Pulse tab translates them into quick-read labels such as `BUY WATCH`, `RECONFIRM`, `NO CHASE`, `PROTECT`, and `AVOID LONG`.
- The critical chain is:

  `prices → baselines → 1m/3m movers → main alerts → UI`

If movers are empty, alerts will be empty — by design.

## What alerts are trying to tell you

| Quick read | Main alert families | Meaning for fast buying |
|---|---|---|
| `BUY WATCH` | `coin_breadth_thrust`, `coin_trend_break_up`, confirmed upside `breakout` | Upside exists with better participation. Look for a pullback, retest, or fresh rank hold; do not buy purely because the label is green. |
| `RECONFIRM` | `moonshot`, `breakout`, `coin_squeeze_break`, `coin_persistent_gainer`, `coin_fomo` | Momentum is live but extension/chase risk is high. Demand another fresh push, volume support, or stable rank hold. |
| `WATCH` | `whale_move`, `stealth_move`, `coin_liquidity_shock`, neutral external attention | Participation or attention is showing before clean price direction. Useful early smoke, not an entry by itself. |
| `NO CHASE` | `coin_fakeout`, late `coin_exhaustion_*`, disagreement after extension | A move may have rejected or become late. Wait for reclaim confirmation. |
| `PROTECT` / `AVOID LONG` | `crater`, `dump`, `coin_breadth_failure`, `coin_trend_break_down`, `coin_persistent_loser`, `coin_reversal_down` | Downside pressure is active. Protect longs; wait for reclaim/base before buying. |
| `TRAP RISK` | `divergence` | Price/timeframe/volume are disagreeing. Do not treat the visible move as clean until confirmation appears. |

The quick-read card also checks:

- **freshness**: fresh confirmation inside roughly 2 minutes is treated better than old alerts;
- **volume**: volume confirmation improves buy quality;
- **breadth**: broad tape support makes upside alerts more useful and weak breadth downgrades them;
- **sentiment/attention**: credentialed social sources can support a move; CoinGecko/CoinPaprika community data is labeled as an attention proxy, not true sentiment.

## Current default thresholds

These defaults come from `DEFAULT_THRESHOLDS` in `backend/alerts_engine.py`.

| Family | Default requirement |
|---|---|
| Moonshot / crater | `abs(1m) >= 1.00%` or `abs(3m) >= 2.60%` |
| Breakout / dump | `abs(1m) >= 0.55%` or `abs(3m) >= 1.90%` |
| Generic impulse consideration | `1m >= 1.25%` or `3m >= 2.0%` |
| Whale move | minute-volume z-score `>= 3.0`, 3-candle cluster z-score `>= 2.5`, candle move `>= 0.3%`, or 1h volume surge `>= 150%`; minimum absolute volume `500` |
| Stealth move | 1h volume change `> 110%` while `abs(3m price) < 1.2%` |
| Divergence | opposite/disagreeing 1m and 3m moves with each side `>= 0.65%` |
| Coin FOMO | MPI `>= 72`, MPI delta over 60s `>= 6`, 3m `>= 1.8%`, 1m `>= 0.6%`, acceleration `>= 0.9` |
| Breadth thrust | breadth `>= 0.65`, 3m `>= 1.2%`, relative strength `>= 0.8`, persistence `>= 0.35` |
| Breadth failure | breadth `<= 0.35`, 3m `<= -1.2%`, relative strength `<= -0.9` |
| Reversal | previous move `>= 2.0%`, flip move `>= 0.6%` |
| Fakeout | breakout leg `>= 1.6%`, rejection `>= 0.6%` |
| Persistent mover | streak `>= 3`, move `>= 1.1%` |
| Volatility expansion | current/previous realized-vol ratio `>= 1.7` |
| Liquidity shock | minute-volume z-score `>= 2.6`, latest volume `>= 75`, price muted under `0.25%` |
| Trend break | fast/slow return EMA difference `>= 0.08`, volume confirm `>= 15%` or volume ratio `>= 1.20` |
| Squeeze break | compressed volatility percentile `<= 0.25`, 1m move `>= 0.8%`, volume ratio `>= 1.6` |
| Exhaustion | streak `>= 4`, 1m flip `>= 0.6%`, 3m context move `>= 1.0%` |

Default caps and freshness:

- max total active alerts: `24`
- max per symbol: `2`
- common cooldowns: impulse `90s`, whale `180s`, stealth `420s`, divergence `180s`, coin FOMO `240s`, breadth thrust/failure `180s`
- common TTLs: impulse `5m`, whale `8m`, stealth `5m`, divergence `5m`, coin mood `5m`, reversal `10m`, fakeout `8m`

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
