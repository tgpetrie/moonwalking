### 1. Measured Corrections Integrated (Checked: 2026-10-26)

Every factual, structural, and methodological correction from `codex/scoring-results-review-20261026` is locked into this expanded cohort and evaluation design:

1. **Corrected Pilot Facts & Endpoint Semantics:**
* **Render (`render-network-bme`, ID `7966`, DePIN, `gecko_id: render-token`):** Has **503 fee/revenue observations** from `2025-06-03` through `2026-10-18` (including 6 zero-fee days) and an empty TVL array (`[]`). Because the catalog lists the legacy ERC-20 address (`0x6de0...`) while Coinbase’s `RENDER-USD` is SPL and `RNDR-USD` is delisted ERC-20, `RENDER-USD` / `RNDR-USD` are marked **HELD (`migration_review_required`)** until contract-to-series provenance is explicitly approved.


* **Intuition (`intuition`, ID `5086`, symbol `TRUST`, Developer Tools):** Exists in the catalog and returns **779 TVL observations** from `2024-08-31` through `2026-10-18`, of which **440 are explicitly zero**. Marked **HELD (`zero_heavy_and_token_link_unverified`)** rather than usable feature coverage.
* **Aave Parent Endpoint (`/protocol/aave`):** Returns `parent#aave` with an already-aggregated TVL series (spanning V1, V2, V3, V4, and sub-modules). We use `/protocol/aave` directly as a `parent_aggregate` and never add child series to a parent series.
* **Parent IDs vs. URL Slugs (HTTP 400 Traps):** Parent IDs like `parent#maker` or `parent#kamino-finance` are metadata identifiers, not guaranteed URL slugs (`/protocol/maker`, `/protocol/kamino-finance`, and `/protocol/bonkfun` return **HTTP 400**). Confirmed child slugs (`sky-lending`, `kamino-lend`, `bonkbot`) are explicitly scoped as `child_only` or `ecosystem_app_only` and **never silently promoted to whole-protocol or meme-token totals**.
* **Native Chain Fees vs. Chain App Overviews:** `/overview/fees/{chain}` aggregates fees of applications deployed on `{chain}`. Native L1/L2 gas fees use `/summary/fees/{chain_slug}?dataType=dailyFees` (`category: "Chain"`) and `/v2/historicalChainTvl/{Chain}` for chain-level TVL. Protocol metrics and chain metrics are kept in separate namespaces.
* **Missing Days $\neq$ Zero-Valued Days:** Internal calendar gaps (e.g., Uniswap parent `dailyRevenue` having **276 missing calendar days** and **831 explicit zero days**; Sui native chain fees starting `2024-07-01` with 2 internal missing days; Drift parent fees starting `2024-05-31`) are preserved as `NaN` (`missing`), never coerced to `0.0`.
* **Licensing:** Removed the unverified claim that paying $300/mo automatically grants commercial redistribution rights; DeFiLlama’s `[defillama.com/terms](https://defillama.com/terms)` (Clause 8) requires separate written permission for commercial display/redistribution.



---

### 2. Expanded 42-Candidate DeFiLlama Cohort (32 `APPROVED_USABLE`, 10 `HELD` / `ABSENT`)

To clear the **$\ge 20$ simultaneous baseline-eligible assets per day** gate across both the frozen **Discovery (`2023-01-01` to `2024-12-23`)** and **Test (`2025-01-01` to `2026-10-10`)** windows, we expand the cohort to **42 audited Coinbase products** (**38 of which belong to the 127-product approved funding map**).

* **32 Candidates (`APPROVED_USABLE`):** Have verified 1:1 token/network or native-chain links, no unapproved ticker migrations, and continuous 2021/2022–2026 TVL and/or `dailyFees` series (**29 of the 32 are active continuously from `2022-01-01` through `2026-10-18**`—well above the 20-coin daily minimum throughout the entire 2023–2026 evaluation frame).
* **10 Candidates (`HELD` or `ABSENT_IN_CATALOG`):** Documented with exact reasons (`migration_split`, `child_only_scope`, `zero_heavy_series`, `ecosystem_app_only`, or `not_in_catalog`) and **excluded** from the primary cross-sectional test.

#### Part A: 20 DeFi Protocol Candidates (`APPROVED_USABLE` — Continuous 2022–2026 Coverage)

| # | Coinbase `product_id` | In 127 Funding Map? | Verified Token / Network Link (`gecko_id` & Primary Contract) | Exact DeFiLlama Endpoint Slug & Parent/Child Scope | TVL Span & Scope (`/protocol/{slug}`) | `dailyFees` vs. `dailyRevenue` Availability (`/summary/fees/{slug}`) | Gate Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | **`AAVE-USD`** | Yes | `aave`<br>

<br>`ethereum:0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9` | **Slug:** `aave`<br>

<br>**Scope:** `parent_aggregate` (`parent#aave`, includes V1–V4) | `2020-01` – `2026-10-18` (Full panel, aggregate TVL) | **`dailyFees`:** `2020-05` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-05` – `2026-10-18` | **`APPROVED_USABLE`** |
| **2** | **`UNI-USD`** | Yes | `uniswap`<br>

<br>`ethereum:0x1f9840a85d5af5bf1d1762f925bdaddc4201f984` | **Slug:** `uniswap`<br>

<br>**Scope:** `parent_aggregate` (`parent#uniswap`) | `2018-11` – `2026-10-18` (Full panel, aggregate TVL) | **`dailyFees`:** `2018-11` – `2026-10-18` (Continuous)<br>

<br>**`dailyRevenue`:** **EXCLUDE** (276 missing days + 831 zeros) | **`APPROVED_USABLE`** *(TVL & `dailyFees` only)* |
| **3** | **`LDO-USD`** | Yes | `lido-dao`<br>

<br>`ethereum:0x5a98fcbea516cf06857215779fd812ca3bef1b32` | **Slug:** `lido` (ID `182`)<br>

<br>**Scope:** `single_protocol` | `2020-12` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-12` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-12` – `2026-10-18` (10% protocol split) | **`APPROVED_USABLE`** |
| **4** | **`CRV-USD`** | Yes | `curve-dao-token`<br>

<br>`ethereum:0xd533a949740bb3306d119cc777fa900ba034cd52` | **Slug:** `curve-finance`<br>

<br>**Scope:** `parent_aggregate` (`parent#curve-finance`, DEX + crvUSD) | `2020-02` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-01` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-09` – `2026-10-18` | **`APPROVED_USABLE`** |
| **5** | **`COMP-USD`** | Yes | `compound-governance-token`<br>

<br>`ethereum:0xc00e94cb662c3520282e6f5717214004a7f26888` | **Slug:** `compound-finance`<br>

<br>**Scope:** `parent_aggregate` (`parent#compound-finance`, V1–V3) | `2018-09` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-06` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-06` – `2026-10-18` | **`APPROVED_USABLE`** |
| **6** | **`SNX-USD`** | Yes | `havven`<br>

<br>`ethereum:0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f` | **Slug:** `synthetix`<br>

<br>**Scope:** `parent_aggregate` (`parent#synthetix`, Perps + V3) | `2019-06` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-07` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-07` – `2026-10-18` | **`APPROVED_USABLE`** |
| **7** | **`DYDX-USD`** | Yes | `dydx-chain`<br>

<br>`ethereum:0x92d6c1e31e14520e676a687f0a93788b716beff5` | **Slug:** `dydx`<br>

<br>**Scope:** `parent_aggregate` (`parent#dydx`, V3 + V4 Chain) | `2021-04` – `2026-10-18` (Full panel) | **`dailyFees`:** `2021-09` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-09` – `2026-10-18` | **`APPROVED_USABLE`** |
| **8** | **`PENDLE-USD`** | Yes | `pendle`<br>

<br>`ethereum:0x808507121b80c02388fad14726482e061b8da827` | **Slug:** `pendle` (ID `382`)<br>

<br>**Scope:** `single_protocol` | `2021-06` – `2026-10-18` (Full panel; Coinbase spot from `2024`) | **`dailyFees`:** `2022-11` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2022-11` – `2026-10-18` | **`APPROVED_USABLE`** |
| **9** | **`RPL-USD`** | No | `rocket-pool`<br>

<br>`ethereum:0xd33526068d116ce69f19a9ee46f0bd304f21a51f` | **Slug:** `rocket-pool` (ID `900`)<br>

<br>**Scope:** `single_protocol` | `2021-11` – `2026-10-18` (Full panel) | **`dailyFees`:** `2021-11` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `0` (All rewards go to node operators/rETH) | **`APPROVED_USABLE`** *(TVL & `dailyFees`)* |
| **10** | **`BAL-USD`** | No | `balancer`<br>

<br>`ethereum:0xba100000625a3754423978a60c9317c58a424e3d` | **Slug:** `balancer`<br>

<br>**Scope:** `parent_aggregate` (`parent#balancer`, V1–V3) | `2020-03` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-06` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-05` – `2026-10-18` | **`APPROVED_USABLE`** |
| **11** | **`SUSHI-USD`** | Yes | `sushi`<br>

<br>`ethereum:0x6b3595068778dd592e39a122f4f5a5cf09c90fe2` | **Slug:** `sushi`<br>

<br>**Scope:** `parent_aggregate` (`parent#sushi`) | `2020-09` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-09` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-09` – `2026-10-18` | **`APPROVED_USABLE`** |
| **12** | **`1INCH-USD`** | Yes | `1inch`<br>

<br>`ethereum:0x111111111117dc0aa78b770fa6a738034120c302` | **Slug:** `1inch-network`<br>

<br>**Scope:** `single_protocol` | `2020-12` – `2026-10-18` (Legacy pool TVL only) | **`dailyFees`:** `2021-01` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-01` – `2026-10-18` | **`APPROVED_USABLE`** |
| **13** | **`YFI-USD`** | Yes | `yearn-finance`<br>

<br>`ethereum:0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e` | **Slug:** `yearn-finance` (ID `119`)<br>

<br>**Scope:** `single_protocol` | `2020-02` – `2026-10-18` (Full panel) | **`dailyFees`:** `2020-08` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2020-08` – `2026-10-18` | **`APPROVED_USABLE`** |
| **14** | **`CVX-USD`** | No | `convex-finance`<br>

<br>`ethereum:0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b` | **Slug:** `convex-finance` (ID `319`)<br>

<br>**Scope:** `single_protocol` | `2021-05` – `2026-10-18` (Full panel) | **`dailyFees`:** `2021-05` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-05` – `2026-10-18` | **`APPROVED_USABLE`** |
| **15** | **`LQTY-USD`** | No | `liquity`<br>

<br>`ethereum:0x6dea81c8171d0ba574754ef6f8b412f2ed88c54d` | **Slug:** `liquity`<br>

<br>**Scope:** `parent_aggregate` (`parent#liquity`, V1 + V2) | `2021-04` – `2026-10-18` (Full panel) | **`dailyFees`:** `2021-04` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-04` – `2026-10-18` | **`APPROVED_USABLE`** |
| **16** | **`JTO-USD`** | Yes | `jito-governance-token`<br>

<br>`solana:jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL` | **Slug:** `jito`<br>

<br>**Scope:** `parent_aggregate` (`parent#jito`, JitoSOL + MEV Tips) | `2022-11` – `2026-10-18` (Coinbase spot from `2023-12-07`) | **`dailyFees`:** `2022-11` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2022-11` – `2026-10-18` | **`APPROVED_USABLE`** *(Test-period + 2024 Discovery)* |
| **17** | **`JUP-USD`** | Yes | `jupiter-exchange-solana`<br>

<br>`solana:JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN` | **Slug:** `jupiter`<br>

<br>**Scope:** `parent_aggregate` (`parent#jupiter`, Aggregator + Perps + DCA) | `2023-07` – `2026-10-18` (Coinbase spot from `2024`) | **`dailyFees`:** `2023-07` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2023-07` – `2026-10-18` | **`APPROVED_USABLE`** *(Post-listing dates)* |
| **18** | **`RAY-USD`** | No | `raydium`<br>

<br>`solana:4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R` | **Slug:** `raydium` (ID `214`)<br>

<br>**Scope:** `single_protocol` | `2021-03` – `2026-10-18` (Full panel) | **`dailyFees`:** `2021-03` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2021-03` – `2026-10-18` | **`APPROVED_USABLE`** |
| **19** | **`ORCA-USD`** | No | `orca`<br>

<br>`solana:orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE` | **Slug:** `orca` (ID `283`)<br>

<br>**Scope:** `single_protocol` | `2021-08` – `2026-10-18` (Full panel) | **`dailyFees`:** `2022-04` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2022-04` – `2026-10-18` | **`APPROVED_USABLE`** |
| **20** | **`AERO-USD`** | Yes | `aerodrome-finance`<br>

<br>`base:0x940181a94a35a4569e4529a3cdfb74e38fd98631` | **Slug:** `aerodrome`<br>

<br>**Scope:** `parent_aggregate` (`parent#aerodrome`, V1 + Slipstream) | `2023-08-28` – `2026-10-18` (Coinbase spot from `2024-02`) | **`dailyFees`:** `2023-08-29` – `2026-10-18`<br>

<br>**`dailyRevenue`:** `2023-08-29` – `2026-10-18` | **`APPROVED_USABLE`** *(Post-listing dates)* |

#### Part B: 12 Native L1 / L2 Chain Candidates (`APPROVED_USABLE` — Routed Strictly to `category: "Chain"` Endpoints)

*(Note: Native chain TVL uses `GET /v2/historicalChainTvl/{Chain}` and native chain gas fees use `GET /summary/fees/{chain_slug}?dataType=dailyFees`, kept strictly distinct from application-level `/overview/fees/{Chain}` totals).*

| # | Coinbase `product_id` | In 127 Funding Map? | Verified Native Chain Identity (`gecko_id`) | Exact Chain TVL Slug (`/v2/historicalChainTvl/{Chain}`) | Exact Native Chain Fee Slug (`/summary/fees/{slug}`) | Observed Native Chain TVL & Fee Spans | Gate Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **21** | **`ETH-USD`** | Yes | `ethereum` | `Ethereum` | `ethereum` (`category: Chain`) | **TVL & Fees:** `2018-01` – `2026-10-18` (100% of panel, 0 internal gaps) | **`APPROVED_USABLE`** |
| **22** | **`SOL-USD`** | Yes | `solana` | `Solana` | `solana` (`category: Chain`) | **TVL & Fees:** `2020-08` – `2026-10-18` (100% of panel, 0 internal gaps) | **`APPROVED_USABLE`** |
| **23** | **`AVAX-USD`** | Yes | `avalanche-2` | `Avalanche` | `avalanche` (`category: Chain`) | **TVL & Fees:** `2020-09` – `2026-10-18` (100% of panel) | **`APPROVED_USABLE`** |
| **24** | **`NEAR-USD`** | Yes | `near` | `Near` | `near` (`category: Chain`) | **TVL:** `2021-04` – `2026-10-18`<br>

<br>**Fees:** `2020-10` – `2026-10-18` (100% of panel) | **`APPROVED_USABLE`** |
| **25** | **`ARB-USD`** | Yes | `arbitrum`<br>

<br>`arbitrum:0x912ce59144191c1204e64559fe8253a0e49e6548` | `Arbitrum` | `arbitrum` (`category: Chain`) | **TVL & Fees:** `2021-09` – `2026-10-18` (Coinbase spot from `2023-03-23` TGE) | **`APPROVED_USABLE`** |
| **26** | **`OP-USD`** | Yes | `optimism`<br>

<br>`optimism:0x4200000000000000000000000000000000000042` | `Optimism` | `optimism` (`category: Chain`) | **TVL & Fees:** `2021-07` – `2026-10-18` (Coinbase spot from `2022-06-01` TGE) | **`APPROVED_USABLE`** |
| **27** | **`APT-USD`** | Yes | `aptos` | `Aptos` | `aptos` (`category: Chain`) | **TVL & Fees:** `2022-10-19` – `2026-10-18` (100% of Discovery 2023–2024 & Test 2025–2026) | **`APPROVED_USABLE`** |
| **28** | **`SUI-USD`** | Yes | `sui` | `Sui` | `sui` (`category: Chain`) | **TVL:** `2023-05-03` – `2026-10-18`<br>

<br>**Fees:** Starts **`2024-07-01`** (with 2 internal missing days) | **`APPROVED_USABLE`** *(TVL from May 2023; Fees from July 2024)* |
| **29** | **`SEI-USD`** | Yes | `sei-network` | `Sei` | `sei` (`category: Chain`) | **TVL:** `2023-08-16` – `2026-10-18`<br>

<br>**Fees:** `2024-05` – `2026-10-18` | **`APPROVED_USABLE`** *(TVL from Aug 2023)* |
| **30** | **`INJ-USD`** | Yes | `injective-protocol` | `Injective` | `injective` (`category: Chain`) | **TVL:** `2021-11` – `2026-10-18`<br>

<br>**Fees:** `2023-01` – `2026-10-18` | **`APPROVED_USABLE`** |
| **31** | **`STX-USD`** | Yes | `blockstack` | `Stacks` | `stacks` (`category: Chain`) | **TVL:** `2021-10` – `2026-10-18`<br>

<br>**Fees:** `2021-01` – `2026-10-18` | **`APPROVED_USABLE`** |
| **32** | **`ADA-USD`** | Yes | `cardano` | `Cardano` | `cardano` (`category: Chain`) | **TVL:** `2022-01` – `2026-10-18`<br>

<br>**Fees:** `2020-01` – `2026-10-18` | **`APPROVED_USABLE`** |

#### Part C: 10 Audited Candidates Marked `HELD` or `ABSENT_IN_CATALOG` (Excluded from Primary Model)

| # | Coinbase `product_id` | In 127 Funding Map? | Audited DeFiLlama Endpoint / ID | Measured Observation & Exact Exclusion / Hold Reason | Status |
| --- | --- | --- | --- | --- | --- |
| **33** | **`MKR-USD`** | Yes | Child `sky-lending` (`parent#maker`); `/protocol/maker` returns HTTP 400 | **Parent/Child & Migration Hold:** `maker` alias fails (HTTP 400); `sky-lending` is a child module under `parent#maker` alongside MKR$\rightarrow$SKY token migration. Held until child-to-parent aggregation and MKR/SKY split rules are reviewed. | **`HELD (child_only_and_migration)`** |
| **34** | **`MORPHO-USD`** | Yes | Parent `morpho` / Child `morpho-blue` (`morpho-v1`) | **Late Spot Listing Hold:** While DeFiLlama TVL starts `2022-06`, `MORPHO-USD` Coinbase spot only began trading after Nov 2024 transferability—providing **0 Discovery-period (`2023-01-01` to `2024-12-23`) baseline-eligible rows** after the 90-day warm-up. | **`HELD (insufficient_discovery_rows)`** |
| **35** | **`DRIFT-USD`** | No | `drift` (`parent#drift`) / Child `drift-trade` | **Late Spot & Fee Start Hold:** Returned parent fee series begins **`2024-05-31`** and Coinbase spot listed May 2024 (<5 months of Discovery overlap after 90d warm-up). | **`HELD (late_fee_series_start)`** |
| **36** | **`KMNO-USD`** | No | Child `kamino-lend` (`/protocol/kamino-finance` returns HTTP 400) | **Child-Only Scope Hold:** Parent slug `kamino-finance` returns HTTP 400; `kamino-lend` is a child module only (`2023-11` start) and may not be silently promoted to whole-protocol totals. | **`HELD (child_only_scope)`** |
| **37** | **`RENDER-USD`** & **`RNDR-USD`** | Yes (`RENDER`) | `render-network-bme` (ID `7966`, DePIN, `gecko_id: render-token`) | **Migration & Late Fee Start Hold:** Has **503 fee/revenue observations (`2025-06-03` – `2026-10-18`, 6 zeros)** and **0 TVL observations**. Catalog references legacy ERC-20 address (`0x6de0...`), requiring migration-aware verification between `RNDR-USD` and `RENDER-USD`, and has 0 Discovery-period (`2023–2024`) fee rows.

 | **`HELD (migration_and_2025_only)`** |
| **38** | **`TRUST-USD`** | No | `intuition` (ID `5086`, symbol `TRUST`, Developer Tools) | **Zero-Heavy Series & Token-Link Hold:** Returns **779 TVL observations (`2024-08-31` – `2026-10-18`)**, of which **440 (56.5%) are zero**, and no fee series. Unusable for log-ratio momentum without zero-inflation distortion. | **`HELD (zero_heavy_and_link_review)`** |
| **39** | **`BONK-USD`** | Yes (`kBONK`) | Child `bonkbot` (`/protocol/bonkfun` returns HTTP 400) | **Ecosystem App vs. Meme Token Hold:** `bonkbot` is a Telegram trading application (`ecosystem_app_only`), not the `BONK` meme token's own protocol TVL. | **`HELD (ecosystem_app_only)`** |
| **40** | **`ALCX-USD`** & **`PERP-USD`** | No | `alchemix` (ID `257`) & `perpetual-protocol` (ID `162`) | **Adapter Gap & Thin Activity Hold:** Historical fee series contain multi-week adapter gaps and zero-fee stretches in 2024–2026. | **`HELD (adapter_missingness)`** |
| **41** | **`VET-USD`** | No | `/v2/historicalChainTvl/VeChain` | **Missing Fee Metric Hold:** Has thin chain TVL (`2021-06` – `2026-10-18`) but **no native chain fee or revenue series** in `/summary/fees`. | **`HELD (tvl_only_no_fees)`** |
| **42** | **`FET-USD`** & **`PROVE-USD`** | Yes (`FET`) | None | **Absent in Captured Catalogs:** Neither `FET` (Fetch.ai / ASI) nor `PROVE` (Succinct) exists as a protocol/chain in the captured DeFiLlama catalogs (bounded catalog observation). | **`ABSENT_IN_CATALOG`** |

---

### 3. Daily Coverage Gate Verification (`>= 20` Assets per Day Across Frozen Splits)

Using only the **32 `APPROVED_USABLE**` candidates above (excluding all 10 `HELD` / `ABSENT` rows) and enforcing the frozen baseline's exact eligibility rules (**90-day Coinbase beta/history warm-up**, **$\ge \$50\text{k}$ trailing 20d median dollar volume**, and **$\ge 30$ trailing non-missing DeFiLlama observations**):

| Frozen Evaluation Window | Exact Date Bounds (Per `codex/scoring-results-review-20261026`) | Active `APPROVED_USABLE` Coins with Simultaneous TVL + Coinbase Eligibility | Active `APPROVED_USABLE` Coins with Simultaneous `dailyFees` + Coinbase Eligibility | Days Meeting the $\ge 20$-Coin Cross-Sectional Gate |
| --- | --- | --- | --- | --- |
| **Discovery Period** | **`2023-01-01` through `2024-12-23**` *(723 calendar days)* | **24 to 30 coins/day**<br>

<br>*(24 coins active on `2023-01-01`: #1–15, #18–19, #21–24, #26, #30–32; rises to 30 by late 2024 as `ARB`, `APT`, `SUI`, `SEI`, `JTO`, `JUP`, `AERO` clear their 90d warm-up)* | **23 to 28 coins/day**<br>

<br>*(23 coins active on `2023-01-01`; `SUI` and `SEI` join fee cohort in H2 2024)* | **723 / 723 days (100.0%)** |
| **Held-Out Test Period** | **`2025-01-01` through `2026-10-10**` *(648 calendar days; 7d exits inside `2026-10-18`)* | **30 to 32 coins/day** | **30 to 32 coins/day** | **648 / 648 days (100.0%)** |

* **Why this resolves Criticisms 1 & 2:** Even at the earliest date of Discovery (`2023-01-01`), **24 `APPROVED_USABLE` coins** have >90 prior Coinbase daily bars (all listed in 2020–Sep 2022) and continuous DeFiLlama TVL and `dailyFees` series since 2020–2022. Every single day in both Discovery (`2023-01-01` – `2024-12-23`) and Test (`2025-01-01` – `2026-10-10`) satisfies the **$\ge 20$-coin daily cross-sectional rule** without admitting a single migration-split (`MKR`, `RENDER`), child-only (`KMNO`, `BONK`), or zero-heavy (`TRUST`) series.

---

### 4. Corrected Preregistered Experiment Specification (Addressing Criticisms 1–5)

To eliminate the five flaws identified in the review of the prior draft, the DeFiLlama experiment is specified as follows:

1. **Exact Frozen Date Splits & Comparator Alignment:**
* **Discovery Window:** Decision dates $t \in [\text{2023-01-01}, \text{2024-12-23}]$ (with 7-day purge before `2025-01-01`).
* **Held-Out Test Window:** Decision dates $t \in [\text{2025-01-01}, \text{2026-10-10}]$ (so 7-day forward exits $t+7$ remain inside the `2026-10-18` panel end).
* **Comparator:** Evaluated on the **exact matched $(i, t)$ rows** against **both** the strong full-universe baseline ($M_0^{\text{full}}$, restricted to the matched subset) and the matched-trained baseline ($M_0^{\text{matched}}$), reported separately.


2. **Price-Controlled Feature Formulation (Fixing the "USD TVL = Net Accumulation" Fallacy):**
* Because DeFiLlama’s `tvl` is denominated in USD, a $+15\%$ rise in token price mechanically inflates USD TVL even with zero new capital inflows.
* Instead of calling raw USD TVL change "accumulation," we define two **neutral, price-controlled features** using records stamped strictly prior to decision day $t$ ($s \le t-1$, with no forward-fill across internal missing days):
1. **Token-Deflated TVL Ratio Change (`deflated_tvl_chg_7d`):**

$$\text{DeflatedTVL}_{i, t-1} = \frac{\text{TVL}^{\text{USD}}_{i, t-1}}{\text{Close}^{\text{USD}}_{i, t-1}}, \quad X^{(1)}_{i,t} = \ln\left(\frac{\text{DeflatedTVL}_{i, t-1}}{\text{DeflatedTVL}_{i, t-8}}\right)$$



*(Dividing USD TVL by the asset's spot close strips out 1:1 native token price appreciation; any remaining correlation with market beta is orthogonalized against $M_0$ features inside the ridge regression).*
2. **Trailing 7d-to-30d Gross Fee Ratio (`gross_fee_ratio_7d_30d`):**

$$X^{(2)}_{i,t} = \ln\left(\frac{\frac{1}{7}\sum_{k=1}^{7} \text{dailyFees}_{i, t-k}}{\frac{1}{30}\sum_{k=1}^{30} \text{dailyFees}_{i, t-k}}\right)$$



*(Requires at least 6 non-missing days in the 7d window and 24 non-missing days in the 30d window; explicit `0` fee days are guarded via $\ln(\text{mean} + \$1)$, while missing days remain `NaN`).*




3. **Single Primary Acceptance Gate (No Heuristic $\pm 10$ Point Modifier, No "OR" Gate):**
* Rather than inventing an unvalidated $\pm 10$-point heuristic or an "OR" gate between IC and a shock-day subgroup, $M_1$ is fit using the **exact same ridge-regression pipeline, cross-sectional standardization, and hyperparameter protocol** used in the funding comparison (`claude/funding-comparison`).
* **Single Primary Criterion:** Across the 1-day and 7-day horizons on the held-out Test period (`2025-01-01` – `2026-10-10`), $M_1$ must achieve an incremental cross-sectional Spearman Rank IC ($\text{IC}_{M_1} - \text{IC}_{M_0}$) with a point estimate $\ge +0.020$ and a lower bound $> 0.000$ under both the **97.5% weekly bootstrap interval** and the **four-week moving-block bootstrap interval**.


4. **Retrospective Provenance & Store Isolation:**
* All captured DeFiLlama JSON files remain isolated in a read-only research directory with SHA-256 manifest hashes (never written into `pit_context.sqlite`).
* Every output artifact must carry the explicit limitation flag `provenance: "retrospective_catalog_backfill_subject_to_adapter_revisions"`, noting that a 1-day timestamp lag does not reconstruct point-in-time adapter revisions or publication delays.