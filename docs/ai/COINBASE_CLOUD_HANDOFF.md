# Coinbase paper trading handoff

Repository: `tgpetrie/moonwalking`. Branch: `codex/coinbase-paper-trading`.

Moonwalking's [Portfolio Mode](../../backend/portfolio_mode.py) reads Coinbase Advanced Trade account, product, fill and order data with a view-only key. The simulator reads a scenario JSON file. The separate [collector](../../backend/paper_exit_adapter.py) can write that file using authenticated Coinbase reads for one USD spot position.

## Run the sample

Save this synthetic example as `paper-demo.json` outside the repository. Run `python scripts/coinbase_paper_exit.py /path/to/paper-demo.json` from the repository root. On Windows, substitute the full path to your file.

```json
{
  "product_id": "BTC-USD",
  "quantity": "0.01",
  "entry_cost_usd": "500",
  "exit_fee_bps": "100",
  "slippage_bps": "0",
  "thresholds": {
    "rebound_usd": "50",
    "rebound_pct": "8",
    "net_profit_pct": "8"
  },
  "quotes": [
    {"observed_at_ms": 0, "bid_usd": "40000"},
    {"observed_at_ms": 1000, "bid_usd": "43200"},
    {"observed_at_ms": 2000, "bid_usd": "45000"},
    {"observed_at_ms": 3000, "bid_usd": "54000"},
    {"observed_at_ms": 4000, "bid_usd": "55000"}
  ]
}
```

The position is assumed open before the first observation. Use the all-in acquisition cost attributable to exactly the quantity being simulated. Specify a USD spot pair, a fixed sell quantity and a tape in strictly increasing time-of-observation order. For real observations, use the time a bid was available to the decision process in Unix milliseconds. The low starts with the first observed bid and updates as the supplied window progresses. Keep the window start fixed in any comparison. This experiment assumes the supplied tape is usable and does not validate completeness, freshness or market depth.

Each rule gets a separate first hypothetical exit. The 8% rebound rule fires at a $432 bid value for the position, the $50 rebound rule fires at $450, and the 8% net profit rule fires at $550 with $544.50 in estimated proceeds under the sample fee. The simulator applies assumed slippage to the bid first, then the fee to that gross value. A missing trigger is JSON null. The final bid also gets a hypothetical liquidation mark as the hold comparison. Estimated execution prices, fees, and proceeds are paper assumptions.

## Continue in the cloud

Open Codex with a [published Cloud environment](https://learn.chatgpt.com/docs/environments/cloud-environments) for this repository. Select this branch as the task checkout or explicitly check it out from origin in the cloud task. Read this handoff and run the sample. The same branch also works from a local checkout on another computer. The repository is public. Keep personal holdings, fills, API keys and real scenario files outside Git.

## Collect a short window on Windows

Run from the repository root with the backend Python environment and the
existing `COINBASE_API_KEY_NAME` and `COINBASE_API_KEY_SECRET` set privately
in the process environment. Choose a held USD spot pair and a quantity
available in the key's portfolio. The example uses a 10 bps slippage
assumption and schedules a 30-second smoke check one minute ahead.

```powershell
$pilotDir = Join-Path $env:USERPROFILE '.moonwalking\analysis\coinbase-paper'
New-Item -ItemType Directory -Force $pilotDir | Out-Null
$pair = Read-Host 'Held USD spot pair'
$quantity = Read-Host 'Quantity of the coin to simulate'
$start = [DateTimeOffset]::UtcNow.AddMinutes(1).ToString("yyyy-MM-ddTHH:mm:ss'Z'")
$tape = Join-Path $pilotDir ("smoke-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".json")
python -m backend.paper_exit_adapter --product $pair --quantity $quantity --start-utc $start --duration-seconds 30 --slippage-bps 10 --out $tape
if ($LASTEXITCODE -eq 0) {
    python scripts/coinbase_paper_exit.py $tape
}
```

For a four-hour research window, supply a future UTC start at 00:00,
04:00, 08:00, 12:00, 16:00 or 20:00 and omit `--duration-seconds`.
The collector checks View-only permissions, reconciles the full holding
to paginated USD fills, and allocates weighted acquisition cost to the
selected quantity. It checks the balance again after reading fills.
Transferred inventory, cross-pair fills, ambiguous fill order and
incomplete pagination can make a holding ineligible. Reconciliation
can establish agreement between fills and balances. Transfers that
offset each other can escape a quantity comparison.
The [transaction summary](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/fees/get-transaction-summary)
supplies the account's spot taker fee estimate. The
[product book](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/products/get-product-book)
supplies the best bid, displayed size and book timestamp. Keep the
resulting file private because it contains fill IDs and acquisition cost.

## Interpret the pilot result

- The two rebound rules use the gross change in the bid. The net-profit
  rule uses estimated proceeds after fees and slippage. In the original
  sample, a $50 gross rebound gives $49.50 in recovery against the
  after-fee low and leaves a $54.50 loss relative to entry.
- A quote needs a fresh book timestamp and displayed size covering the
  full quantity before it can set the low or trigger an exit. The trial
  uses a 500ms assumed decision delay. The first observation after that
  delay supplies the hypothetical execution quote or records a miss.
  The result shows whether the threshold still held using the original
  trigger's low. Actual fills depend on the book at order arrival.
- A valid comparison needs usable observations in at least 98% of
  pre-end polling slots, bounded gaps and a fresh, liquid endpoint.
  The endpoint mark uses the last observed quote at or before the fixed
  end, within one poll interval and the same freshness limit. Eligible
  windows with zero exits contribute a zero difference versus holding.
  Invalid windows show unavailable comparison values.
- Use the smoke check to verify data and timing. The proposed four-hour
  windows, delays and coverage limits are engineering assumptions.
  Collect fresh windows to measure performance before choosing any
  rule or numeric promotion criterion.

[Coinbase for Agents](https://docs.cdp.coinbase.com/ai-agents/coinbase-for-agents/coinbase-mcp) is an interactive order path. A later automated execution project would use a separate, explicitly approved trading portfolio with an asset allowlist, order and daily size limits, duplicate-order protection and a stop control. Keep trading credentials out of research and Cloud development. Instant Radar's research status is tracked in its [own branch checkpoint](https://github.com/tgpetrie/moonwalking/blob/codex/instant-radar-20261028/docs/ai/RESUME_HERE.md).
