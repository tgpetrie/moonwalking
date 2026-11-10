# Coinbase paper trading handoff

Repository: `tgpetrie/moonwalking`. Branch: `codex/coinbase-paper-trading`.

Moonwalking's existing [Portfolio Mode](../../backend/portfolio_mode.py) reads Coinbase Advanced Trade account, product, fill and order data with a view-only key. The paper experiment uses only the input file passed to its command. Run it from a checkout of this branch on any machine with Python 3.

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

The next coding task is a read-only input adapter that pairs a user-selected position slice and verified acquisition cost with timestamped Coinbase bids and observable size. Reuse Portfolio Mode's read path. Skip assets with unknown cost basis and reject stale or incomplete inputs before deciding an exit. Choose a fixed observation window and compare predeclared exits against holding the same slice to the same endpoint, including conservative cost and liquidity assumptions. Review results on untouched windows before enabling any order submission.

[Coinbase for Agents](https://docs.cdp.coinbase.com/ai-agents/coinbase-for-agents/coinbase-mcp) is an interactive order path. A later automated execution project would use a separate, explicitly approved trading portfolio with an asset allowlist, order and daily size limits, duplicate-order protection and a stop control. Keep trading credentials out of research and Cloud development. Instant Radar's research status is tracked in its [own branch checkpoint](https://github.com/tgpetrie/moonwalking/blob/codex/instant-radar-20261028/docs/ai/RESUME_HERE.md).
