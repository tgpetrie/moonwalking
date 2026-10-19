# Master Architectural & Research Handoff for Codex

Date: 2026-10-19. Repository: `tgpetrie/moonwalking`.

This document consolidates the supplied architectural draft with committed
Moonwalking research and implementation records. Read the
[checked review](MASTER_HANDOFF_REVIEW_2026-10-19.md) from upstream `09011e3c`
together with [Claude's handoff](HANDOFF_FOR_CODEX_2026-10-19.md); their verified
corrections take precedence over the original Gemini text. The six-agent suite
is retained as an archived proposal and **must not be started**. Keep the existing
evidence-ID selection and Python-rendered narration.
The documentation change does not install models, change scheduled tasks,
start studies, integrate branches, or deploy application code.

## 0. Authority, provenance, and current state

Read `MW_SPEC.md`, the applicable `AGENTS.md` instructions, and
[AI_INDEX.md](../ai/AI_INDEX.md) first. Committed code and study artifacts take
precedence over imported conversations. The principal records inspected are:

| Record | Pinned revision | What it establishes |
| --- | --- | --- |
| `claude/render-history-data` | `1f198332a78b1788dc0e4203e048d43c519906a4` | Research, validated RENDER exports, PIT schema, and [Claude's 2026-10-19 handoff](HANDOFF_FOR_CODEX_2026-10-19.md) |
| Checked master review | `09011e3c35a6125c8df66b48bec28ba184669f36` | [Line-by-line corrections](MASTER_HANDOFF_REVIEW_2026-10-19.md), imported as documentation only; the intervening `d9873046` research code was not integrated |
| `codex/macro-chart-20261018` | `fb59304a` | Separate chart implementation, AMP worker, evidence-ID narration, daily next-run map |
| Historical chart checkpoint | `0198513` | Frozen FET arithmetic reviewed in the supplied draft; not the latest chart behavior |
| PIT impact-price update | `b379d669` | Additive mid/bid-impact/ask-impact fields |

The chart branch is **not integrated into the research branch**. Links to its
files below use pinned GitHub URLs, so a reader does not mistake absent local
files for broken implementation. No main merge or production release is implied.

### Status ledger and corrections to the supplied draft

| Item | Reconciled state |
| --- | --- |
| Six specialized Qwen roles | Archived draft, not recommended or approved for implementation. Do not start the suite, social classifier, divergence narrator, or execution badges. Use deterministic status text for hygiene. |
| Local chart narrator | Already implemented on the chart branch using `qwen3.5:9b`: the model selects fact IDs and trusted Python renders sentences. Preserve that stronger boundary. |
| Sentiment runtime | Flask proxies `sentiment_api.py`; `sentiment_aggregator_enhanced.py` is a deprecated shim. The claimed active MD5 fallback is obsolete. |
| Source roles | Four roles in the salvage plan, expanded to six here by adding `event_calendar` and `onchain_flow`. |
| Divergence thresholds | `sentiment_aggregator.py` and `sentiment_config.yaml` default to 0.12 for tier1 versus tier3; high severity starts at twice that threshold. The 0.25/0.40 planning values are not implemented behavior. This is a code check, not a deployed health check. |
| Fear & Greed / CoinGecko cache TTL | Draft proposes 1 hour / 5 minutes. Research-branch code uses 300 / 120 seconds; overall sentiment cache defaults to 30 seconds. Cache TTL and stale-display windows are different. |
| Study 1 robustness | Post hoc, including the liquidity and shock splits; retain this qualification. |
| Study 2b break-rate labels | Canonical study says **LVN 39.3%, HVN 38.7%** from below in discovery; the draft reverses them. |
| Study 2b hourly parity | +0.65 vs +0.65 is the POC-from-above comparison only. POC from below is -0.18 hourly vs -0.35 daily. |
| Study 3a | Preregistered, code committed; latest pinned handoff reports downloading. `FUNDING_STUDY.md` has no results. This document does not verify current process progress. |
| Study 3b | Candidate only. No `TAKER_DELTA_STUDY.md` exists at the pinned research revision. |
| Watcher / exchange availability | Dated observations from prior machine checks, not a fresh health probe. |
| Guardrail immunity claim | Numeric echoes and a lexical denylist cannot establish factual correctness. The exact draft harness is retained as reference, with blockers below. |
| Test counts | Fresh offline run for this handoff: **59 passed** across history, studies, and PIT tests. The chart branch's 46 Python tests are a separate suite. |

### Operating boundaries

- Keep RNDR and RENDER separate, with venue, quote, and migration identity.
- Preserve the real-data-only, last-good, stale/offline, and one-board rules.
- Keep the collector on port 5003 and the installed PIT watcher untouched.
- Do not open live stores with helpers that create schemas or write metadata.
  Read PIT via SQLite `mode=ro`; use a consistent backup for long analysis.
- Do not infer a per-coin probability, price objective, timing claim, or trade
  instruction from these studies. Historical relative returns are not a
  forecast or a measured net trading return.
- Keep further implementation in a named branch/worktree. Review overlapping
  changes through committed diffs. Do not merge older design branches or resume
  the cancelled broad consolidation as a side effect of this handoff.

## 1. Archived Qwen suite: preserve the existing narration boundary

### 1.1 Runtime foundation and model mapping

Local endpoint: `http://127.0.0.1:11434/api/chat`. Numerical evidence is
computed by deterministic code before inference. Models may classify captured
text or select vetted explanations; they do not set prices, severity, thresholds,
or historical study results.

The draft's hardware tiers below are preserved for provenance only, not a
download or upgrade plan. The machine already uses `qwen3.5:9b`; no model
download is authorized by this handoff. These are not tested fit or latency guarantees:

| Nominal memory tier | Runtime candidate | Offline development candidate |
| --- | --- | --- |
| 8-12 GB | `qwen3:8b` | `qwen2.5-coder:7b` |
| 16 GB VRAM / unified memory | `qwen3:14b` | `qwen2.5-coder:14b` |
| 24 GB+ / larger unified memory | `qwen3:30b-a3b` or `qwen3.8:27b` | `qwen3-coder:30b` |

The draft describes the 30B-A3B candidate as 30B total / 3B active parameters
and the coder candidate as having a 256K context capability. These are model
characteristics to verify for the selected tag, not an inference-memory budget.
Weights, quantization, context/KV memory, and other loaded models determine fit.
The [official Qwen3.8 library entry](https://ollama.com/library/qwen3.8)
lists a 27B tag. No pulls or hardware changes are part of this handoff.

Proposed sampling controls: `temperature=0`, `top_k=1`, `seed=42`. Use
`PARAMETER seed 42` in a Modelfile or the corresponding request option;
`seed: 42` alone is not Modelfile syntax. These settings reduce variation;
they do not prove determinism across model digests, runtimes, or hardware.
Record the exact model digest and renderer/schema versions with cached output.

Pass `Schema.model_json_schema()` as `format`, then validate the content with
`Schema.model_validate_json()`. Timeout, invalid schema, missing required facts,
and model failure must produce a labelled deterministic fallback.
[Ollama's structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs)
describes this schema/validation flow.

[Ollama issue #14850](https://github.com/ollama/ollama/issues/14850) reports
`think=False` breaking structured output for **qwen3.5:27b on Ollama
0.17.7/0.18.0** and was closed as a duplicate of #14645. It is not evidence
that every Qwen3 build has a grammar conflict. Test the installed combination;
omit or change `think` only if that reproduction requires it. The existing
chart narrator's recorded working configuration has thinking disabled.

### 1.2 Six bounded roles

The following contract names and proposed Modelfile names come from the draft.
They are historical proposal details, not implementation requirements or imports
available on the research branch. Agent 1 is superseded by bounded narration;
Agent 2 needs deterministic text, not an LLM. Agents 3/4 lack captured inputs
and validated scores; Agent 5's per-coin badges are not approved. Agent 6 is
an optional personal development tool only.

#### Agent 1: Runtime Chart & Diff Translator (`chart-auditor`)

- Trigger: a new generation of `completed_weekly_evidence_hash` or
  `completed_context_layers_hash`; zero calls on unchanged evidence. These
  proposed hash names are not the existing narrator's field names.
- Input: a locked, versioned slice of atomic evidence JSON: anchor prices,
  signed distances, three pivot dates, Coinbase 30-day relative volume,
  market-wide Fear & Greed, and `what_changed_code`.
- Proposed `ClickableExplanationOutput`: `headline_state`,
  `three_date_provenance`, `math_and_invalidation`, `context_layer_note`,
  `what_changed_plain_english`.
- Explain the weekly period, actual daily extreme, and confirmation-close
  timestamp separately. Describe `P = L + r(H-L)` and the **macro low the
  calculation is anchored to**. $0.1338 is the frozen FET example, not a
  universal threshold. The draft's 2.31x volume has no source in the checked
  repository; do not display it without independently captured evidence.
- Distinguish daily cache changes from completed weekly structural changes.
  Fear & Greed remains market-wide/BTC-driven context.

The existing implementation already uses a safer output contract: the model
selects evidence IDs; Python owns all prose. Its `narration_detail.evidence_sha256`
fingerprints the fact catalog, model name, and renderer source. An unchanged
accepted plan is revalidated and rendered without another model request.
Unknown/duplicate IDs, wrong topics, omitted mandatory facts, model mismatch,
truncation, and malformed responses are rejected. See the pinned
[local narration record](https://github.com/tgpetrie/moonwalking/blob/fb59304a/docs/research/LOCAL_CHART_NARRATION_2026-10-19.md)
and [next-run map](https://github.com/tgpetrie/moonwalking/blob/fb59304a/docs/research/NEXT_RUN_MAP_2026-10-19.md).
Keep this implementation; do not add the draft free-prose fields to runtime.

#### Agent 2: SQLite hygiene and revision triage (`data-hygiene-auditor`)

- Trigger: nonempty `missing_gap_records`, candle/context revisions, or
  HTTP 429/451/403 anomalies.
- Input: the anomaly bundle, Python's `deterministic_severity`, and
  `completed_weekly_evidence_hash_changed`.
- Proposed `OperatorTriageReport`: `severity_classification`,
  `operator_headline`, `gap_and_warmup_audit`, `revision_impact_summary`,
  `required_operator_action`.
- Severity must exactly echo one of Python's classifications:
  `HEALTHY_PARITY`, `BENIGN_DAILY_REVISION`, `STALE_ROLLOVER_BACKOFF`,
  `QUARANTINED_MISSING_GAP`, `CRITICAL_WEEKLY_EVIDENCE_REVISION`.
- Model output cannot change quarantine, retry timing, data completeness, or
  severity. Repairs remain an operator/developer workflow.

#### Agent 3: PIT social, news, and GitHub classifier (`social-classifier`)

- Trigger: newly captured RSS headlines, GitHub releases, Farcaster casts,
  or approved Reddit OAuth posts. Those capture adapters are not all built.
- Input: at most 25 items, each with `item_id`, `symbol`, `source_venue`,
  `created_at_utc`, and `text`. Add the existing PIT `first_seen_utc`,
  verified identity, payload hash, and revision link at the trusted wrapper.
- Proposed `BatchClassificationOutput`: one result per input ID with
  `is_spam_or_bot: bool`, `topic_category`, and `retail_tone`.
- Topic enum: `PROTOCOL_DEV_OR_RELEASE`, `EXCHANGE_LISTING_OR_MIGRATION`,
  `MACRO_OR_REGULATORY`, `RETAIL_PRICE_EMOTION`, `NETWORK_OUTAGE_OR_BUG`,
  `IRRELEVANT_SPAM`.
- Tone enum: `EUPHORIC`, `CONSTRUCTIVE`, `NEUTRAL`, `FEARFUL`, `CAPITULATION`.
- No model-generated 0-100 score. Python filters spam and computes
  `net_tone_score` in [-1,+1] and `organic_post_count`. A tone-to-number
  mapping, denominator, deduplication rules, and minimum sample requirement
  still need a versioned specification; this handoff does not invent them.
- Reject missing, duplicate, and foreign item IDs. Captured text is data,
  never instructions. Classification time must not replace capture time.

#### Agent 4: Tier divergence and positioning narrator (`divergence-auditor`)

- Trigger proposal: a comparable pairwise normalized score gap >=0.25
  (warning), or >=0.40 (critical), detected by trusted code. These are
  planning values, not the 0.12 code default; do not implement this narrator.
- Input: tier scores/weights, source reliability/freshness, funding, open
  interest, and impact-price asymmetry. The draft names
  `EnhancedSentimentAggregator`; use the current service payload instead.
- Proposed `DivergenceExplanationOutput`: `divergence_state`,
  `venue_coverage_note`, `book_asymmetry_note`.
- Distinguish measured score from trust weight: 0.85/0.70/0.50 are weights,
  not observed sentiment values. Do not compare different scales or stale
  and fresh values as if aligned.
- Report available and blocked venues, and any deterministic confidence
  penalty for one-venue coverage. A penalty formula is not specified here.
- Explain disagreement descriptively. Negative funding alone does not
  establish short crowding, accumulation, a squeeze, or a local top.
  No directional funding interpretation before Study 3a reports.

#### Agent 5: Execution hygiene / anti-FOMO (`execution-guardrail`)

- Proposed triggers: completed-day rise >=10% with >=5x prior 20-day
  median volume; thin liquidity below $1M/day; or relative volume below
  0.5x the prior 20-day median.
- Input: `move_pct`, `volume_vs_20d_median`, `median_20d_usd_vol`, book
  measurements and a versioned empirical lookup with exact study scope.
- Proposed `ExecutionHygieneOutput`: `regime_badge`, `empirical_base_rate`.
  Badge enum: `CHASING_HAZARD_THIN_BOOK`,
  `LOW_PARTICIPATION_STAND_ASIDE`, `NORMAL_LIQUIDITY`.
- Python owns eligibility and badge selection. Missing liquidity cannot
  fall through to `NORMAL_LIQUIDITY`; use an explicit unavailable wrapper.
  The <0.5x rule and these badges are proposals, not validated study findings.
- For the studied shock subgroup, require **all** the Study 1 conditions,
  including move minus BTC >=15 percentage points. Live partial-day moves
  do not equal completed-day study events.
- `empirical_base_rate` is a legacy proposed field name: the cited -5.7%
  and -7.3% are **mean seven-day returns relative to peers**, not an event
  probability. They apply to high-volume, coin-specific spikes **across all
  liquidity tiers**. The separate <$1M/day group yields -2.4%/-2.7% at seven
  days. Do not merge those groups or ship this
  field or the per-coin badges; at most use the dated, scoped approach sentence
  in Claude's handoff when its completed-day eligibility conditions apply.
- The +6.0%/+7.8% level-arrival values use a reaction sign convention;
  they describe give-back, not positive long returns. Cite study/horizon,
  sample scope, and post-hoc status in research records only. Do not attach
  them to individual level popovers or use them as a return for this coin.
- The draft attributes the motivation to Chris Kmer's "Back-End
  Optimization" / removing C-game FOMO trades. This is supplied framing,
  not an independently verified empirical authority.

#### Agent 6: Offline developer / SQLite / fixture assistant

Candidate models: `qwen3-coder:30b` or `qwen2.5-coder:14b` (7B on the small
tier). Offline development only: inspect SQLite schema, history manifests,
study scripts, and 100-week indicator parity fixtures; propose migrations
and meaningful tests. Review generated diffs before use. No live runtime
agent, production database writes, model-controlled execution, or numerical
consensus is implied.

### 1.3 Exact draft `local_qwen_guardrails.py` reference

The supplied harness is reproduced verbatim below for review. **It is not an
installed module or an adequate production verification gate.** Keeping it
here preserves the draft without weakening the existing evidence-ID renderer.

```python
import json
import re
from typing import Any, Dict, List, Set

# Lexical denylist backed by Studies 1, 2, 2b, 2c, 2d
BANNED_PREDICTIVE_PATTERNS = [
    r"(?<!no\s)(?<!not\sa\s)\btarget(?:s|ed)?\b(?!\sand\sinvalidation\stouched)",
    r"(?<!no\s)\bforecast(?:s|ed|ing)?\b(?!\sdate)",
    r"\bprobab(?:le|ility|ilities)\b",
    r"\blikely\b",
    r"\bbullish\b",
    r"\bbearish\b",
    r"\bnext stop\b",
    r"\bwill (?:reach|hit|hold|break|bounce|rally|continue)\b",
    r"\bexpect(?:ed|ing)? to\b",
    r"\bodds\b",
    r"\bsupport\b",
    r"\bresistance\b",
    r"\bmagnet(?:s)?\b",
    r"\bhighway(?:s)?\b",
]


def extract_numeric_tokens(text: str) -> Set[str]:
    """Extracts all YYYY-MM-DD dates, decimals, and integers (stripping commas)."""
    cleaned = text.replace(",", "")
    return set(re.findall(r"\d{4}-\d{2}-\d{2}|\d+(?:\.\d+)?", cleaned))


def build_allowed_number_whitelist(payload: Dict[str, Any]) -> Set[str]:
    """Builds the strict whitelist of numbers/dates present in the deterministic input JSON."""
    allowed = extract_numeric_tokens(json.dumps(payload))
    allowed.update({"30", "20", "100", "0", "1", "7", "14", "2018-02-01", "2024-02-15", "2027-12-13"})
    return allowed


def verify_llm_output(text_fields: List[str], payload: Dict[str, Any]) -> List[str]:
    """
    Gate 1: Every number/date emitted by Qwen must exist verbatim in `payload`.
    Gate 2: Zero predictive/support/resistance/magnet/highway terms allowed (with negation allowlist).
    """
    violations: List[str] = []
    combined = " ".join(text_fields)
    allowed_nums = build_allowed_number_whitelist(payload)

    emitted_nums = extract_numeric_tokens(combined)
    unverified = emitted_nums - allowed_nums
    if unverified:
        violations.append(f"UNVERIFIED_NUMBERS_EMITTED: {sorted(unverified)}")

    for pat in BANNED_PREDICTIVE_PATTERNS:
        m = re.search(pat, combined, flags=re.IGNORECASE)
        if m:
            violations.append(f"BANNED_LEXICAL_TOKEN: '{m.group(0)}'")

    return violations
```

Why the draft harness is unsuitable for runtime:

1. The extractor loses signs, units, and associations. A negative return can
   become positive, dollars can become percentages, and a valid number can
   be attached to the wrong instrument/date without detection. Digits inside
   keys, hashes, and unrelated payload text also enter the whitelist.
2. The fixed date/number additions authorize values absent from the input,
   contradicting Gate 1's docstring. FET or RENDER dates must come from the
   selected evidence, never from a global exception list.
3. Regex negation exceptions are narrow. They miss paraphrased predictions
   and reject honest limitations such as "no support". Lexical bans also
   conflict with terms in the proposed input classifiers and research titles.
4. Schema validation does not establish semantic truth, complete provenance,
   or faithful statistics. Enforce required facts, identity, signed units,
   scope, timestamps, and exact source IDs in trusted code.
5. Use constrained evidence-ID selection and deterministic templates for
   chart/triage/execution prose. Text classification is a separate bounded
   task; record its model/version, and treat spam/tone judgments as estimates.

Use a revised lexical scan only as a unit/CI check on the prepared sentence
catalog, with explicit allowances for required negated disclosures such as
"not validated support/resistance". Keep the number provenance and semantic
checks in the trusted renderer. This is a proposed follow-up test, not one
implemented or run by this documentation change.

Failure at any layer returns a labelled deterministic fallback or unavailable
state. Do not publish partially accepted model prose. Any future implementation
needs checks for sign/unit swaps, omitted limitations, spoofed IDs, malformed
JSON, stale cached evidence, adversarial source text, and unchanged-input calls.

## 2. Sentiment and context architecture

### 2.1 Active route and one-board contract

The mounted coin information popup is
`frontend/src/components/SentimentPopupAdvanced.jsx`; `CoinPositioning.jsx`
provides positioning content. Do not use the orphaned `SymbolPanel` as the
runtime entrypoint.

Current flow on the research branch:

```text
SentimentPopupAdvanced -> Flask GET /api/sentiment/latest?symbol=BTC
                      -> FastAPI /sentiment/latest (sentiment_api.py)
CoinPositioning       -> Flask GET /api/positioning/<symbol>
                      -> derivatives_positioning.py
```

`backend/sentiment_aggregator_enhanced.py` only re-exports
`get_sentiment_for_symbol` from `sentiment_aggregator.py`. Do not rebuild a
legacy enhanced aggregator or reintroduce its old fabricated fallbacks.
The symbol on the sentiment request is request context; market-wide mood
does not become coin-specific because a popup requested it.

[SENTIMENT_ONE_BOARD.md](SENTIMENT_ONE_BOARD.md) defines:

- `sentiment: object | null`;
- `sentiment_meta: {ok: bool, staleSeconds: number, lastOkTs: ISO | null,
  lastTryTs: ISO | null, error: string | null}`;
- `pipelineStatus: object | null` when surfaced by the normalizer.

Keep this documentation contract distinct from the current proxy envelope,
which exposes the service fields plus `scope`, `requested_symbol(s)`,
`proxy_meta`, and `sentiment_meta`. Inspect the route before adding another
wrapper or claiming `pipelineStatus` is always emitted.

Reject missing required keys, NaN, infinity, and out-of-range values. On
failure retain valid last-good values with explicit stale/offline status,
`ok=false`, actual attempt/success timestamps and an error. Never fabricate
successful metadata, neutral 50%, news, history, social counts, or a score
for an unknown coin. Missing source data stays null/empty.

### 2.2 Source roles, caching, and freshness

The salvage plan defines four roles; this inventory adds event and on-chain
roles without merging them into a generic sentiment score.

| Role | Sources / proposed adapters | Cache policy in draft | Role stale window / state |
| --- | --- | --- | --- |
| `market_mood` | Alternative.me Fear & Greed; CoinGecko global | 1h / 5m proposed; actual code 5m / 2m | 6h salvage window; disclose market-wide scope |
| `market_positioning` | Hyperliquid, OKX public v5; Coinalyze with key; Binance/Bybit health rows | Existing service caches; per-coin Hyperliquid context TTL 60s | 10m |
| `event_calendar` | Coinbase product/status diff watcher; DefiLlama hacks/protocols; GitHub releases; optional CoinMarketCal | Watcher every 5m; other adapters pending | Source-specific freshness policy still required |
| `news_context` | CoinDesk, Cointelegraph, Decrypt, The Block, Bitcoin Magazine RSS/Atom | Proposed capture every 5-15m | 24h display, 2h breaking context |
| `social_chatter` | Neynar/Farcaster; approved Reddit OAuth; optional Santiment | Reddit 10m proposed | 30-60m |
| `onchain_flow` | DEX Screener, GeckoTerminal, DefiLlama TVL, Dune SQL API v1 | Adapter-specific, not implemented as one policy | Not yet specified; expose observation age |

Do not silently change runtime TTLs to match this proposal. Stale thresholds,
provider update cadence, cache reuse, and request backoff are distinct controls.
See [salvage plan](SENTIMENT_SOURCE_SALVAGE_PLAN.md),
[source architecture](SENTIMENT_ARCHITECTURE.md), and
[dated endpoint verification](SENTIMENT_SOURCES_VERIFIED_2026-10-19.md).

### 2.3 Trust weights, divergence, and lexicon

Proposed trust defaults: `tier1=0.85` (official exchange/on-chain and
market-mood sources), `tier2=0.70` (curated news/professional context),
`tier3=0.50` (retail/social), `fringe=0.30`. Labels such as "institutional"
describe a proposed grouping; Fear & Greed is not measured institutional flow.

For comparable source scores `s_i` in [0,1], tier weight `w_i`, and declared
reliability `r_i`, the corrected formula is:

```text
overall_context_score = 100 * sum(s_i * w_i * r_i) / sum(w_i * r_i)
```

Missing sources are omitted rather than scored neutral. If the denominator
is zero, output null. Raw tone [-1,+1], 0-100 mood, funding rates, and open
interest are not interchangeable scores; a versioned normalization would be
needed before applying this formula. The score affects context priority only.

The salvage plan proposes normalized pairwise gaps >=0.25 warning and >=0.40
critical. The checked-in `sentiment_aggregator.py` helper and
`backend/sentiment_config.yaml` instead use `divergence_threshold=0.12`:
only tier1 versus tier3 is compared, medium severity at >=0.12 and high at
>=0.24 by default. Configuration can change that threshold. Neither rule is
validated against outcomes, and inspecting this helper does not establish
that it is the mounted FastAPI proxy's divergence path. Preserve the code/
plan distinction; no runtime threshold change is made here.

Explain disagreement and source coverage only. Older documents mention
"accumulation" or "local-top" readings; treat those as unvalidated hypotheses,
not approved predictive copy.

Archived text lexicon (not a price model): positive terms `breakout`,
`rally`, `accumulate`, `golden cross`, `adoption`; negative terms `rug pull`,
`hack`, `liquidation`, `death cross`, `bankruptcy`; noise terms `dyor`,
`nfa`, `gm`, `wen`. Do not surface these as chart color, labels, or explanatory
claims. The classifier is not approved or supplied with captured inputs.

### 2.4 Source inventory and verification limits

The table combines the draft inventory with **2026-10-19 checks reported by
Claude**, not new endpoint probes. Quotas, subscriptions, and policies below
are explicitly unverified unless a primary-source link is supplied.

| Source | Access / dated observation | Intended use and limitation |
| --- | --- | --- |
| Alternative.me | Already used | BTC-driven market mood; not coin-specific social sentiment |
| CoinGecko `/global` | HTTP 200; already used | Global market context; community data requires its own provenance |
| CoinPaprika `/v1/global` | 200; coin intel already uses provider | Additional market/coin context |
| Hyperliquid `/info` | `metaAndAssetCtxs`, `fundingHistory` 200 | Perps, funding/OI, mid/impact prices; funding is hourly, x8 only for labelled 8h equivalence |
| OKX public v5 | Funding, OI, recent funding history 200 | BTC/ETH service plus per-coin capability; do not assume every settlement interval is 8h |
| Binance live `api` / `fapi` | 451 from reviewed US machine | Record blocked; no workaround; public Vision archives are a separate source |
| Bybit public v5 | 403 / regional block | Record blocked; no workaround |
| Coinalyze | 401 without `COINALYZE_API_KEY` | Code slot exists; aggregated OI/funding/liquidations/L-S proposed. Draft 40 RPM/free-key/history claims need verification |
| Deribit | BTC options summary 200 | Majors only; distinct from broad altcoin perp coverage |
| Coinbase `/products` | 842 observed registry products | Forward listing/status/removal diffs; first pass is baseline |
| Coinbase status incidents | 200, last 50 incidents | Forward incident capture; not a full historical incident archive |
| DefiLlama `/protocols`, `/hacks` | 200 keyless; `/emissions` 402 | Protocol/TVL/security-event context; paid unlock data excluded |
| GitHub releases | Fetch.ai releases endpoint 200 | Official development/release context, not retail mood; draft 60 unauthenticated / 5,000 authenticated hourly limits need current verification |
| CoinDesk RSS | 308 then 200 | Follow the actual redirect; GUID/URL dedupe and real User-Agent |
| Cointelegraph, Decrypt, The Block RSS | 200 | Forward news capture; existing RSS path is older, in-memory plumbing |
| Bitcoin Magazine RSS | Draft inventory only | Endpoint/capture adapter not verified here |
| CoinMarketCal | No response in prior check; key needed | Unverified optional event source, not live coverage |
| Neynar / Farcaster | Draft inventory only | Check current credits, terms, identity mapping before adapter work |
| Reddit OAuth / PRAW | Older handler has placeholder configuration | Requires approved app/access. Draft 100 req/min, noncommercial status, and Nov 2025 Responsible Builder pre-approval claims need primary verification |
| Santiment GraphQL | Anonymous endpoint 200 | Reachability does not establish free data scope or history access |
| DEX Screener | 200 for RENDER Solana address | Contract-resolved pool/liquidity context; draft 300 req/min not verified |
| GeckoTerminal | 403 HTML challenge from reviewed machine | Keyless eligibility does not establish local availability; draft ~30 req/min not verified |
| Dune SQL API v1 | Draft inventory only | Proposed SQL-result source; draft 2,500 free monthly credits not verified |
| Polymarket Gamma | Events endpoint 200 | Optional context, not a validated signal; rate/plan limits unverified |

**Retire / do not build on without fresh verification:**

- CryptoPanic: prior free endpoint returned 403 and older RSS plumbing still
  references it. Remove that dependency in its own implementation slice.
  Draft claims April 1, 2026 free shutdown and $9/month PRO are unverified
  commercial details; 403 alone does not prove their cause.
- CCData/CryptoCompare: draft claims the 250k lifetime free tier ended
  May 21, 2026; Glassnode: draft claims free tier ended May 2026; Dune SIM:
  draft claims retirement August 1, 2026. The canonical source audit explicitly
  did **not** verify those dates. Keep SQL v1 as the candidate Dune path and
  recheck provider terms before building.
- SentiCrypt, CoinyBubble, and CryptoMeter Trend Indicator: legacy sources
  retired unless endpoint, provenance, and quality are revalidated.
- X/Twitter free-tier assumptions: obsolete as a design dependency. The
  draft's $0.005/read and $42k/month Enterprise figures are unverified;
  do not use them for a budget or integration decision.

### 2.5 PIT capture and source build order

Persist raw payload/hash, canonical identity, source publication time,
`first_seen_utc`, source URL, and revision lineage. Deduplicate RSS by GUID/URL
and payload revision, not by a model's interpretation. Resolve projects by
contract, verified project name/cashtag, or registry mapping; ticker alone is
insufficient for UP/TRUST/EDGE/RED/COMP/BIO/AI and other collisions.

For point-in-time research, filter by **first seen**, not article date.
Do not backfill a headline into a past event as though it was captured then.
Later edits or classifications cannot silently replace the original record.

Build order from the source audit: PIT log; Coinbase watcher; persistence of
existing positioning; configure Coinalyze if appropriate; RSS forward logger
with retired CryptoPanic dependency removed; DefiLlama/DEX Screener; GitHub;
then Neynar/Reddit if access and terms fit. Steps 1-3 exist in the research
branch; deployment coverage differs by collector versus watcher runtime.

The prior audit's power calculation corrects the draft research expectations:
for a five-percentage-point group difference, 80% power, and observed shock
standard deviation 18.5%, approximately 641 events total at alpha .01 or 848
at alpha .002 are needed under equal groups. At about 32/month overall or
37/month recently, forward collection is about 17-26 months, potentially
longer for unequal groups. These are design calculations, not outcome odds.

## 3. Empirical research record

### 3.0 Shared interpretation and artifact map

Daily universe: 492 Coinbase USD products including 89 delisted, extended
event range 2022-01-03 through 2026-10-17. Daily discovery is 2022-2024,
test begins 2025-01-01; hourly studies use their separately stated one-year
archive and split. Outcomes are generally forward returns minus same-day
volatility-matched peers. Level studies use a signed **reaction** convention:
positive means turning away from the approached line. Read each study's
precise construction before comparing numbers.

Study 1's matched control and stricter test family were added after its
first results. Studies 2/2b/2c/2d were committed before their corresponding
outcome computations; post-hoc path analyses and reused data remain post hoc
even inside a preregistered study. Bonferroni discovery gates and same-sign
test confirmation must not be replaced with selective favorable cells.

| Study | Design/result record | Executable code | Committed result |
| --- | --- | --- | --- |
| 1 | [MOVE_STUDY.md](MOVE_STUDY.md) | `scripts/move_study/continuation_vs_reversal.py`, `robustness.py` | `data/move-study/continuation_vs_reversal_daily_2022.json`, `robustness.json` |
| 2 | [LEVEL_STUDY.md](LEVEL_STUDY.md) | `scripts/move_study/level_study.py` | `data/move-study/level_study.json` |
| 2b | [VOLUME_PROFILE_STUDY.md](VOLUME_PROFILE_STUDY.md) | `scripts/move_study/volume_profile_study.py` | `data/move-study/volume_profile_study.json` |
| 2c | [ABSORPTION_STUDY.md](ABSORPTION_STUDY.md) | `scripts/move_study/absorption_study.py` | `data/move-study/absorption_study.json` |
| 2d | [PROFILE_SHAPE_STUDY.md](PROFILE_SHAPE_STUDY.md) | `scripts/move_study/profile_shape_study.py` | `data/move-study/profile_shape_study.json` |
| 3a | [FUNDING_STUDY.md](FUNDING_STUDY.md) | `scripts/move_study/fetch_funding.py`, `funding_study.py` | No results in the pinned record |
| 3b | Proposal in this handoff and Claude handoff | No committed study at the pinned revision | None |

### 3.1 Study 1: large daily moves and 80-event cause review

Checkpoints in the supplied draft: `dd6666c`, robustness `c1f5a3a`.
There are 9,034 +10% up-events before horizon-specific exclusions, with a
seven-day per-coin cooldown and calendar-day resampling.

Seven-day relative means after +10% days: -1.90% discovery and -2.20% test.
The extended run's first-day **peer-relative** means are -1.39% (4,847
events) and -1.34% (4,155 events): 9,002 observations at that horizon, not
the full 9,034-event robustness population. Counts vary by available horizon.
The draft's approximate "-1.6% next day" is a different measure: **plain
return from buying at the close**, -1.45% discovery / -1.66% test before
costs. Keep plain returns separate from peer-relative returns in every lookup.
No replicated dip-buying finding follows -10% days.

The 80-event review contains 40 largest and 40 random rises from the
October 2025-October 2026 period. In the largest-event subset, protocol/news
events (n=8) have +5.6% seven-day mean and +6.6% median versus -20.9% mean
for no-known-cause (n=21). The p=.13 comparison in the canonical write-up
is the broader **known-cause versus unknown-cause mean gap**, not a
demonstrated protocol-news edge. Restricting evidence to sources dated on
or before the move removes the apparent known/unknown effect: mean gap
+1.6 points, p=.86; median gap **-3.1** points, p=.53. The draft's removed
rows are ALCX, TNSR, ZKP, APE, ALLO, BIRB, AERGO, ESP, DEEP. This remains
a publication-time restriction, not proof the source was captured before
the move. Store first-seen times going forward.

Eight post-hoc robustness checks are recorded:

1. Cause hindsight: the news gap vanishes under the timing restriction.
2. Outliers: seven-day medians -3.9%/-3.7% and 10% trimmed means
   -3.4%/-3.5% are more negative than arithmetic means.
3. Calendar-day equal weighting: first-day means -2.4%/-2.8%, seven-day
   -3.7%/-4.8%, stronger than event weighting.
4. Midnight print: only 23% of next-day relative loss occurs in the first
   UTC hour in the hourly check (2,088 events).
5. Liquidity: prior 20-day median USD volume <$1M yields -1.9%/-1.9%
   next day and -2.4%/-2.7% seven days. $1M-$10M yields -0.8%/-1.0%
   seven days; >=$10M -1.5%/-1.0%, with test intervals touching zero.
6. Shocks versus market beta: >=5x prior 20-day median volume and
   `ret1 - btc_ret >= 0.15` yields -3.8%/-4.4% next day,
   -5.7%/-7.3% seven days **across all liquidity tiers**. Low-volume beta-like events: roughly
   -0.3% next day, -0.3%/-0.4% seven days, intervals including zero.
7. Survivorship/new listings: delisted products already included and fade
   more (-3.5%/-6.1% seven days in this robustness comparison); products
   under 90 days old and established products look similar.
8. Own drift: subtracting per-coin unconditional mean leaves the result
   similar (-1.8%/-2.2% seven days).

Scope the warning to high-volume, coin-specific spikes and measured liquidity.
Thin coins have higher execution costs; these means do not establish a
profitable short, a suitable exit price, or a conditional probability.

### 3.2 Study 2: confirmed highs/lows and Fibonacci ratios

Monday 00:00 UTC weekly bars; a pivot becomes available at the close of the
second following week. Respect `confirmed_at` during replay. The study has
16,672 confirmed weekly pivots, 76,783 real/placebo levels, 276,209 liquid
arrivals, and 27,313 first touches. **0 of 24 primary tests pass discovery.**

Seven-day first-touch reaction summaries (the real/placebo means below are
discovery figures; differences separately identify discovery and test):

| Reference / approach | Real | Placebo | Difference discovery | Difference test |
| --- | --- | --- | --- | --- |
| Confirmed pivot from below | +2.31% | +2.19% | +0.11 points | +0.02 points |
| Confirmed pivot from above | -0.35% | -0.23% | -0.12 | -0.26 |
| Fib .5/.618/.786 from below | +3.73% | +3.28% | +0.45 | -0.07 |
| Macro high r=1 from below | +2.05% | +2.19% | -0.14 | -0.98 |
| Macro low r=0 from above | -0.44% | -0.23% | -0.21 | -0.30 |

Non-Fib ratio controls: .37, .44, .56, .67, .73, .83. Same-day breaks
are about 40% at real pivots versus 39-42% at placebos.

Post-hoc path effect: shock arrivals from below have +6.0% seven-day
reaction (median +9.9%, n=1,366), versus +0.3% (median +2.6%, n=2,727)
for grinding arrivals. Thin liquidity: +3.3% reaction versus -0.3% for
>=$1M/day. This describes the approach, including reaction at arbitrary
lines, and does not validate a predictive level.

### 3.3 Study 2b: fixed-range volume profile versus placebo

Preregistration `704937b0`, results `bc8a8873`. Course claims were tested,
not adopted. There are 14,352 causal legs, 104,516 first touches, 100 bins,
volume outside the leg dropped, and HVN/LVN searches in interior bins 5-94.
**0 of 22 primary tests pass discovery.**

Seven-day real-minus-placebo reactions in discovery/test: POC from below
+0.49/+0.09 points; POC from above -0.14/+0.03; VAH from below
-0.25/+0.11; VAL from above -0.55/-0.34. Test intervals all cross zero.
Thus the draft's "all differences <0.5%" is not exact for discovery VAL.

From below, discovery arrival-day break rates are **LVN 39.3%, HVN 38.7%**;
from above, 42.6%/40.2%. No replicated continuation-speed difference at
one or three days. "Magnet" and "highway" claims lack evidence here.

Hourly profiles rebuilt for 3,534 legs give the same overall null result.
POC-from-below differences are -0.18 hourly versus -0.35 daily; from above
+0.65 versus +0.65. VAH -0.02/+0.14; VAL +0.02/+0.10. These are comparison
cells, not one universal +0.65 result.

Descriptive reaction/acceptance split: a close beyond VAH has +2.5%
give-back versus +1.2% for a close inside; placebo lines show +2.6% versus
+1.35%. Shock-day POC arrival: +7.8% seven-day reaction (median +10.6%,
n=1,060), grinding +0.6%; thin coins +2.8%, liquid +0.5%. The approach,
not the line, carries the observed information. Profiles use candle volume,
not executed trade-side order flow.

### 3.4 Study 2c: two-step hourly absorption and low breakdowns

Preregistration `3949e53b`, results `fb845d7a`. Hourly scope is
2025-10-02 through 2026-10-10, split at 2026-04-01. There are 19,342
liquid triggers (8,532 bullish, 10,810 bearish).

- Bullish absorption: no edge at one, three, or seven days in either half.
- Bearish exhaustion: one-day discovery +0.33 points survives its gate,
  but test +0.11 points, p=.06, fails replication. Other horizons did not
  pass discovery. Small magnitudes do not establish an after-cost edge.
- Location/confluence: all 12 discovery tests fail, including profile,
  pivot, and .705-.886 discount-zone comparisons with placebo/open air.
- Shock timing: 97/463 shock days have a bearish trigger within 48 hours;
  test improvement +0.4 to +0.6 points has intervals across zero.

Daily macro-low/VAL breakdown consistency check (14-day relative return):

| Period | Real | Placebo | Difference | p |
| --- | --- | --- | --- | --- |
| 2022-2024 | -0.27% | +0.56% | -0.83 points | .037 |
| 2025-2026 | -0.27% | +0.79% | -1.06 points | .012 |

Macro-low mean is -0.79% (median -1.92%, n=892), VAL -0.06% (n=2,330).
The hypothesis was noticed using both historical periods in Studies 2/2b;
this is **not independent out-of-sample replication**, even though the
specific test was committed before this run. The next independent sample
begins 2026-10-18, with complete outcome horizons required.

### 3.5 Study 2d: profile shapes, balances, and volume ledges

Preregistration `90815a9d`, results `b3410c4f`, count correction `91d6035a`.
Offline hourly/daily archives, not tick data. **0 of 22 primary tests pass
discovery.**

- S1: P-shape rallies do not outperform bottom-heavy rallies; discovery
  three-day difference -0.67 points. b-shape drops fail discovery.
- S2: three-day merged hourly-value-area and daily-range balance breakouts
  fail versus same-size moves using 2% move bins.
- S3: steepest three-bin-smoothed HVN-to-LVN edges behave like placebo
  lines: 17,660 ledge first touches, 50,018 placebo touches.

Hourly S1/S2h uses 2025-10-02 through 2026-10-10 and the April split;
daily S2d/S3 uses the extended daily split. No book, taker delta, or
trade-side data was present. The findings limit the tested candle-based
claims; they do not test every market or every possible pivot rule.

### 3.6 Study 3a: settled perp funding (pending)

Preregistration `42073481`, initial fetch/analysis code `a4d8b112`. There are
6,256 planned Binance Vision **monthly** funding archives, not monthly/daily
funding files. The draft reports 11,087 planned requests including Hyperliquid,
throttled to one per 1.1 seconds. The checked review reports a dropped connection
at file 3,897, followed by retry/backoff and checks-only support in upstream
`d9873046`. That code change is not part of this documentation-only branch.
The user's later estimate of about two hours remaining is an estimate, not
completion evidence. No results are present in the reviewed record; no watcher,
rerun, model job, or outcome computation is started here.

The committed design is the authority:

- Population A: Study 1 +10% days; B: shock subgroup (>=5x volume and
  >=15 points above BTC). Seven-day cooldown; daily discovery/test split.
- For day t, use prints settled in `(t 00:00 UTC, t+1 00:00 UTC]` only.
  Convert each to `rate * 8 / interval_hours`, then average. Hyperliquid
  interval is one hour. Prefer Binance where prints exist, otherwise
  Hyperliquid; retain the actual venue and coverage.
- Regimes in 8h-equivalent units: negative <0; neutral 0 through +0.02%;
  crowded long >+0.02%. These are test labels, not established causal states.
- Ten primary tests: F1 negative minus crowded-long for A/B at 1/3/7 days
  (six); F2 perp-listed minus spot-only at seven days in two liquidity
  tiers for A/B (four). Bonferroni discovery, same-sign confirmation,
  seven-day calendar-block bootstrap.
- Symbol mapping must handle `B`, `1000B`, `1000000B`, and Hyperliquid
  `kB`, and keep RNDR/RENDER separate. The design verifies one overlapping
  month of daily closes within 5% median ratio error after scaling.
  Review whether verification uses future identity information before
  accepting a point-in-time claim.
- "Spot-only" means no verified print in these two sources, not proof of
  no perp anywhere. Missing coverage or identity failure is not evidence
  that an instrument never had a perp.
- Secondary checks: funding/outcome rank correlation, +/-0.05% tails,
  down-days, cross-venue agreement, and coverage by year. Report all results.

Before results are joined, independently review the script against its
preregistration for cutoff inclusivity, normalization, scaled-contract
identity, missing-versus-unlisted classification, and the ten-test family.
Write findings separately; do not silently alter the preregistration.

### 3.7 Candidate Study 3b: signed taker delta (not started)

Study 3b still needs the user's explicit go-ahead, an identity map, and a
committed design; do not start it on the strength of this handoff. Create a
preregistration only after that approval and the Study 3a dependency/scope are
resolved. The candidate uses Binance **spot or USD-M** kline
archives: one-based column 10 (zero-based index 9) is taker-buy base volume;
column 6 (index 5) is total base volume. COIN-M columns have different
units/layout and cannot reuse that parser blindly. The
[Binance public-data specification](https://github.com/binance/binance-public-data/blob/master/README.md)
also records that spot timestamps from 2025 onward use microseconds and
archives may later be revised; preserve raw hashes and timestamp units.

```text
signed_taker_delta = 2 * taker_buy_base_volume - total_base_volume
delta_ratio = signed_taker_delta / total_base_volume
```

For positive total volume and valid component bounds, ratio is in [-1,+1].
Zero/missing volume yields unavailable, not zero. The hypothesis asks whether
delta and positive delta with a stalled close (candidate absorption) separate
holding spikes from fading ones. Thresholds, close-stall definition, costs,
horizons, controls, missingness, and multiplicity are not yet preregistered.

Coinbase event prices and Binance aggression are cross-venue series. Keep
them separate and verify the spot/perp identity map; coins without Binance
coverage drop out, likely excluding some thin instruments. Signed taker
volume is observed aggression, not proof of participant intent, hidden
liquidity, or a future reaction.

## 4. PIT watcher, database schema, and microstructure

### 4.1 Installed watcher: dated observations

Implementation: `backend/pit_watch.py`, `backend/pit_log.py`,
`scripts/windows/install_pit_watch_task.ps1`, `run_pit_watch.ps1`.
See [PIT_LOG.md](PIT_LOG.md) for the operational record.

The prior handoff reports the task **Moonwalking PIT Watch** installed from
`b379d66` under `%USERPROFILE%\.moonwalking\pit`, with the source revision
in `INSTALLED.txt`. Database: `%USERPROFILE%\.moonwalking\data\pit_context.sqlite`.
Logs under `%USERPROFILE%\.moonwalking\logs\pit-watch-*.log`, including
`pit-watch-events.log`. It runs at logon with a five-minute backstop and a
self-restarting launcher. No task installation or restart was performed here.

Current watcher code makes **three** public requests per pass, 1.1 seconds
apart: Coinbase products, status incidents, Hyperliquid asset contexts.
The older two-request sentence in `PIT_LOG.md` predates Hyperliquid capture.
The last pinned operational snapshot (2026-10-19 16:15 UTC) reports:

- 842 registered products, initially logged as `BASELINE`;
- 50 Coinbase incidents;
- 178 Hyperliquid assets per pass, 13 passes / 2,314 snapshots;
- 120 ticker matches to Coinbase, explicitly not verified identities;
- one recovered restart at 15:25 UTC; collector health 200 when checked.

Positioning hooks in `sentiment_api.py` and `derivatives_positioning.py` append
when those services run the research code. The separate installed collector
runtime does not automatically acquire branch-only hooks. The watcher itself
already captures all Hyperliquid asset contexts.

### 4.2 Canonical SQLite schema at the pinned research revision

The following is the `SCHEMA` literal from `backend/pit_log.py` at `1f198332`.
`SCHEMA_VERSION=1`; `_migrate()` additively adds the three impact/mid columns
for older stores. The append-only rule applies to the history/event tables;
registry, health, watch state, and metadata are mutable operational tables.
Append-only history is an application convention, not enforced by SQL triggers.

```sql
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Coinbase products as observed. Mappings to other venues stay NULL until
-- verified; nothing is auto-mapped by ticker here.
CREATE TABLE IF NOT EXISTS symbol_registry (
    product_id TEXT PRIMARY KEY,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    coinbase_status TEXT,
    first_seen_utc TEXT NOT NULL,
    last_seen_utc TEXT NOT NULL,
    removed_seen_utc TEXT,
    hyperliquid_coin TEXT,
    okx_inst_id TEXT,
    chain TEXT,
    contract_address TEXT,
    mapping_note TEXT
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    data_status TEXT NOT NULL,       -- live | stale | offline | blocked | unconfigured
    last_ok_utc TEXT,
    last_try_utc TEXT NOT NULL,
    http_status INTEGER,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS pit_context_log (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,                 -- Coinbase product id when it exists, else NULL
    venue_symbol TEXT,               -- the source's own symbol (e.g. RENDER, RENDER-USDT-SWAP)
    source_id TEXT NOT NULL,
    role TEXT NOT NULL,              -- event_calendar | market_positioning | ...
    event_type TEXT NOT NULL,
    source_published_utc TEXT,
    first_seen_utc TEXT NOT NULL,
    metric_primary REAL,
    metric_secondary REAL,
    label TEXT,
    source_url TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    revision_of INTEGER REFERENCES pit_context_log(record_id)
);
CREATE INDEX IF NOT EXISTS idx_pit_product_seen ON pit_context_log(product_id, first_seen_utc);
CREATE INDEX IF NOT EXISTS idx_pit_source_seen ON pit_context_log(source_id, first_seen_utc);

-- Compact per-asset derivatives snapshots from the watcher (one row per asset per pass).
-- Provenance for each pass (response hash, count) is a row in pit_context_log.
CREATE TABLE IF NOT EXISTS positioning_snapshot (
    first_seen_utc TEXT NOT NULL,
    venue TEXT NOT NULL,
    venue_symbol TEXT NOT NULL,
    product_id TEXT,                 -- Coinbase product when '<symbol>-USD' exists (ticker match, see docs)
    funding_rate REAL,               -- per the venue's own interval (Hyperliquid: 1h)
    funding_interval_hours REAL,
    open_interest REAL,              -- base units
    mark_price REAL,
    oracle_price REAL,
    premium REAL,
    day_notional_volume REAL,
    pass_record_id INTEGER REFERENCES pit_context_log(record_id),
    mid_price REAL,
    impact_bid_price REAL,           -- price a standard-size market sell would fill at (Hyperliquid impactPxs[0])
    impact_ask_price REAL            -- price a standard-size market buy would fill at (impactPxs[1])
);
CREATE INDEX IF NOT EXISTS idx_pos_symbol_seen ON positioning_snapshot(venue_symbol, first_seen_utc);

-- Last observed state per watched item, for diffing (not history).
CREATE TABLE IF NOT EXISTS watch_state (
    source_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    state_sha256 TEXT NOT NULL,
    state_json TEXT NOT NULL,
    last_record_id INTEGER,
    updated_utc TEXT NOT NULL,
    PRIMARY KEY (source_id, item_id)
);
```

Preserve missing numbers as NULL. `open_interest` in compact snapshots is
base units; do not label it USD unless the conversion and timestamp are
explicit. Event-hook `metric_secondary` is USD where known, otherwise
venue-native OI; inspect the payload rather than assuming shared units.

`POSITIONING_PASS` is the raw-response hash/count provenance event;
`positioning_snapshot.pass_record_id` links each asset row to it. Other
events include `BASELINE`, `PRODUCT_LISTED`, `PRODUCT_STATUS_CHANGE`,
`PRODUCT_REMOVED`, `STATUS_INCIDENT`, `STATUS_INCIDENT_UPDATE`, and
`POSITIONING_SNAPSHOT`. Changed payloads append with `revision_of`; they
do not rewrite historical captures.

The logger's generic `connect()` executes schema/migration/metadata writes.
Read-only consumers must instead use a URI such as
`sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)` and avoid write helpers.
Filter availability on `first_seen_utc`, validate UTC timestamps, and retain
source publication time separately. A historical source date alone is not
proof the information was available to this system then.

### 4.3 Hyperliquid impact-price asymmetry

Stored fields: funding/rate interval, base OI, mark, oracle, premium, day
notional volume, `mid_price`, `impact_bid_price`, `impact_ask_price`.
The latter two come from `impactPxs[0]` and `[1]`.

```text
bid_impact_bps = (mid - impact_bid) / mid * 10_000
ask_impact_bps = (impact_ask - mid) / mid * 10_000
```

With valid positive mid and correctly ordered quotes, larger ask cost means
more buy-side impact for the venue's impact amount; larger bid cost means
more sell-side impact. This is a venue snapshot, not a predicted price path
or a universal "path of least resistance". Retain venue/size semantics,
observation time, and missing/invalid states. Do not equate this impact
amount with the proposed $10k Coinbase simulation.

Prior RENDER observation: mid 1.8195, impact bid 1.8183, impact ask 1.8211.
The values illustrate stored fields, not current quotes. No predictive
validation of asymmetry has been committed in these studies.

### 4.4 Proposed on-demand Coinbase spot microstructure

For an opened coin popup or a bounded top 5-10 shock-mover set, propose
cached, deduplicated requests under a shared request budget. Polling books
and trades for 400 coins does not fit the research workflow's one-request-
per-second budget; that is a local budget, not a verified exchange-wide cap.

1. `GET /products/{product_id}/book?level=2`: compute bid and ask resting
   USD notional within +/-2% of a timestamped mid. A ratio with an empty
   denominator is unavailable or explicitly one-sided. Simulate a $10k
   market buy/sell by walking displayed depth; report VWAP-based slippage
   in basis points. If depth cannot fill the amount, report insufficient
   displayed depth rather than an invented completed fill. Aggregated L2
   sizes already include all orders at the price; do not multiply by the
   order count. See [Coinbase book documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book).
2. `GET /products/{product_id}/trades?limit=1000`: compute delta over the
   returned, deduplicated trade IDs and disclose its actual time span. The
   `side` identifies the **maker**: `sell` means buyer aggression, `buy`
   means seller aggression. Use consistent base or USD units. Pages are
   trade-count samples, not fixed-duration flow. See
   [Coinbase trade documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades).
3. Proposed large-print filters: >=$5k thin coins, >=$25k majors. The
   major/thin universe, thresholds, absorption window, and stalled-price
   definition still need specifications. A large trade does not identify
   a whale, and a thin snapshot alone does not prove why price moved.

Positive aggression with flat/red price or negative aggression with
flat/green price is a candidate absorption description only. Do not claim
predictive edge until a preregistered study survives its controls and costs.

## 5. Video, RENDER identity, FET arithmetic, and chart wording

### 5.1 Video audit and source separation

The committed [RENDER history record](RENDER_HISTORY.md), section 5b, supersedes
its earlier indirect video review. It contains 61 directly transcribed bars in
`data/render-history/video_reference_bars.json`. This handoff reads that
record; it does not claim a new ffmpeg/frame inspection of the original video.

- Chart display is logarithmic; linear-price Fibonacci arithmetic stays linear.
- Recording is approximately 2026-10-13 21:00-22:00 UTC, active week
  2026-10-12. The review mixed hovered 2026-10-05 OHLC with live-week SMAs.
- Live-week video SMA50/100/200: about 1.6997 / 3.1332 / 3.7009; the draft's
  1.6998 is an approximate review transcription. Completed Oct 5 video
  values: 1.7049 / 3.1838 / 3.6930; Coinbase RENDER SMA50/100:
  1.7048 / 3.1839. Do not use different weeks or sources as exact fixtures.
- October 2025 index wick is **0.5454**, Coinbase validated daily low
  **0.651 on 2025-10-10**. The earlier 0.80-0.90 review estimate is wrong.
- The TradingView aggregated `RENDERUSD` index includes RNDR-era prices.
  Its SMA200 is not a valid Coinbase RENDER-only indicator.

RENDER-USD: 977 daily records from 2024-02-15 through the captured
2026-10-18 open day; 976 complete daily records and 138 complete weekly
bars at that snapshot. No missing observed daily interval. RNDR-USD,
RNDR-USDT, RNDR-EUR are distinct delisted series, not a splice source.
RENDER SMA200 is unavailable until the **week of 2027-12-13**, conditional
on sufficient subsequent complete weeks. No Coinbase all-time high/low
claim is established; `is_all_time_low` stays false.

Acceptance inputs: `identity.json`, `coverage.json`, `validation.json`,
`reference_parity.json` and its 100-week `indicator_fixture`, raw manifests,
and separate `series/` / `weekly/` files under `data/render-history/`.
Use [market-history.schema.json](market-history.schema.json) for field,
unit, completeness, and provenance requirements. Identical-input parity,
not approximate video prices, is the test boundary.

### 5.2 Frozen FET example through 2026-07-23

These chart-branch figures are a frozen historical calculation, not an
independent Coinbase pull performed for this handoff. Claude's checked review
explicitly did **not** verify these macro inputs. Their provenance is the pinned
[macro-range record](https://github.com/tgpetrie/moonwalking/blob/fb59304a/docs/research/MACRO_RANGE_REVIEW_2026-10-18.md)
and [frozen-close explanation record](https://github.com/tgpetrie/moonwalking/blob/fb59304a/docs/research/CHART_LEVEL_EXPLANATIONS_2026-10-18.md).
The arithmetic below was recomputed; source-candle identity and an independent
engine-fixture rerun remain unverified by this documentation change:

| Quantity | Value / provenance |
| --- | --- |
| Macro high H | $3.485, weekly period 2024-03-25 |
| Macro low L | $0.1338, weekly period 2026-02-02 |
| Completed weekly analysis close C | $0.1567, weekly period 2026-07-13 (through July 19) |
| Prior broken pivot low | $0.1843, actual daily extreme 2026-05-17; +17.61% above C |
| Ratio r=.786 | `L + .786*(H-L) = 2.7678432`, displayed $2.7678 |
| Signed distance from C | `(2.7678432/.1567 - 1)*100 = +1,666.33%` using unrounded arithmetic |

The pasted +1,666.31% uses the **rounded displayed price 2.7678**; it is
approximately +1,666.31%. Specify whether a UI formats an unrounded engine
value or recomputes from display precision; do not turn this rounding
difference into a conflicting fixture. Describe $0.1338 as **the macro low
the calculation is anchored to**. Avoid presenting it as an "invalidation
threshold" or a trade-plan instruction, guaranteed floor, or threshold for
other coins.

### 5.3 Synthesized wording checklist (not an existing eight-rule contract)

This eight-item checklist was assembled for this master document from the
supplied draft and chart/research disclosures. It is not a pre-existing
canonical list found on Claude's branch, nor evidence that all items have
been implemented. Use the cited chart records and checked review as sources.

1. A prior low above the dated analysis close is labelled **Prior Broken
   Pivot Low (Overhead Reference)**. A historical low is not automatically
   below current price. Never imply a protective floor from its label.
2. Show the **Weekly Candle Period** (or explicitly daily analysis period)
   separately from the actual extreme date.
3. Show the **True Daily Extreme Date** from source candles; do not infer it
   from a Monday weekly timestamp.
4. Show the **Confirmation Close Date**, with UTC availability; replay must
   not expose an unconfirmed extreme.
5. Every distance names the dated analysis close and uses signed
   `(reference / close - 1)*100`; distinguish above/below from recovery ratio.
6. Calculated macro explanations disclose `P=L+r(H-L)`, substituted anchors,
   and linear arithmetic even on a logarithmic display.
7. Explain the macro low the calculation is anchored to (FET example $0.1338) and
   limitations. Missing anchors/history/indicators remain unavailable.
8. Remove affirmative support/resistance/magnet/highway/target claims from
   chart popovers and narration. Preserve honest limitation statements and
   historical study titles; a crude global word deletion is not sufficient.

### 5.4 Latest chart-branch changes and next corrections

The next-run map at `fb59304a` prioritizes confirmed daily turns in a
365-day scope, ranked by distance from the latest completed daily close.
Macro arithmetic is collapsed and its overlays default off. This supersedes
older handoff paragraphs that promoted an always-visible future overlay.

Claude's latest review requests replacing R1-R3/S1-S3 with **Prior high
1-3 / Prior low 1-3** (or H1/L1), because R/S implies unvalidated behavior.
Mandatory disclosure: daily two-bars-each-side pivots were not directly
tested; weekly-scale equivalents behaved like arbitrary lines at a similar
distance in Coinbase USD 2022-2026. Make this a required narrator fact,
not optional prose. These are requested changes, not changes made here.

If approach context is added, use the exact completed-day Study 1 conditions
and dated study scope. Do not infer that a line itself caused the reaction.
For low-volume market-following rises, the observed tendency was weak.

## 6. Implementation sequence and completion evidence

1. On the chart branch, change R/S labels and require the study limitation;
   preserve evidence-ID rendering, daily-map priority, and replay cutoffs.
2. Use validated RENDER fixtures for indicator/history acceptance. Preserve
   the unavailable SMA200 and no-splice/no-all-time rules.
3. Review Study 3a against its frozen design before outcomes are interpreted;
   keep results and review findings in their own documented commits.
4. Add optional read-only PIT visibility with raw values, venue, identity
   confidence, timestamps, and health. No funding directional claims yet.
5. Add a negation-aware catalog wording check in a separately scoped chart
   change. Keep hygiene explanations deterministic. Do not start the six-agent
   suite, social classifier, divergence narrator, or execution badges. Source
   capture and empirical scoring need their own authorized, validated scope.
6. Study 3b remains proposed and requires explicit user approval plus a committed
   design; do not claim it has started or create live research jobs here.

For code changes, run the relevant backend/frontend checks, guardrails,
prefix/replay and failure-path tests, and a browser pass when behavior changes.
Commit coherent changes, push the named branch, and report checks and remaining
modified/untracked files under the user's supplied agent workflow. A branch
push is not a main merge or deployment.

### Checks performed for this documentation handoff

- Confirmed authoritative remote, fetched all refs, inspected recent history,
  diffs, worktrees, and overlapping work before writing. Existing local-AI and
  portfolio worktrees had unrelated uncommitted work and were left untouched.
- Reconciled the pasted draft against the pinned research/chart records and
  checked Ollama structured-output issue scope plus Coinbase/Binance field
  semantics against the primary sources linked above.
- Ran offline research/history/PIT checks using the installed research venv:

  ```powershell
  & "$env:USERPROFILE\.moonwalking\venv\Scripts\python.exe" -I -m pytest -o addopts='' scripts/render_history scripts/move_study backend/tests/test_pit_log.py -q
  ```

  Result: **59 passed**. No data download, live-store writes, model call,
  task restart, or outcome-study run was needed.

- Documentation checks passed: relative links, pinned chart-file paths,
  balanced code fences, exact embedded draft/schema matches, Python syntax,
  the six-table schema executed in memory, FET arithmetic, and staged
  `git diff --check`.
- `scripts/validate_mw_guardrails.sh` passes the legacy-port check but fails
  the display-symbol rule on the **pre-existing, unchanged**
  `frontend/src/components/ScorecardPage.jsx:775` placeholder
  `BTC or BTC-USD`, also present at the parent revision. This documentation
  branch does not fix unrelated UI code; the repository-wide guardrail check
  remains failed until that separate correction is integrated.
- Follow-up after the `09011e3c` review: documentation provenance, links,
  pinned paths, exact embedded references, in-memory schema, threshold/code
  agreement, arithmetic, and documentation-only scope checks passed. The
  59-test result above is from the initial pass; unchanged runtime code did
  not require repeating that suite. The catalog wording test remains a
  separately scoped chart-branch follow-up, not a completed check here.

The master document, checked review, navigation links, and documentation
validation are the deliverable. The archived six-agent design is not an
implementation plan; runtime behavior and existing model configuration stay
unchanged.
