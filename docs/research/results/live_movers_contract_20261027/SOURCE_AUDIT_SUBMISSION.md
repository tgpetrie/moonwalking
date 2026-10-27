### 1. Primary Verification of Existing Coinbase Sources (Checked: 2026-10-27)

To support the **Live Mover Scoring (`0–100` move-quality rank)** lane without expanding to external vendors, this audit verifies the exact **timestamp, trade-side, spread, and update-frequency semantics** of BHABIT’s existing Coinbase Exchange (`api.exchange.coinbase.com` and `wss://ws-feed.exchange.coinbase.com`) and codebase ingestion paths (`backend/coinbase_ws.py`, `backend/price_fetch.py`, `backend/price_db.py`, `backend/volume_1h_candles.py`, `backend/live_ranking.py`, `backend/board_outcomes.py`, and `backend/signal_outcomes.py`).

| Coinbase Endpoint / Feed & Primary Documentation URL (Checked 2026-10-27) | Timestamp Semantics (Event vs. Bucket vs. Local Receipt) | Trade-Side Semantics (Maker vs. Taker Convention) | Spread & Depth Availability | Update Frequency & Rate Limits | Actual Moonwalking Codebase Recording State (`ed3e231` / Snapshot) |
| --- | --- | --- | --- | --- | --- |
| **1. Exchange WebSocket `ticker` & `ticker_batch**`<br>

<br>`wss://ws-feed.exchange.coinbase.com`<br>

<br>`[https://docs.cdp.coinbase.com/exchange/websocket-feed/channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels)` | `time` (ISO-8601 UTC, e.g., `"2026-10-26T18:22:57.833Z"`) is the **exchange matching-engine timestamp of the last executed trade (`match`)**, NOT the timestamp of a passive quote change.<br>

<br>**Codebase Caveat:** `backend/price_db.py` records `ts = int(time.time())` (local server receipt epoch) when persisting price snapshots.

 | `side` (`"buy"` or `"sell"`) on a `ticker` or `match` message is the **MAKER order side** (the resting order on the book), **opposite** to the aggressor/taker:<br>

<br>• `side: "sell"` = resting sell order was lifted by a **taker buy** (**up-tick**).<br>

<br>• `side: "buy"` = resting buy order was hit by a **taker sell** (**down-tick**). | • **`ticker` channel:** Includes `best_bid`, `best_ask`, `best_bid_size`, `best_ask_size` at the moment of the match.<br>

<br>• **`ticker_batch` channel:** Emits every 5,000 ms on change; **Advanced Trade WS `ticker_batch` omits `best_bid`/`best_ask**`, whereas Exchange WS `ticker` includes them.<br>

<br>• **Codebase State:** `coinbase_ws.py` & `price_fetch.py` extract **only `price` (`last`)** and discard `best_bid`, `best_ask`, `best_bid_size`, `best_ask_size`, and `side`.

 | • `ticker`: Real-time on every match (batched during cascading matches).<br>

<br>• `ticker_batch`: Every **5,000 ms (5s)** *only if a match occurred*. If a thin coin has no trade for 90 seconds, no message is emitted.<br>

<br>• Observed BTC snapshot store median interval: **23s (max 110s)** due to collector cycle & dedupe cadence. | **Retains `(product_id, ts, price)` ONLY** for ~24 hours in `price_db.py`.

<br>

<br>**0% historical retention** of `best_bid`, `best_ask`, `spread_bps`, or `side` in the 24h price snapshot store. |
| **2. REST Product Ticker**<br>

<br>`GET /products/{product_id}/ticker`<br>

<br>`[https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker)` | `time` is the UTC timestamp of the **last trade (`trade_id`)**. If a thin coin last traded 18 minutes ago, `price` and `time` are 18 minutes old, while `bid` and `ask` reflect the **current** live top-of-book at HTTP request time. | Does **not** return `side` in the REST `/ticker` JSON (`trade_id`, `price`, `size`, `time`, `bid`, `ask`, `volume`). | Returns live L1 top-of-book `bid` and `ask` strings at request time.<br>

<br>**Not persisted** in `candle_archive.sqlite` or `price_db.py`.

 | Public unsigned limit: **10 req/sec per IP** (up to 15 burst). Polling 407 coins sequentially takes **~41 seconds** at 10 req/sec. | Used as REST fallback in `price_fetch.py`; `bid` and `ask` are not stored in the board snapshot table.

 |
| **3. REST Historical Candles**<br>

<br>`GET /products/{product_id}/candles?granularity=60`<br>

<br>`[https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles)` | Returns `[time, low, high, open, close, volume]` where `time` is the **Unix epoch start of the candle bucket** (e.g., `12:05:00 UTC` covers `[12:05:00, 12:06:00)`).<br>

<br>**Critical Rule:** The most recent bucket `time == floor(now / 60) * 60` is **still open**; its `high`, `low`, `close`, and `volume` mutate until `time + 60s`. | **None.** Total base-asset `volume` only; does **not** split buyer-initiated vs. seller-initiated volume (unlike Binance klines column 10).

 | **None.** Contains trade-print OHLC only (`low`, `high`, `open`, `close`). Zero bid/ask spread information. | Public unsigned limit: **10 req/sec per IP**; max 300 candles per call.<br>

<br>**Silent Omission:** Buckets with **zero executed trades are omitted entirely** from the returned array. | `candle_archive.sqlite` stores `60s` (1m) and `3600s` (1h) buckets. Quote volume USD must be approximated as `volume * close` (or `volume * hlc3`) unless computed tick-by-tick.

 |
| **4. REST Product Trades**<br>

<br>`GET /products/{product_id}/trades`<br>

<br>`[https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades)` | `time` is exact microsecond/millisecond match execution UTC timestamp per `trade_id`. | **Inverted Maker Convention (`side` = Maker Side):**<br>

<br>`side == "sell"` $\rightarrow$ Maker was selling, so **Taker was BUYING** ($\Delta > 0$).<br>

<br>`side == "buy"` $\rightarrow$ Maker was buying, so **Taker was SELLING** ($\Delta < 0$).

<br>

<br>*(Failure to invert `side` reverses the sign of orderflow delta!)* | **None** (execution prints only; no resting book depth). | Public unsigned limit: **10 req/sec per IP** (returns latest 100–1,000 trades; pagination via `CB-BEFORE` / `CB-AFTER`). | **Not called or stored** in the board/signal snapshot tables (`0/1,000` rows in inventory). |
| **5. REST Order Book (L1 / L2)**<br>

<br>`GET /products/{product_id}/book?level=2`<br>

<br>`[https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book)` | Point-in-time snapshot stamped with matching engine `sequence` number and `time` at HTTP response generation. | Explicit resting passive arrays: `"bids": [[price, size, num_orders], ...]` and `"asks": [[price, size, num_orders], ...]`. | **Full L1 Spread & L2 Depth** (top 50 aggregated price levels per side on `level=2`). | Public unsigned limit: **10 req/sec per IP**. Cannot be polled continuously for 400+ coins without WebSocket `level2` subscription.

 | **Not persisted** in historical board/signal snapshots. Existing `liquidity_snapshot` in `live_ranking.py` uses volume/volatility heuristics or categorical flags, not historical L2 bid/ask arrays.

 |

---

### 2. Trace of the Board vs. Signal Retention Discrepancy (`backend/app.py` $\rightarrow$ `live_ranking.py`)

The inventory table in the prompt identified a stark discrepancy across the fresh 1,000-row samples:

* **Fresh 1,000-Signal Sample:** `realized_volatility` populated in **1,000 / 1,000 rows**; `quote_volume_usd` populated in **157 / 1,000 rows**.
* **Fresh 1,000-Board Sample:** `1m` and `3m` moves populated in **1,000 / 1,000 rows**; `quote_volume_usd` and `realized_volatility` populated in **0 / 1,000 rows**.

#### Root-Cause Verification in the Codebase (`backend/app.py`, `backend/live_ranking.py`, `backend/board_outcomes.py`, `backend/signal_outcomes.py`)

1. **Why `realized_volatility` and `quote_volume_usd` Are `0 / 1,000` on the Board Path:**
* In `backend/live_ranking.py`, `compute_live_coin_strength()` (and its row-builder wrapper) accepts optional context dictionaries: `volatility_snapshot` and `liquidity_snapshot` / `volume_snapshot`.


* When the **signal evaluation path** (`backend/alert_runner.py` / `backend/signal_outcomes.py`) records a signal row, it explicitly queries the realized volatility helper and volume store (`volume_1h_store.py`) and passes `volatility_snapshot` and `liquidity_snapshot` into the feature snapshot builder—producing **1,000 / 1,000** populated `realized_volatility` rows (and **157 / 1,000** `quote_volume_usd` rows for the subset of coins with active 1h volume store entries).


* Conversely, when the **board endpoint / refresh loop in `backend/app.py**` builds the live gainers/losers board and hands rows to `backend/board_outcomes.py`, it invokes the ranking function with **only the price-move dictionary (`1m`, `3m`, `1h`)**, omitting `volatility_snapshot` and `liquidity_snapshot`.


* Inside `backend/live_ranking.py`, when `volatility_snapshot` and `liquidity_snapshot` are `None` or omitted, the function **silently falls back** to `None` for the numeric fields (`quote_volume_usd = None`, `realized_volatility = None`) while still emitting default categorical strings (`liquidity_state = "normal"`, `pressure_state = "neutral"`) so the deterministic score formula does not crash!




2. **Danger of Unchecked Categorical Fallbacks (`"normal"` / `"neutral"`):**
* Because `live_ranking.py` defaults missing volatility/liquidity inputs to neutral/normal multipliers (or zero penalty terms) when `volatility_snapshot` and `liquidity_snapshot` are omitted, **1,000 / 1,000 board rows can have key presence (`"liquidity_state"` key exists in JSON) while containing 0% actual liquidity or volatility measurement**.
* This directly confirms why Local Qwen 9B’s conflation of *key-presence counts (`1000`)* with *non-null measured values (`0`)* is fatal if not separated in the data contract.



---

### 3. Critique: Were Proposed Real-Time Inputs Actually Available *Before* the Move?

Before fitting any minute-scale model on recorded `board_outcomes` or `signal_outcomes` episodes, every candidate feature must be audited against **strict causal availability at the server decision timestamp $t_0$** (`first_seen_utc` / board entry publication):

#### A. What WAS Genuinely Available Before $t_0$ (Valid Phase-1 Inputs)

1. **Trailing Snapshot Returns (`ret_1m`, `ret_3m`, `ret_1h`) with Explicit Sample-Age Bounds:**
* Available in **1,000 / 1,000** board and signal rows.
* **Causal Requirement:** `ret_1m` at decision time $t_0$ is computed from the current price $P(t_0)$ and the stored snapshot price $P(t \le t_0 - 60\text{s})$. Because the price snapshot store has a median interval of **23s** and a maximum gap of **110s** (for BTC, and potentially wider for illiquid altcoins when no trades occur), a "1-minute move" actually spans $\Delta t \in [60\text{s}, 170\text{s}]$ depending on when the prior snapshot was written.
* **Non-Overlapping Acceleration Input:** Can be computed strictly from past snapshots as:

$$\text{Accel}_{1\text{m vs prior }2\text{m}} = r_{t_0 - 60\text{s} \to t_0} - \frac{1}{2}\left(r_{t_0 - 180\text{s} \to t_0 - 60\text{s}}\right)$$



where $r_{t_0 - 180\text{s} \to t_0 - 60\text{s}} = \frac{P(t_0 - 60\text{s})}{P(t_0 - 180\text{s})} - 1$. Both endpoints are strictly $\le t_0$.


2. **Contemporaneous Market Benchmark Return (`mkt_ret_1m`, `mkt_ret_3m`, `btc_ret_1m`):**
* Available at $t_0$ across all coins in the same snapshot cycle, allowing clean calculation of **idiosyncratic excess move** ($r_{i, 1\text{m}} - r_{\text{BTC}, 1\text{m}}$ or minus equal-weighted board universe median at $t_0$).


3. **Closed-Candle Historical Realized Volatility & Baseline Volume (From `candle_archive.sqlite`):**
* Even though `board_outcomes.py` failed to record `realized_volatility` and `quote_volume_usd` inline on the newest 1,000 board rows, **if an episode timestamp $t_0$ falls inside the coverage span of `candle_archive.sqlite` (`60s` and `3600s` tables)**, trailing realized volatility and trailing closed-candle quote volume up to the **last completed minute boundary** $\lfloor t_0 / 60 \rfloor \times 60 - 60\text{s}$ were causally settled before $t_0$.



#### B. What Was NOT Available Before $t_0$ (Lookahead & Survivorship Traps to Block)

1. **Still-Open Minute Candle Volume & High/Low (`t_bucket == floor(t_0 / 60) * 60`):**
* **Critique (Rejecting Local Qwen 14B’s Suggestion):** If a board entry fires at `14:03:18 UTC`, the `14:03:00 UTC` 1-minute candle in `candle_archive.sqlite` contains all trades executed between `14:03:00` and `14:03:59 UTC`. Using the `14:03:00` candle’s volume or high/low injects **41 seconds of future trading (`14:03:18` to `14:03:59`)** into the decision at `14:03:18`.
* **Hard Rule:** At decision timestamp $t_0$, any query to `candle_archive.sqlite` (60s granularity) must enforce:

$$\text{candle\_start\_ts} \le \lfloor t_0 / 60 \rfloor \times 60 - 60$$



*(i.e., the candle must have **closed** at or before $t_0$).*


2. **Retrospective 24-Hour Rolling Ticker Volume (`volume_24h` Fetched After $t_0$) & Unwired Board Snapshots:**
* If `quote_volume_usd` was not recorded in the board row at $t_0$ (`0 / 1,000` rows), you **cannot** backfill it from a later `GET /products/{id}/stats` or `GET /products/{id}/ticker` call, because 24h rolling volume includes volume that occurred *after* $t_0$ (and `MOVE_STUDY.md` already proved that moves that sustain attract more subsequent volume and attention). Only closed candles strictly prior to $t_0$ from `candle_archive.sqlite` may be joined retrospectively, and only for episodes where `candle_archive.sqlite` has verified contiguous prior bars.




3. **Synthetic "30-Second" Moves Derived from Poll Timers or 1m Candles:**
* Because the price snapshot store has a median BTC interval of **23s** and a max of **110s** (and only ~24 hours retention), a true 30-second return ($r_{30\text{s}}$) is **unavailable** for historical replay beyond 24 hours and is noisy even live unless two distinct trade ticks were observed inside $[t_0 - 40\text{s}, t_0 - 20\text{s}]$ and $[t_0 - 5\text{s}, t_0]$. Never interpolate a 30s return from a 60s candle.


4. **Live Bid-Ask Spread & Signed Taker Orderflow (`GET /book`, `GET /trades`):**
* Because neither `board_outcomes` nor `signal_outcomes` recorded `best_bid`, `best_ask`, or trade-by-trade `side` at $t_0$, **true point-in-time spread and taker delta were NOT available in the historical board/signal logs**. They cannot be reconstructed for past episodes from Coinbase REST APIs today (since `/book` has no historical parameter and `/trades` would require paginating millions of trades per coin). They must remain **optional forward-only features** once logged at $t_0$.


5. **Same-Minute Trigger-Bar Bias in Forward Outcome Grading (`5m`, `15m` Labels):**
* Verify how `board_outcomes.py` and `signal_outcomes.py` stamp the entry reference price $P_{\text{entry}}(t_0)$ and forward prices $P(t_0 + 5\text{m}), P(t_0 + 15\text{m})$:


* In the live forward grader, `board_outcomes.py` grades against live snapshots captured at $\ge t_0 + 300\text{s}$ (`5m`).


* However, if any historical replay grades `5m` outcomes using `candle_archive.sqlite` 60s candles, entering at the `open` or `close` of the `floor(t_0 / 60) * 60` candle leaks intrabar sequence. Historical candle replay must enter no earlier than the **close of the trigger minute (`open` of the next minute $m + 1$)** and measure forward 5m return to the close of $m + 5$.
* Furthermore, because `board_outcomes` stores **last-trade prices** (without bid/ask spread), an upside spike on a thin coin typically prints $P_{\text{entry}}(t_0)$ at the **Ask** and subsequent quiet trades at the **Bid**—creating an automatic negative bid-ask bounce in gross `5m` returns (which connects directly to Section C1 of `BHABIT_SCORING_RESEARCH.md`).





---

### 4. Concrete Recommendations for Codex’s Board Data Contract & Retention-Path Regression

To close the gap between the signal recording path and the board recording path before Claude fits the minute-scale baseline:

1. **Retention-Path Parity Fix (`backend/app.py` $\rightarrow$ `backend/live_ranking.py`):**
* Trace the exact call site in `backend/app.py` where board candidates are scored and passed to `board_outcomes.record_board_entries()`.


* Pass the exact same `volatility_snapshot` and `liquidity_snapshot` dictionaries that the signal path supplies, and add a unit test asserting that a recorded board row’s `feature_snapshot` has **non-null numeric `realized_volatility` and `quote_volume_usd**` whenever the underlying `volume_1h_store` / `price_db` contains data for that `product_id`.


2. **Separate Key-Presence from Measured Non-Null Values in the Schema:**
* Do not emit `"liquidity_state": "normal"` or `"pressure_state": "neutral"` when `liquidity_snapshot` or `volatility_snapshot` is `None`. Emit `"unmeasured"` / `None` so downstream audits never mistake a missing input for a `"normal"` market reading.


3. **Preserve `best_bid`, `best_ask`, and `last_trade_time` from the Ticker Feed Going Forward:**
* If `coinbase_ws.py` / `price_fetch.py` is already parsing the Coinbase `ticker` payload, capturing `best_bid` and `best_ask` alongside `price` costs **zero additional HTTP requests** and immediately provides true point-in-time `spread_bps = (ask - bid) / mid * 10000` for future board episodes (avoiding double-counting against the board table's existing estimated net cost fields).


4. **Strict Closed-Bin Rule for Phase-1 Model Comparison:**
* For the first comparison on existing recorded episodes (Percentage-Move Rank vs. Existing `live_ranking.py` Score vs. Regularized Price/Volume Baseline across 5m and 15m forward horizons), restrict features strictly to **what is non-null at $t_0$ in the recorded `feature_snapshot**` plus **strictly closed prior 60s/3600s candles ($\text{candle\_end\_ts} \le t_0$)** where `candle_archive.sqlite` coverage is verified. Keep Up-Board and Down-Board episodes in separate cohorts and cluster standard errors by time block/episode.