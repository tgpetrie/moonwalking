# MacBook continuation: live movers - 2026-10-27

**Resume branch: `codex/macbook-resume-20261027`.** It combines scoring work
at `2199848` and audit work at `7e3b4fb`: scripts, tests, corrected contracts,
locked results and the full handoff. Large evidence is attached to draft
GitHub release `research-handoff-20261027`, outside Git history.

## Objective and current state

BHABIT should identify coins about to surge/drop or in the earliest moments
of a move. Score, direction, lifecycle stage and data reliability stay
separate. The user asked to continue the main scoring work while progressing
the prospective 30s data-collection tangent independently.

- **Historical comparison: complete, locked, inconclusive.** M1-B2 mean daily
  IC +0.01265 is below required +0.02; the block interval [-0.00047,+0.02545]
  includes zero. Primary highest-score-band gross 5m mean is -0.03006% before
  costs. Read [the results](../research/LIVE_MOVERS_RESULTS_20261027.md).
  Do not rerun discovery/validation, retune against those dates or release
  live ranking changes. This is previously inspected history, not an
  untouched holdout or executable-fill study.
- **Prospective contract: corrected.** Match-derived counts/flow, sampled
  ticker BBO, heartbeat/REST coverage checks, sparse 5s storage, decayed sums,
  hard `EXTENDED` exclusion, fixed 30s/180s windows and >=14 valid shadow days.
  Read [the contract](../research/LIVE_MOVERS_PROSPECTIVE_CONTRACT_20261027.md).
- **First hour attempt: failed after 34m19s.** It ran 09:06:40-09:40:59 UTC
  on October 27, then lost the remote connection. `hour_gate_pass` is false.
  BTC's 5,341 and SOL's 538 paired records support ticker taker-side semantics
  in this sample. ALCX's eight and AURORA's three are inconclusive. Coverage
  is incomplete/unverified for the interrupted run. Read
  [the report](../research/results/feed_audit_20261027_interrupted/REPORT.json).
  No Windows audit process needs to be continued; start a new Mac capture.
- **Production is unchanged.** No live score, UI sort, collector, deployment
  or 5s recorder change was made. Windows port 5003 is its always-on collector.
  Do not start another backend against those stores or transfer production keys.

## Get the branch without disturbing Mac work

In the existing Moonwalking checkout, inspect its remote, status and
worktrees, then fetch. Read `AGENTS.md`, `docs/ai/AI_INDEX.md`, `HANDOFF.md`
and `MW_BACKLOG.md`. Preserve all current edits. If the resume branch already
has a worktree, use it. Otherwise, for a new local tracking branch/path:

```bash
git remote -v
git status --short --branch
git worktree list
git fetch --all --prune
git worktree add --track -b codex/macbook-resume-20261027 \
  ../Moonwalking-MacBook-20261027 origin/codex/macbook-resume-20261027
cd ../Moonwalking-MacBook-20261027
```

If the local branch already exists, omit `--track -b` and use its local name.
For a new repository, use an absent destination directory:

```bash
gh repo clone tgpetrie/moonwalking Moonwalking-MacBook-20261027 -- \
  --branch codex/macbook-resume-20261027
cd Moonwalking-MacBook-20261027
```

Use the actual Mac path. The Windows `.codex/worktrees` attachment is not
the completed worktree. No `.git`, `.codex`, `.claude` or venv copying is needed.

## Research environment and checks

Use Python 3.12 with a new local venv and the pinned small research environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r docs/ai/requirements-macbook-research-20261027.txt
.venv/bin/python -m pytest -o addopts= -q \
  tests/test_live_contract.py tests/test_live_movers_run.py \
  tests/test_live_movers_review.py tests/test_coinbase_feed_audit.py \
  tests/test_restore_macbook_evidence.py backend/tests/test_coinbase_ws.py
bash scripts/validate_mw_guardrails.sh
```

Pins: NumPy 2.5.3, pandas 3.0.6, pytest 8.3.5, websocket-client 1.9.0.
Mac/universal wheels were checked on PyPI; native Mac execution still needs
verification. Flask, frontend, account credentials and Ollama are unnecessary
for these tests/captures. Codex owns diagnostic/statistical signoff; local
14B/9B models may assist with bounded review/reporting, while code measures facts.

## Restore the evidence from GitHub

The bundle is about **112 MB compressed / 764 MB unpacked**, with exactly:

- `live_movers_contract_20261027_production/`: frozen 495,539-row public-market
  research DB, eligible CSV, contract and original manifest, unchanged hashes.
- `live_movers_comparison/`: verify/discovery/test results and persistent
  validation-attempt marker, so the once-only guard travels with the handoff.
- `feed_audit_20261027_1h/`: original raw WS/REST gzip records, capture metadata,
  hash manifest, failed status and report.

The repository is public. This draft-release bundle includes only board/feed
research data; live app/account/portfolio databases, keys and `.env` are
excluded. Use your authenticated GitHub account for the draft assets:

```bash
gh auth status
mkdir -p "$HOME/Downloads/moonwalking-handoff-20261027"
gh release download research-handoff-20261027 --repo tgpetrie/moonwalking \
  --dir "$HOME/Downloads/moonwalking-handoff-20261027" \
  --pattern 'moonwalking-live-movers-evidence-20261027.tar.gz'
.venv/bin/python scripts/restore_macbook_evidence.py \
  "$HOME/Downloads/moonwalking-handoff-20261027/moonwalking-live-movers-evidence-20261027.tar.gz"
```

Restore verifies the archive and every file against the committed
[manifest](MACBOOK_EVIDENCE_MANIFEST_20261027.json). It restores under
`~/.moonwalking/analysis`, skips identical existing files and refuses
different ones before writing. `--verify-only` checks without extraction.
Raw evidence remains outside Git; frozen research files become read-only.

Replay of the interrupted audit is safe and must still report a failed gate:

```bash
.venv/bin/python scripts/coinbase_feed_audit.py analyze \
  --run-dir "$HOME/.moonwalking/analysis/feed_audit_20261027_1h"
```

The historical `verify` phase may check transferred readiness. **Do not run
historical `discovery` or `test` again**: both are already complete and their
results/attempt guard are preserved locally and in the repository.

## Next action

Start a **new uninterrupted one-hour** paired ticker/matches/heartbeat audit
on the Mac, in a new output directory. The earlier error establishes a lost
connection, not its cause. Preserve failures and keep strict coverage/sample
gates; thin products may need more evidence. For a normal local run that
inhibits idle sleep while it executes:

```bash
caffeinate -i .venv/bin/python scripts/coinbase_feed_audit.py capture \
  --run-dir "$HOME/.moonwalking/analysis/feed_audit_macbook_20261027_1h" \
  --seconds 3600
```

This is an ordinary process; an AI need not remain active for the hour.
Review its `STATUS.json` / `REPORT.json`. Only after step 2.5 passes should
the 5s recorder and prospective shadow study proceed. Do not deploy this
research branch merely because it is the continuation checkpoint.

## Paste into Codex on the MacBook

> Resume Moonwalking from GitHub branch `codex/macbook-resume-20261027`.
> Preserve local work and read `docs/ai/MACBOOK_HANDOFF_20261027.md`.
> Restore the GitHub evidence bundle as documented. Historical validation
> is complete and inconclusive; do not rerun it. The 34-minute feed capture
> failed, so resume with a fresh one-hour MacBook audit under the corrected
> prospective contract. Keep live scores and collectors unchanged.

This file reconstructs the work even if the desktop chat or its Windows
attachment is unavailable on the MacBook.

Checkpoint verification on Windows: all **44** listed tests, repository
guardrails, link/diff checks and all **14** transfer member hashes pass.
Historical contract hashes and main-driver fingerprints remain unchanged.
