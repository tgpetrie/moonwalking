# Local agents and local models

This document defines the local-first agent layer for Moonwalking. It is written
for Tom, Codex, Claude, and any other developer or model that needs to continue
the work.

## Goal

Moonwalking agents are local workers that gather better evidence, improve app
development, and help Tom read his personal portfolio more clearly. They are not
trading bots, portfolio managers, or a replacement for the canonical price
board.

There are two lanes:

1. Product-development agents improve the app's efficiency, accuracy, scope,
   testing, and handoff quality.
2. Portfolio-intelligence agents process the real portfolio/watchlist/risk data
   and surface evidence-backed watch items.

Both lanes write observations into the same local ledger so the app, a dev, or a
local model can review one shared fact trail.

The first useful version has two layers:

1. Deterministic agents inspect real app payloads and write observations.
2. An optional local model summarizes those observations in plain language.

The deterministic observations are the source of truth. The local model is only
a narrator.

## Current implementation

Backend package:

- `backend/agents/contracts.py` defines the observation contract.
- `backend/agents/store.py` stores runs and observations in SQLite.
- `backend/agents/audit_triage.py` reads saved audit Markdown and converts
  ranked problems, recommended changes, and implementation phases into
  structured observations.
- `backend/agents/data_quality.py` checks payload freshness, identity, prices,
  duplicate rows, Coin Pressure missing-price states, and unmeasured track
  records.
- `backend/agents/tape_scout.py` flags fast 1m or 3m moves as watch items.
- `backend/agents/portfolio_watch.py` reads portfolio risk-board rows and flags
  protection, watch, entry-watch, fallback, and unavailable-plan states.
- `backend/agents/development_efficiency.py` turns repo and test state into
  handoff observations for faster multi-model development.
- `backend/agents/runner.py` runs the current deterministic agents once.

Local model package:

- `backend/local_ai/client.py` talks to an OpenAI-compatible local server such
  as Ollama or LM Studio.
- Local models are disabled by default.
- Remote LLM URLs are rejected unless `BHABIT_LLM_ALLOW_REMOTE=1` is set.

Runner:

- `scripts/run_local_agents.py` fetches the local backend payload and records
  one agent pass.

SQLite output:

- Default path: `backend/data/agent_observations.sqlite`
- Override: `MW_AGENT_OBSERVATIONS_DB`

Read-only API surface:

- `GET /api/agents/status`
- `GET /api/agents/observations?limit=100`
- `GET /api/agents/observations?symbol=BTC`

These routes read the local ledger. They do not run agents, place trades, or
change the board source of truth.

`/api/agents/status` also returns `agent_summaries`: one row per agent the
runner knows about (including agents that have never run here), with its label
and purpose from `backend/agents/catalog.py`, its latest run, a derived `state`,
and that run's findings counted by severity. States come only from recorded
runs:

- `never_run`: no run recorded on this machine.
- `running`: the latest run started and hasn't finished.
- `interrupted`: the latest run never finished and started 15+ minutes ago
  (the process most likely died).
- `failed`: the latest run finished with an error.
- `idle`: the latest run finished OK. Agents run on demand, so this is the
  normal resting state.

## Agents page

`/app/agents` (member sidebar: **Agents**) is a read-only view of the ledger:

- Summary tiles: agents known and how many have run here, last pass, current
  (non-expired) findings, and how many are critical or warning.
- One card per agent: state, purpose, last activity, run count, the latest
  run's findings by severity, and the error text when a run failed.
- Findings: newest first, filterable by agent and severity, with each
  finding's evidence fields and a link to the app page it came from (Live
  Board, Risk Board). Expired findings are hidden unless "Show expired" is on.
- Audit queue: audit-triage findings grouped into problems, recommended
  changes and implementation steps, labelled *identified, not tracked*.
- Local model narrator: on/off and which model, nothing more.

Not built yet: audit task states (queued, working, awaiting review, verified)
and a record of the changes and checks behind each fix. Today the audit agent
only lists work, so the page says so instead of implying progress tracking.

The page has no control that runs agents, edits code or trades. Run agents with
`scripts/run_local_agents.py`; the page refreshes every 30 seconds while
visible, or on demand with Refresh.

The audit agent parses one specific layout (`## B. Ranked UX problems` with
`### P0`/`### P1`/`### P2`, `## C. Exact recommended changes` table, `## E.
Smallest coherent implementation sequence`). None of the audit documents
currently in the repository use that layout, so the queue stays empty until an
`AUDIT.md` in that format is passed with `--audit-file`.

## Local model settings

Use paid OpenAI or Claude models to design and review the system if useful, but
runtime summaries can stay local.

Recommended environment shape:

```bash
BHABIT_LLM_ENABLED=1
BHABIT_LLM_PROVIDER=ollama
BHABIT_LLM_BASE_URL=http://127.0.0.1:11434/v1
BHABIT_LLM_MODEL=<local-model-name>
BHABIT_LLM_TIMEOUT_SECONDS=20
```

LM Studio can use the same contract if its local server exposes an
OpenAI-compatible `/v1/chat/completions` endpoint:

```bash
BHABIT_LLM_PROVIDER=lmstudio
BHABIT_LLM_BASE_URL=http://127.0.0.1:1234/v1
BHABIT_LLM_MODEL=<loaded-model-name>
```

On Tom's RTX 3060 12GB machine, start with 7B to 12B 4-bit instruct models for
daily local use. Larger models can work with CPU offload, but they will be slow
and should not block the app loop.

Good first candidates to test locally:

- Gemma 4 12B for general briefing and explanation.
- Qwen3 8B or 14B instruct for structured summaries and careful reasoning.
- Llama 3.x 8B-class instruct models as a widely supported fallback.

Model choice should be evaluated against local examples before being trusted in
the UI.

## Observation contract

Every observation has:

```json
{
  "agent": "data_quality",
  "kind": "missing_or_invalid_price",
  "severity": "warning",
  "product_id": "BTC-USD",
  "symbol": "BTC",
  "summary": "BTC is missing a usable current price.",
  "evidence": {"field": "price_now"},
  "source": {"surface": "board"},
  "created_ts": 1791830400,
  "expires_ts": null
}
```

Rules:

- Cite fields in `evidence`.
- Use `severity` as operator priority, not a price prediction.
- Keep missing data as missing. Do not fill unknown price, volume, history, or
  portfolio fields with guesses.
- Expire short-window observations when they age out.

## First agents

### Data Quality Agent

Purpose: catch the exact problems that make the UI look confusing or dishonest.

Examples:

- Board snapshot is stale.
- Table contains duplicate `product_id` values.
- Row has no usable current price.
- Coin Pressure payload is missing current price.
- Track-record rows are all `0 of 100 market periods`, so rates must stay
  hidden.

### Audit Triage Agent

Purpose: let agents work from `AUDIT.md` instead of relying on chat memory.

It extracts:

- P0/P1/P2 ranked problems.
- Exact recommended changes.
- The smallest coherent implementation sequence.

The output is a structured task trail. It does not automatically edit files; a
developer or coding agent still chooses the next coherent patch and verifies it.

### Tape Scout Agent

Purpose: find fast price movement that deserves attention.

It uses rule thresholds only:

- 1m absolute move at or above 2%.
- 3m absolute move at or above 4%.

It writes a watch observation and explicitly avoids forecast language.

### Portfolio Watch Agent

Purpose: help Tom read his personal portfolio from the same risk-board payload
the app already uses.

Examples:

- A held coin is in the highest protection bucket.
- A held coin is in a watch bucket.
- A coin has an entry-side watch state.
- Portfolio data is unavailable and the board fell back to watchlist-only data.
- Some coins lack enough candle history for a plan.

Rules:

- Use position size only when the payload source is `portfolio`.
- Do not infer holdings from watchlist-only rows.
- Do not recommend orders. Surface the state and the evidence.

### Development Efficiency Agent

Purpose: make Codex, Claude, and human developer handoffs tighter.

Examples:

- Local uncommitted files need a handoff note before another model edits nearby
  files.
- Code changed without a docs update.
- Test failures need attention before handoff.

This agent is intentionally simple. It should help development flow without
trying to autonomously rewrite the project.

## How to run locally

Start Moonwalking with the normal local dev command, then run:

```bash
python scripts/run_local_agents.py
```

Optional watchlist-style risk fallback:

```bash
python scripts/run_local_agents.py --symbols BTC,ETH,SOL
```

Run agents against a saved audit:

```powershell
python scripts\run_local_agents.py --audit-file "C:\path\to\AUDIT.md"
```

Run the backend tests on Windows through the repo wrapper:

```powershell
.\scripts\test_backend.ps1 backend\tests\test_agents_data_quality.py backend\tests\test_agents_store_and_local_ai.py backend\tests\test_agents_portfolio_and_dev.py
```

The wrapper chooses the project virtual environment when present. Default
pytest settings do not require the optional coverage plugin, so a missing
`pytest-cov` install no longer blocks normal local testing.

Read observations from SQLite:

```bash
python - <<'PY'
from pathlib import Path
import sqlite3

db = Path("backend/data/agent_observations.sqlite")
conn = sqlite3.connect(db)
for row in conn.execute(
    "SELECT created_ts, agent, severity, symbol, kind, summary "
    "FROM agent_observations ORDER BY created_ts DESC LIMIT 20"
):
    print(row)
PY
```

On Windows PowerShell, run the same query through a short `.py` file or the
Python REPL if heredoc syntax is unavailable.

## How to extend

Add a new deterministic agent when it can produce evidence without a model.

Good next agents:

- Baseline Builder: records rolling per-symbol movement and volume baselines.
- Signal Grader Agent: compares fired signals with later outcomes.
- Dev Triage Agent: turns failing tests, logs, and recent diffs into a concise
  repair queue.
- Scope Mapper Agent: finds which routes, components, tests, and docs are
  touched by a proposed feature before work starts.
- Audit Worker Agent: takes one audit observation, maps it to files/tests, makes
  a small patch, and reports verification.
- Accuracy Auditor Agent: compares UI claims against source fields so copy does
  not outrun measured evidence.
- External Context Agent: collects configured real providers and reports
  unavailable states honestly.
- Briefing Agent: uses the local model to summarize the latest observations.

Each new agent should include:

- A pure function or small class under `backend/agents/`.
- Tests under `backend/tests/`.
- Evidence fields for every claim.
- Documentation in this file or a linked model card.

## Boundaries

- Do not change `/data`, `/api/data`, `/api/alerts/recent`, watchlist
  contracts, or sentiment contracts for agent experiments.
- Do not use generated model text as a source of truth.
- Do not place local-model output in primary board surfaces until there are
  eval cases.
- Do not add order, cancel, transfer, or withdrawal behavior.
- Do not hide missing data behind cheerful copy.

## Evaluation path

Before a local model summary is shown in the UI, add examples that check:

- Output uses only supplied observations.
- Output preserves missing-data states.
- Output avoids buy/sell instructions.
- Output returns the required format.
- Output does not quote success rates when the track record is unmeasured.

Use the decision log format in `docs/developer/AI_ML_NEXT_STEP_PLAN.md` after
each iteration.
