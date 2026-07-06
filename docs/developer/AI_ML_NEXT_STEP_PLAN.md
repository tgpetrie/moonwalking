# Moonwalkings AI/ML Next-Step Plan

## Purpose

This plan turns the next AI/ML work into two connected tracks:

- Tier 1: product features that improve the Moonwalkings market board, alerts, watchlist, and intelligence surfaces.
- Tier 2: learning milestones that explain how those features are built, measured, and improved.

The goal is not to chase deep learning first. The goal is to build clean market data workflows, simple models, explicit evaluation, and practical API surfaces that can become a serious portfolio project.

## Working Rule

Every iteration should produce both:

- A shipped or prototype feature in the app.
- A learning artifact that explains the data, model/rule, API contract, evaluation result, and next decision.

Use the smallest useful method first:

1. Clean data.
2. Visual inspection.
3. Rule baseline.
4. Simple scikit-learn model.
5. Evaluation against the rule baseline.
6. Only then consider heavier AI frameworks.

## Repo Anchors

Current contracts and surfaces to respect:

- `MW_SPEC.md`: source-of-truth rules for data, UI, alerts, freshness, and copy.
- `docs/DATA_PIPELINES.md`: board payload contract around `/data` and `/api/data`.
- `backend/app.py`: active Flask backend and current API surface.
- `backend/alerts_engine.py`: canonical alert engine.
- `backend/watchlist.py`: watchlist and watchlist insight endpoints.
- `backend/sentiment_api.py` and sentiment aggregator files: sentiment-specific service work.
- `frontend/src/api.js` and `frontend/src/config/api.js`: frontend API access patterns.

Important boundary: AI/ML additions should not replace the board's primary price/volume truth. They should be attached as optional analysis, experiments, explanations, and quality checks.

## Endpoint Boundary

This plan document does not change any live endpoint behavior.

Future AI/ML work should follow these endpoint rules:

- Do not modify the shape or meaning of `/data`, `/api/data`, `/api/alerts/recent`, watchlist endpoints, or existing sentiment endpoints as part of ML experiments.
- Add new work behind separate experimental routes, feature flags, scripts, notebooks, or offline reports.
- Treat the endpoint examples in this document as proposed future contracts, not active routes.
- Do not wire experimental scores into primary UI surfaces until the data and evaluation path are documented.
- Keep each future implementation on its own branch unless the task is explicitly scoped as docs-only.

## Tier 1: Product Feature Iterations

### 1. Data Lab Foundation

Feature goal:

- Create a repeatable way to export, clean, and inspect historical board snapshots.
- Start with Coinbase/CoinGecko-derived fields that already power the board.

Candidate dataset fields:

- `ts_ms`
- `product_id`
- `symbol`
- `price_now`
- `pct_1m`
- `pct_3m`
- `pct_1h`
- `volume_1h`
- `rank_1m`
- `rank_3m_gainer`
- `rank_3m_loser`
- `alert_type`
- `alert_severity`
- `market_pressure`
- `source_status`
- `age_s`

Deliverables:

- A data export script or backend command that writes snapshots to `data/` or `backend/data/`.
- A small analysis notebook or script using pandas and matplotlib.
- Basic data quality checks: missing values, duplicate `product_id` rows, stale timestamps, impossible percentages, non-numeric payload fields.

Done when:

- We can load a snapshot dataset with pandas.
- We can chart price/percent movement for a few symbols.
- We can explain what data is safe to model and what data is not ready yet.

### 2. Unusual Price Movement Detection

Feature goal:

- Detect unusual price movement without pretending it is predictive magic.
- Start with statistical baselines before ML.

Baseline methods:

- Rolling z-score per symbol.
- Median absolute deviation for robustness.
- Rank jump detection across board tables.
- Volume-confirmed movement vs price-only movement.

Possible app surface:

- Add an experimental `unusual_move_score` to internal analysis payloads.
- Later expose as `GET /api/market/anomalies`.

Evaluation:

- Count how many signals fire per hour.
- Inspect examples manually.
- Track false positives: price spike vanishes quickly, stale data, duplicate row, tiny-volume token.
- Track false negatives: obvious large move was missed.

Learning artifact:

- Short writeup explaining z-score, rolling windows, false positives, and why a simple baseline is the correct first step.

### 3. Strong vs Weak Gainers

Feature goal:

- Classify gainers as "strong" or "weak" using after-the-fact labels from historical data.

Grounded label idea:

- A "strong" gainer is still above a threshold after a future hold window, such as 5 or 15 minutes.
- A "weak" gainer fades below the threshold or reverses.

Example features:

- `pct_1m`
- `pct_3m`
- `pct_1h`
- `volume_1h`
- rank position
- rank movement
- market pressure
- alert count for symbol
- recent volatility
- age/freshness fields

Model candidates:

- Logistic regression.
- Decision tree.
- Random forest only after the simple models are benchmarked.

Possible app surface:

- Internal score first: `gainer_strength_score`.
- Later add `POST /api/market/classify-mover` for explainable experiments.

Evaluation:

- Train/test split by time, not random row shuffle.
- Precision and recall for "strong" gainers.
- Confusion matrix.
- Compare against a simple rule baseline, such as `pct_3m > X and volume_1h > Y`.

Learning artifact:

- Model card with features, label definition, metric results, and known failure cases.

### 4. Trend Persistence Scoring

Feature goal:

- Score whether a move looks likely to persist for a short window.
- Keep the wording careful: this is a persistence score, not financial advice or a price prediction.

Possible score:

- `trend_persistence_score`: 0-100.
- `trend_persistence_window`: `5m` or `15m`.
- `confidence`: based on data completeness and model/rule performance.

Possible app surface:

- Add to token detail/intelligence views before adding it to primary tables.
- Avoid turning this into alert spam.

Evaluation:

- Calibration curve: when score says 70, does the outcome happen roughly 70 percent of the time?
- Compare score buckets over time.
- Track degradation during high-volatility market periods.

Learning artifact:

- Explanation of classification probabilities, calibration, and why confidence is different from certainty.

### 5. Alert Quality And False Signal Reduction

Feature goal:

- Improve alert quality by measuring whether alerts were useful after they fired.

Useful labels:

- Alert remained directionally valid after 5 minutes.
- Alert remained directionally valid after 15 minutes.
- Alert was volume-confirmed.
- Alert duplicated another alert family too soon.
- Alert fired during stale or incomplete data.

Possible app surface:

- `POST /api/alerts/evaluate`
- `GET /api/alerts/quality-report`
- Internal alert metadata: `quality_score`, `quality_reason`, `suppression_reason`.

Evaluation:

- False positive rate by alert type.
- Alert volume per hour.
- Duplicate/suppressed alerts per hour.
- Precision by alert family.

Learning artifact:

- Before/after report showing whether suppression improved quality without hiding important moves.

### 6. Forecasting Experiments

Feature goal:

- Run forecasting experiments as learning work, not production claims.

Baseline first:

- No-change forecast.
- Last-window continuation.
- Simple moving average.

Possible models:

- Linear regression.
- Ridge regression.
- Random forest regressor.

Evaluation:

- Mean absolute error.
- Directional accuracy.
- Compare to naive baselines.
- Report where the model fails.

App boundary:

- Keep forecasting behind an experiment flag until it beats baselines consistently.
- Do not place forecast output in the primary board until it has a documented evaluation record.

Learning artifact:

- Forecasting experiment report with charts, metrics, and a decision: abandon, revise, or continue.

## Tier 2: Learning Track

### 1. Python Data Stack

Focus tools:

- pandas: clean, transform, group, filter, join, resample, and analyze data.
- scikit-learn: classical ML models, preprocessing, pipelines, metrics, and model selection.
- matplotlib: visual inspection, charts, outlier analysis, and evaluation plots.

Repo note:

- pandas and numpy are already present in the Python requirements.
- scikit-learn and matplotlib should be added when the first ML lab work starts.

Learning checkpoints:

- Load board snapshots into a DataFrame.
- Normalize symbol/product IDs.
- Convert timestamps safely.
- Find missing/stale/duplicate rows.
- Create rolling features per product.
- Plot movement and volume for selected assets.
- Save a cleaned dataset for repeatable experiments.

### 2. Classical ML Basics

Start here:

- Feature engineering.
- Train/test split by time.
- Baseline rules.
- Logistic regression.
- Decision trees.
- Random forests.
- Confusion matrix.
- Precision, recall, F1.
- MAE for regression experiments.

Avoid for now:

- Deep learning.
- AutoML.
- Complex time-series models.
- Black-box claims that cannot beat a baseline.

### 3. API Design Around AI Features

The goal is to ship AI/ML capabilities as clear backend contracts, not random helper functions.

General examples:

```http
POST /api/search-docs
POST /api/summarize-thread
POST /api/review-diff
POST /api/extract-todos
POST /api/evaluate-answer
GET  /api/search-history
```

Moonwalkings-specific candidates:

```http
GET  /api/market/movers
GET  /api/market/anomalies
POST /api/market/explain-token-move
POST /api/market/classify-mover
POST /api/watchlist/summarize
POST /api/alerts/evaluate
GET  /api/alerts/quality-report
GET  /api/ai/search-history
```

API rules:

- Inputs and outputs must be JSON-schema friendly.
- Include `source_data` or `evidence` fields for explanations.
- Include `status`, `stale`, or `insufficient_data` states instead of fake confidence.
- Keep experiment endpoints separate from production board endpoints.
- Version outputs once UI depends on them.

### 4. Generative AI And Prompt Engineering

Practical app uses:

- Explain why a token moved using board data, alerts, and sentiment context.
- Summarize watchlist changes.
- Turn alert history into a short operator-style note.
- Review a diff for risk.
- Extract todos from a dev thread or notes file.

Prompt rules:

- Give the model structured data, not vague instructions.
- Force citations to provided fields or docs.
- Require explicit uncertainty when data is missing.
- Use stable output schemas for UI rendering.
- Keep financial language cautious and factual.

Example endpoint:

```http
POST /api/market/explain-token-move
```

Example request:

```json
{
  "product_id": "BTC-USD",
  "window": "3m",
  "include": ["board_row", "recent_alerts", "market_pressure", "sentiment"]
}
```

Example response shape:

```json
{
  "status": "ok",
  "product_id": "BTC-USD",
  "summary": "BTC is rising over the 3m window with volume support.",
  "evidence": [
    {"field": "pct_3m", "value": 1.4},
    {"field": "volume_1h", "value": 24500000}
  ],
  "missing_context": [],
  "cautions": ["Short-window moves can reverse quickly."]
}
```

### 5. Evaluation For AI Output

This is a core skill, not an afterthought.

Check:

- Did it answer the actual question?
- Did it cite only available source data?
- Did it invent facts?
- Did it follow the requested JSON format?
- Did it preserve constraints?
- Is generated code runnable?
- Did it break existing behavior?
- Are false positives and false negatives acceptable?
- Can the result be tested automatically?

Deliverables:

- `eval_cases.json` for prompt/API examples.
- A small evaluation runner.
- Pass/fail checks for required fields, citations, unsupported claims, and format validity.
- A report comparing prompt versions.

Useful eval types:

- Deterministic checks: valid JSON, required keys, no forbidden language.
- Source-grounding checks: cited fields exist in the request payload.
- Human review: small curated examples with expected behavior.
- Regression evals: old examples should not get worse when prompts change.

### 6. RAG And Vector Search

Use RAG when search over project knowledge becomes useful:

- docs
- handoff notes
- alert history
- watchlist notes
- model cards
- evaluation reports

Do not start here. First create useful docs and structured records worth retrieving.

Minimum useful RAG version:

- Chunk selected docs and reports.
- Embed chunks.
- Store vectors locally.
- Search top matches.
- Ask an LLM to answer using only retrieved context.
- Return citations to source files or records.

Framework progression:

1. Direct implementation with a small vector store.
2. LangChain or LlamaIndex only when orchestration starts becoming repetitive.
3. LLM evaluation once answers are generated from retrieved context.

Possible endpoint:

```http
POST /api/search-docs
```

Response requirements:

- Matched sources.
- Snippets or compact evidence.
- Generated answer only when requested.
- No answer when retrieval quality is too low.

## Suggested First Four Iterations

### Iteration 1: Data Lab

Product output:

- Snapshot export and first data-quality report.

Learning output:

- pandas cleanup walkthrough and matplotlib charts.

Success metric:

- We can show what data is reliable enough for experiments.

### Iteration 2: Unusual Movement Baseline

Product output:

- Rule-based anomaly score generated from historical snapshots.

Learning output:

- Writeup on rolling z-score, MAD, outlier inspection, and false positives.

Success metric:

- We can explain why each anomaly fired using source fields.

### Iteration 3: Strong vs Weak Gainer Classifier

Product output:

- Prototype classifier trained on historical labels.

Learning output:

- scikit-learn model card with confusion matrix and precision/recall.

Success metric:

- The model is compared against a simple rule baseline.

### Iteration 4: AI Explanation Endpoint With Eval

Product output:

- `POST /api/market/explain-token-move` prototype.

Learning output:

- Prompt design notes plus automated eval cases for grounding and JSON format.

Success metric:

- The endpoint refuses or marks insufficient data instead of inventing unsupported explanations.

## Portfolio Structure

The final portfolio story should show:

- Problem: short-window crypto boards create noisy, fast-moving signals.
- Data: real Coinbase/CoinGecko-derived snapshots with freshness rules.
- Baselines: statistical rules before ML.
- Models: simple scikit-learn classifiers/regressors with honest metrics.
- APIs: clean endpoints that serve analysis and AI explanations.
- Evaluation: model metrics plus LLM output checks.
- UI: market board, watchlist, alerts, and intelligence surfaces using the outputs carefully.
- Engineering judgment: experimental signals are separated from source-of-truth price/volume data.

## Non-Goals

- No deep learning as the first step.
- No claims that short-window predictions are reliable without evidence.
- No AI output in the primary board unless it has a documented eval path.
- No alert spam from trend scores.
- No fabricated fallback data.
- No replacing `/data` as the board source of truth.
- No endpoint contract changes as part of this planning branch.

## Decision Log Template

Use this after each iteration:

```md
## Decision: <short name>

Date:
Feature:
Learning topic:
Dataset used:
Baseline:
Model or method:
Metrics:
Result:
Known failure cases:
Decision:
Next step:
```
