# Chart level explanations and local evidence handoff

## Delivered

The price guide separates recent observed turning levels from calculated recovery
references and the selected high/extension. Every reference shows signed percentage
distance `(level / analysis_close - 1) * 100`, with the dated completed weekly or
daily analysis close explicitly named. Recent turns are not labelled nearby.
Distances are price changes, not expected returns, probabilities or rankings.

Explain buttons show a turn's actual daily extreme date, analysis candle start,
confirmation date and conditional context. Calculated references also show the
substituted linear-price formula, regardless of logarithmic chart display. Selected
source candles are highlighted. Selecting a calculated reference synchronizes E?.
Chart A–D and E? pointer clicks open the same explanations; ordinary HTML buttons
provide keyboard access. View source candles reuses retrospective inspection without
changing the original analysis interval, cutoff or reference close. Fit history returns.
Changing macro anchors clears the selection; replay/timeframe/confirmation changes
remount the analysis, preventing an old explanation from surviving into a new view.

FET frozen replay through July 23: weekly analysis close $0.1567 through July 19;
recent low $0.1843 is +17.6%, recent high $0.2884 is +84.0%, macro low $0.1338 is
−14.6%. These differ from the timing panel's explicitly labelled latest **daily**
close distances. The 61.8% recovery reference is $2.2048416 (+1,307.0% from the
weekly close), displayed $2.205. These are historical-source calculations, not
illustrative numbers and not evidence of future performance.

## External assistance

Tom authorized assistance from Claude and Gemini. Sent separate read-only review
assignments through their signed-in browser services; neither was asked to edit
the repository, retrieve private stores or choose new predictive thresholds.

- [Claude review](https://claude.ai/chat/febcde95-ad6f-4dbc-b29b-d48566b8d841)
- [Gemini review](https://gemini.google.com/app/429b7d197fd4e397)

Both independently calculated the supplied FET distances and flagged the distinction
between recent and nearby, between recovery ratio and return, and between extreme,
bar and confirmation dates. They reviewed the supplied brief, not repository code,
raw prices, video or test executions. Their agreement is not predictive validation.

Accepted: neutral signed distances, dated reference close, explicit formula/scale,
confirmation availability, separate observed/calculated roles, no inferred arrival
dates, and deterministic evidence for future local explanations.

Not adopted: declaring a calculated level "never traded" without checking history;
automatic recalculation on any low breach (confirmed anchors govern selection);
invented drawdown thresholds; hiding the future overlay by default contrary to
Tom's request; blanket word bans that would also reject honest statements such as
"no probability established." Source claims and numeric echoes alone are not a
complete validator for model reasoning. No study findings were connected to the UI.

## Local agent foundation

`scripts/chart_evidence_packet.mjs` now emits versioned offline JSON using the same
deterministic calculation functions as the chart. It reads only the explicitly
provided history file, hashes it, carries provenance/cutoffs, and emits dated anchors,
levels, signed distances and reaction evidence. Optional output is create-only.
No network, credentials, data-store discovery, orders or model calls are implemented.
See `LOCAL_CHART_AGENT_CONTRACT_2026-10-18.md` for use and boundaries.

Real local FET smoke output is ignored under
`frontend/.runtime/chart-evidence-fet-polish-v1.json`; it is not committed.
The installed Ollama status command reported "upgrade in progress"; no model job,
download, installer or runtime configuration change was performed by this work.
This packet producer is a foundation, not a completed model agent or dashboard agent
runtime. The separate `claude/agents-page` branch has not been merged here.

## Verification

- Full frontend verify: 541 tests, token/Figma synchronization and production build pass.
- Following final synchronization/copy edits: 18 relevant tests and production build pass.
- Offline CLI: 4 tests pass, including future-price poisoning/prefix invariance and
  refusal to overwrite output/input; actual FET packet generation also passes.
- Guardrails and diff whitespace checks pass.
- FET browser interaction verified both source highlights and selected E? ratio;
  phone layout checked with no page overflow, temporary viewport restored.
- Existing Browserslist age, large bundle and AlertsPanelGlobal act warnings remain.

No production deployment or branch integration performed. Source data, token
migration boundaries and geometry formulas are unchanged.
