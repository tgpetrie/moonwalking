# Cycle Strategist Flight Manual & Settings Guide

This manual explains how to fly the Cycle Strategist desk on the Agents page,
what each Mission Stance changes, and the risk concepts behind each proposal.
The same guide appears in the app. Open **Flight Manual & Settings Guide** in
the Cycle Strategist deck.

Everything the strategist does is **paper only**. No mode sends a live order.

---

## 1. Workflow

### Autonomy modes

| Deck label | Stored setting | What happens |
| --- | --- | --- |
| **Off** | `emergency_pause = true` | No proposal is approved or simulated. Desk Passes still read the market, so you can watch without acting. |
| **Mode A: Recommend** | `autonomy_mode = "approval_queue"` | Every proposal waits in the queue as `pending_approval` until you approve or reject it. No live quotes are fetched. |
| **Mode B: Auto Paper** | `autonomy_mode = "auto_protect_exits"` | Protective exits (trims and stops) are paper-executed automatically against a fresh quote, within the daily auto-order budget. Entries still wait for approval. |

### Flying a Desk Pass

1. Choose a **Mission Stance** (section 2). Pick **Auto-Pilot (AI)** if you
   want the desk to choose the stance itself.
2. Press **Run Desk Pass** (`POST /api/agents/run-cycle-pass`). The pass:
   - reads the cached macro cycle scan for your held and watchlist coins;
   - resolves the effective stance;
   - runs the strategist;
   - applies the cluster and beta heat guard;
   - persists the proposals.
3. If the cached scan is not usable yet, the pass returns `status: "skipped"`
   with `reason: "no_cycle_scan"` and changes nothing.
4. Review the proposals. Each one shows its evidence, plus the stance that
   produced it (`configured_stance` and `effective_stance` in `evidence`).

### From trim to a 3-rung reload ladder

1. A **`TRIM_TO_USDC`** proposal appears when a held coin enters its rollover
   target box. The trim size grows with depth into the box, and the stance
   scales it (section 2). The proposal is capped at 90%.
2. Approve it. The paper desk sells the trim, deducts fees and slippage, and
   books the freed USDC.
3. The trim carries a **reload plan**: three limit rungs inside the support box
   below. The freed USDC is split across the rungs by the ladder weights.
4. When price reaches a rung, a **reload** proposal appears. Approve each rung
   to buy back more coins than you sold. That gain is the coin-stack
   compounding (section 3).

---

## 2. Mission Stances

The stance sets the risk envelope for the whole desk. **Low-Lunar Orbit** is
the default and matches the desk's pre-stance behaviour exactly.

| Stance | Key | Posture | Portfolio heat cap | Cluster heat cap | Coins per cluster | Risk per entry | Trim fraction | Base ladder (shallow / mid / deep) | Entry rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Lunar Bunker** | `bunker` | Defensive | 2.5% | 1.0% | 1 | 0.5% | 50% | 15 / 30 / 55 | New entries only from `deep_accumulation_exhaustion`, or with confluence ≥ 75. Rotation leaders are filtered out. |
| **Low-Lunar Orbit** | `orbit` | Balanced (default) | 5.0% | 2.0% | 2 | 1.0% | 35% | 25 / 35 / 40 | Standard accumulation, breakout and reload entries. |
| **Gravity Assist** | `gravity_assist` | Bullish conviction | 7.5% | 3.0% | 3 | 1.5% | 25% | 40 / 35 / 25 | Standard entries with larger size. |
| **Full Burn** | `full_burn` | Aggressive | 10.0% | 4.0% | 4 | 2.0% | 15% | 50 / 30 / 20 | Also enters `low_confirmation_breakout` and `early_markup` coins with confluence ≥ 55. |
| **Auto-Pilot (AI)** | `autopilot` | Regime-adaptive | — | — | — | — | — | — | Picks one of the four stances above on every pass. |

**Trim fraction** scales the dynamic trim relative to Orbit's 35%. For
example, at the midpoint of the rollover box:

| Stance | Trim at box midpoint |
| --- | --- |
| Orbit | 37.5% |
| Bunker | 53.6% |
| Full Burn | 16.1% |

Reload rungs are never gated by the stance. A reload buys back a coin you
already trimmed.

### When to use each stance

- **Lunar Bunker**: risk-off macro, a late cycle, or rollover tops across the
  board. Trim heavily, keep entries scarce, and buy the deep rung hardest.
- **Low-Lunar Orbit**: the default when the regime is mixed or you are unsure.
- **Gravity Assist**: alt liquidity has rotated (Stage 3 or 4) and breadth
  agrees. Hold more, trim less, and buy the shallow rung harder.
- **Full Burn**: a confirmed alt-season expansion when you accept the largest
  drawdowns. Take early breakouts, trim lightly and reload fast.
- **Auto-Pilot (AI)**: let the regime decide. This is the best fit if you do
  not want to retune the desk by hand as the cycle turns.

### Auto-Pilot rules

`resolve_autopilot_stance(cycle_scan)` is pure and deterministic. The first
rule that matches wins:

1. The macro regime is unavailable → **Lunar Bunker**.
2. The macro gate is `risk_off_headwind` → **Lunar Bunker**.
3. At least 40% of readable Atlas coins are in `rollover_profit_zone` →
   **Lunar Bunker**.
4. All of the following → **Full Burn**:
   - the stage is `stage_3_alt_index_breakout` or `stage_4_alt_season_expansion`;
   - the gate is `risk_on_aligned`;
   - at least 50% of readable coins are in `low_confirmation_breakout`,
     `growth_expansion_ride` or `early_markup`;
   - under 25% of readable coins are in rollover.
5. Stage 3 or 4 with a `risk_on_aligned` gate → **Gravity Assist**.
6. Otherwise → **Low-Lunar Orbit**.

The bucket distribution counts only when at least 10 coin rows can be read.
The deck shows the selected gear and its plain-English reason in the
**Auto-Pilot status** callout. The metrics behind the choice are in
`effective_stance_metrics`.

> **Confluence note.** The confluence gates read a row's `confluence_score`.
> Every readable Atlas row now carries one: a deterministic 0–100 blend of
> structure position in the multi-year range (35%), weekly RSI (25%),
> volume trend and 50-week SMA / MACD alignment (25%) and downside-BTC-beta
> resilience (15%). The parts are in `confluence_components`. So Bunker's
> ≥ 75 path and Full Burn's ≥ 55 low-confirmation-breakout path are live.
> The scan has no `early_markup` bucket, so that Full Burn path stays closed.
> A legacy `confluence` key given as a 0–1 fraction is still scaled to 100.

---

## Workspace and Coin Dossier

The home board has three focused views:

- **Live Tape** (default): 1H price, 1M ignition and side-by-side 3M
  confirmation gainers/losers, with the live 1H volume banner.
- **Cycle Atlas & Pulse**: Industry Pulse cycle buckets, Live Strength,
  the intelligence log and watchlist.
- **Mission Control (Agents)**: the strategist deck, Mission Stances,
  Compounding Scoreboard and agent evidence.

Open any coin for its unified **Coin Dossier Card**. Its Composite
Conviction Score is an equal-weight average of Tape Momentum, Cycle
Position and Volume & Sentiment Confirmation. Each gauge is 0–100;
missing inputs are excluded, and a composite requires all three gauges.
This is an explanatory evidence summary, not a calibrated probability.
Tape Momentum blends 1M/3M velocity and relative-strength rank.
Cycle Position favors the lower end of the observed multi-year range.
Confirmation combines volume change, persistence and weekly RSI proximity
to neutral; an active exhaustion/reversal warning caps it at 35.
Sentiment and the next trigger are stated in plain English, not assigned
invented numeric values. Pulse evidence, Risk Levels and Intel expand
within this card. Owner paper controls are collapsed and absent on
unauthenticated/forbidden responses.

Choose **Cycle (Multi-Year)** for the historical PEAK / A / B / C / D / E
map, dated pivots, base boundaries and projected structural levels. A
one-click shortcut appears when the swing read has no clear setup.
Anatomy uses all loaded daily history with flash-wick filtering; the
existing range indicators retain their trailing three-year window.
An established weekly five-leg channel supplies the A–E pivots, resolved
to exact daily extrema; otherwise the largest counter-rally before the
macro low supplies A/B and a later rally/retest supplies D/E. Unestablished
pivots remain missing rather than being fabricated.

The base starts no earlier than A, within a maximum 2×-floor range, and
excludes the latest seven bars from its ceiling so a fresh breakout can
be recognized. Its duration is a deterministic structural estimate, not
proof that every intervening month accumulated. Targets show the prior B
high and arithmetic 0.382 / 0.618 retracements from the macro high to C.
They are named structural references, not necessarily ascending prices
or guaranteed upside. The floor includes a lower E retest if present.
The story and target distances refer to the latest daily close, not an
executable live quote.

## 3. Risk concepts in plain English

### Downside BTC beta heat

"Heat" is the share of equity you would lose if every open position hit its
stop. A coin that falls harder than BTC on red days carries more real risk
than its stop distance suggests. Its heat is therefore multiplied by
`max(1, downside_beta / 1.25)`, where `downside_beta` is its beta to BTC on
down days. A coin with a downside beta of 2.5 counts double. New entries are
held back with `suppression_reason: "beta_adjusted_heat_cap_exceeded"` once
beta-adjusted heat would pass the stance's heat cap.

### 11-cluster concentration caps

Coins in the same narrative move together, so ten meme coins are one bet, not
ten. Every coin maps to **majors** or to one of 11 sectors:

1. layer-1
2. layer-2
3. defi
4. oracle-data
5. ai-compute
6. meme
7. gaming-metaverse
8. nft-marketplaces
9. payments
10. storage-infra
11. privacy

An unmapped coin forms its own cluster. Each cluster is limited by the
stance's **cluster heat cap** and **coins per cluster**. Blocked entries are
listed under `cluster_guard.suppressed_proposals` with
`suppression_reason: "cluster_heat_cap_exceeded"` or
`"cluster_count_cap_exceeded"`.

### Adaptive wick-tilted ladders (`weight_source`)

The reload ladder starts from the stance's base split. When the Atlas cache
holds fresh daily history for the coin, `ladder_optimizer` reads how deep past
wicks reached into the support box and tilts the weights:

- **Deep-wick regime**: more USDC on the deep rung.
- **Shallow regime**: more USDC on the shallow rung.

The plan's `weight_source` field reports which split was used:

- `"ladder_optimizer"`: the optimizer tilted the weights. Its regime, fill
  probabilities and expected extra coins are listed under `ladder_optimizer`.
- `"default"`: there was no usable history, so the base split was used as-is.

`base_ladder_weights` appears on the plan only when the stance's base differs
from Orbit's 25 / 35 / 40.

### 60 bps fee + 10 bps slippage

Every paper fill assumes a **60 bps (0.60%) taker fee** and **10 bps (0.10%)
slippage** on each side. These are set by `MW_CYCLE_FEE_BPS` and
`MW_CYCLE_SLIPPAGE_BPS`. A full round trip, trim then reload, costs about
1.4% before price moves. Each proposal records its `cost_model`, so the
numbers stay auditable after the settings change.

### Net-of-fees coin-stack compounding

The goal is **more coins**, not more dollars. The freed USDC is the trim
proceeds after fees and slippage, and only that amount funds the ladder. The
compounding summary reports:

- the extra coins gained after reloads;
- the USDC still waiting on unfilled rungs;
- the fees and slippage deducted.

A trim-and-reload cycle counts as a win only if the coins bought back exceed
the coins sold after all costs.

---

## 4. API reference

| Route | Method | Notes |
| --- | --- | --- |
| `/api/agents/settings` (alias of `/api/agents/autonomy`) | GET | Returns `autonomy` (with `stance`) and the stance readout. |
| `/api/agents/settings` | POST | Accepts `stance` (one of `autopilot`, `bunker`, `orbit`, `gravity_assist`, `full_burn`) together with the existing autonomy fields. An invalid stance returns **400** and leaves the settings unchanged. |
| `/api/agents/proposals` | GET | Includes the stance readout. |
| `/api/agents/run-cycle-pass` | POST | Includes the stance readout on both `ok` and `skipped` passes. |

The **stance readout** fields are:

- `configured_stance`
- `effective_stance`
- `effective_stance_reason`
- `effective_stance_metrics` (Auto-Pilot only)
- `stance_profiles`

All of these routes are owner-only and return `Cache-Control: private, no-store`.
