# SENTIMENT INTEGRATION CHECKLIST (Single Board, Truth-State)

Owner: Treal  
Branch: CBSentiment  

Canonical ports:
- Backend (Flask): 5003
- Sentiment pipeline (FastAPI): 8002
- Frontend (Vite): 5173

Principles:
- One board reality: Movers/alerts remain the canonical triggers.
- One frontend contract: UI consumes ONE route + ONE normalized shape.
- Truth-state always: No fabricated 50s / placeholders when offline.
- Relative paths only in frontend: `/api/...` via Vite proxy.
- Backend is the only layer that talks to the pipeline.

---

## Current State Snapshot (fill in as you confirm)
- [ ] Current sentiment UI entrypoint is: (choose)
  - [ ] Advanced modal only
  - [ ] Panel/card + modal
- [ ] Current live advanced UI file:
  - `frontend/src/components/SentimentPopupAdvanced.jsx` ✅
- [ ] Current hook:
  - `frontend/src/hooks/useSentimentLatest.js` ✅
- [ ] Normalizer:
  - `frontend/src/adapters/normalizeSentiment.js` ✅
- [ ] Backend endpoint used by frontend:
  - [ ] `/api/sentiment/latest`
  - [ ] other: ___________

Notes:
- Advanced modal currently contains default fallbacks (`|| 50`, etc.) that must be removed or gated by pipelineStatus.

---

## Definitions (Truth Contract)

### Backend must always return `sentiment_meta`
Required keys:
- `ok` (bool)
- `pipelineRunning` (bool)
- `staleSeconds` (int)
- `lastOkTs` (iso string or null)
- `lastTryTs` (iso string or null)

Optional:
- `error` (string)
- `mode` ("lite" | "deep")

### Frontend truth-state mapping
- LIVE: meta.ok === true AND meta.pipelineRunning === true AND staleSeconds < 120
- STALE: hasData but staleSeconds >= 120 OR pipelineRunning true but stale
- OFFLINE: meta missing and no data OR meta.pipelineRunning false and ok false

Never show numeric sentiment values when OFFLINE unless they are explicitly labeled as cached/stale.

---

# TOOLING RULES (Claude vs Codex)

## Claude = editor
Claude is allowed to:
- make code edits
- update CSS/UI
- add/modify docs

Claude must not:
- invent data
- add placeholder numeric defaults (50/0) that look real

## Codex = auditor
Codex is allowed to:
- run greps/searches/curls/timings
- produce PASS/FAIL tables with file+line receipts

Codex must not:
- edit files
- propose refactors (auditing only)

---

# PHASE 1 — Inventory & Ground Truth (No edits)

Goal: verify exactly what’s live and where modal is opened.

### Tasks
- [ ] Identify where the sentiment modal is mounted (Dashboard/App/Context)
- [ ] Identify how “open sentiment” is triggered (onInfo/global event/etc.)
- [ ] Confirm symbol normalization path (BTC-USD -> BTC)

### Commands (paste outputs)
```bash
rg "SentimentPopupAdvanced" frontend/src -n
rg "SentimentPanel" frontend/src -n
rg "openInfo|onInfo|sentiment" frontend/src -n

Receipts

Paste:
	•	File path(s) and line(s) where Advanced modal is mounted:
	•	File path(s) and line(s) where sentiment open is triggered:
	•	File path(s) and line(s) where symbol is normalized (BTC-USD -> BTC):

Done means
	•	We can point to the single place that owns sentimentOpen + sentimentSymbol
	•	We know exactly which UI triggers openSentiment()
```

⸻

PHASE 2 — Kill Fake Defaults in Advanced Modal (Truth-state UI)

Goal: Advanced modal never shows fake numbers.

Required behavior
	•	OFFLINE: show OFFLINE badge + “—” values; disable charts/insights generation
	•	STALE: show STALE badge; numbers allowed but visually marked stale; charts optional
	•	LIVE: show full UI

Tasks
	•	Remove || 50 patterns for Fear & Greed
	•	Remove fake default sources/tier counts (no “Tier 1/2/3” numbers unless real)
	•	Remove fake fallback prices in charts (no price || 45000)
	•	Gate charts initialization: only when LIVE and history exists
	•	Gate “Top Insight” generation: only when LIVE and required metrics exist
	•	Header status badge must reflect real sentiment_meta (LIVE/STALE/OFFLINE)

Claude edit targets
	•	frontend/src/components/SentimentPopupAdvanced.jsx
	•	(if needed) its CSS file: frontend/src/styles/sentiment-popup-advanced.css

Codex audit (no edits) — Forbidden default scans

rg "\|\|\s*50" frontend/src/components/SentimentPopupAdvanced.jsx -n || true
rg "45000" frontend/src/components/SentimentPopupAdvanced.jsx -n || true
rg "sourceBreakdown\s*\|\|" frontend/src/components/SentimentPopupAdvanced.jsx -n || true
rg "fearGreedIndex.*\|\|" frontend/src/components/SentimentPopupAdvanced.jsx -n || true

Done means
	•	OFFLINE shows “—” not “50”
	•	Charts tab doesn’t fabricate values
	•	Header status reflects real pipeline state

⸻

PHASE 3 — Build a Minimal Launcher Panel (Optional but recommended)

Goal: a stable small “Sentiment” surface that opens Advanced modal, using the same hook and the same normalized shape.

If you currently open only Advanced via info-clicks, this phase creates a canonical entrypoint and reduces “where do I click?” friction.

Tasks
	•	Ensure a single component exists: SentimentPanel (or card) that:
	•	shows pipelineStatus badge
	•	shows 1–2 metrics only when LIVE
	•	has a button: Open (opens Advanced modal)
	•	Panel must not call extra endpoints (only use the same hook)

Claude edit targets
	•	frontend/src/components/cards/SentimentPanel.jsx (or create if missing)
	•	Wherever the panel is placed (Dashboard layout owner)

Done means
	•	Panel renders even when pipeline is OFFLINE
	•	Clicking Open launches Advanced modal reliably (symbol rules apply)

⸻

PHASE 4 — One Open Function (No duplicated wiring)

Goal: everything uses a single openSentiment(rawSymbol) function.

Tasks
	•	Create openSentiment() in the canonical owner (Dashboard/App/Context)
	•	Normalize product_id to symbol inside that function (BTC-USD -> BTC)
	•	Wire:
	•	row info clicks
	•	panel Open button
	•	any global event backstop (if you keep it)
to call openSentiment()

Done means
	•	Every entrypoint opens the same modal
	•	Symbol always arrives as base symbol

⸻

PHASE 5 — “Lite vs Deep” without two frontends

Goal: same route + same shape, richer data only when available.

Backend contract extension (optional)

Add sentiment_meta.mode = "lite" | "deep".

UI behavior
	•	Lite:
	•	Overview shows only what exists (no invented values)
	•	Charts tab hidden/disabled with message “Unavailable in lite”
	•	Sources tab must not claim sources are live unless backend confirms
	•	Deep:
	•	Tabs enabled when the data exists

Done means
	•	You can ship “lite” now safely
	•	Turning on deep later lights up extra UI without rewriting frontend

⸻

PHASE 6 — System Verification (Codex receipts)

Goal: prove we do not have two boards, and nothing lies.

A) Frontend relative paths only

rg "http://" frontend/src -n || true
rg "127\.0\.0\.1|localhost|:5003|:8002" frontend/src -n || true

B) Vite proxy proof

Paste the /api proxy block from:
	•	frontend/vite.config.js

C) Endpoint truth

curl -sS http://127.0.0.1:5003/api/sentiment/latest | head -c 2000
curl -sS http://127.0.0.1:5003/api/sentiment/latest | jq '.sentiment_meta'

D) Offline non-blocking proof

Stop pipeline (or point SENTIMENT_PIPELINE_URL to dead port), then:

time curl -sS http://127.0.0.1:5003/api/sentiment/latest | head -c 2000
time curl -sS http://127.0.0.1:5003/api/data | head -c 2000

PASS/FAIL table (fill after Codex audit)

Goal	Pass?	Evidence
Relative paths only	[ ]	
Vite proxy correct	[ ]	
Backend only talks to pipeline	[ ]	
sentiment_meta always present	[ ]	
Offline is fast + truthful	[ ]	


⸻

CHANGELOG (keep short)
	•	YYYY-MM-DD: ______________
	•	YYYY-MM-DD: ______________

⸻

NOTES / OPEN QUESTIONS
	•	Do we keep a “sources metadata” list in UI even in lite mode?
	•	Which chart(s) are allowed in lite mode (if any)?
	•	Do we want a single modal only, or panel + modal for discoverability?

⸻

How to use it (workflow)
	1.	Create the file and commit it alone:

mkdir -p docs
git add docs/SENTIMENT_INTEGRATION_CHECKLIST.md
git commit -m "Docs: add sentiment integration checklist"

	2.	For each phase:

	•	Claude: you paste only the phase section + the relevant files; Claude edits.
	•	Codex: you run the audit commands and paste raw output into the receipts area.
	•	You check the boxes as each phase is verified.

⸻

When Gemini would be useful (rare)

Only if you want a third opinion on the scoring math/statistics. For wiring/truth-state/contract enforcement, Claude + Codex is enough.

---

## Where to go from there (exact next steps)

### Step 1 — Commit the checklist doc (solo commit)
```bash
git add docs/SENTIMENT_INTEGRATION_CHECKLIST.md
git commit -m "Docs: add sentiment integration checklist"

Step 2 — Run Phase 1 commands and paste receipts (no edits yet)

rg "SentimentPopupAdvanced" frontend/src -n
rg "SentimentPanel" frontend/src -n
rg "openInfo|onInfo|sentiment" frontend/src -n

Paste those outputs into the Phase 1 “Receipts” section.

Step 3 — Decide the next phase (it will almost certainly be Phase 2)

Given what you showed earlier, Phase 2 is the immediate win: remove fake fallbacks (50, fake sources, fake prices) and derive LIVE/STALE/OFFLINE strictly from sentiment_meta / pipelineStatus.

Step 4 — Claude ticket you give next

Once Phase 1 receipts confirm the live file chain, the next Claude instruction is:
	•	“Phase 2 — Kill Fake Defaults in the Advanced modal. Edit only the live popup and its CSS if needed. No refactors.”

Step 5 — Codex audit receipts after Claude edits

Run the Phase 2 forbidden scans + Phase 6 endpoint checks and paste results. That’s your “prove it” layer.

⸻

If you paste your Phase 1 rg outputs here, I’ll tell you exactly:
	•	which checkboxes you can tick immediately,
	•	which file is the canonical owner for openSentiment(),
	•	and whether we should do Phase 2 before Phase 4 (likely yes) or vice versa.
