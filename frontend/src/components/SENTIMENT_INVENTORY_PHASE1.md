Sentiment Inventory — Phase 1 (Repo-only, No Edits)

Scope

This inventory is based strictly on repo search outputs (imports/refs). External editor files not present in the repo are treated as out-of-scope artifacts.

Canonical runtime owner
• frontend/src/App.jsx mounts frontend/src/components/DashboardShell.jsx (DashboardShell is the live board container; Dashboard.jsx exists but is not the mounted entry in App.jsx based on grep output).
• DashboardShell.jsx owns the sentiment open flow via onInfo + window openInfo event handling.

Live sentiment modal chain (active)
• Modal component: frontend/src/components/SentimentPopupAdvanced.jsx
• Hook used by modal: useTieredSentiment (imported inside SentimentPopupAdvanced.jsx)
• Modal CSS: frontend/src/styles/sentiment-popup-advanced.css (imported in SentimentPopupAdvanced.jsx)
• Open flow:
  • DashboardShell.jsx passes onInfo into tables/watchlist components
  • onInfo triggers modal open + sets the symbol (or dispatches openInfo)
  • DashboardShell.jsx renders SentimentPopupAdvanced with isOpen + symbol props

Additional sentiment data paths (also active)

A) Context-driven sentiment (active)
• Provider appears to be mounted:
  • frontend/src/App.jsx imports and wraps with SentimentProvider
  • frontend/src/main.jsx also imports and wraps with SentimentProvider
• Consumers:
  • frontend/src/components/TokenRow.jsx
  • frontend/src/components/SentimentCard.jsx
• Risk: Provider is double-mounted (see RED FLAG #1).

B) Hook-driven sentiment (active but separate)
• Hook: frontend/src/hooks/useSentiment.js
• Used by:
  • frontend/src/components/InsightPanel.jsx

C) useSentimentLatest path (active but separate)
• Hook: frontend/src/hooks/useSentimentLatest.js
• Normalizer: frontend/src/adapters/normalizeSentiment.js
• Used by:
  • frontend/src/components/cards/SentimentCard.jsx
  • frontend/src/components/InsightsTabbed.jsx
  • frontend/src/components/cards/SentimentPanel.jsx
• Notes:
  • This path is distinct from the modal’s useTieredSentiment.

CSS that is actually loaded
• frontend/src/index.css imports ./sentiment-v2.css
• SentimentPopupAdvanced.jsx imports ../styles/sentiment-popup-advanced.css
• SentimentPanel.jsx imports ../../styles/sentiment-panel.css

Duplicate-name / drift hazards to track
• Two SentimentCard files exist and appear referenced:
  • frontend/src/components/SentimentCard.jsx (context-driven consumer; direct import sites into other components not shown in provided outputs—presence in repo confirmed)
  • frontend/src/components/cards/SentimentCard.jsx (imported by AssetTabbedPanel, MetricsPanel, InsightsTabbed, GainersTable1Min.clean)
• Three useSentiment implementations exist:
  • frontend/src/context/SentimentContext.jsx exports useSentiment() (context, no args)
  • frontend/src/hooks/useSentiment.js exports useSentiment(symbol, ttlSec) (hook, args)
  • frontend/src/hooks/useSentiment.ts exports useSentiment(symbol, options) (confirmed 0-ref)

Docs (non-runtime, but keep)
• frontend/src/components/SENTIMENT_FIX_V3.md
• frontend/src/components/SENTIMENT_CARD_V2.md
• frontend/src/components/CBMo4ers_SENTIMENT_READINESS_FINAL.md

External demo artifacts (not in repo; not runtime)
• sentiment-popup-production.js / sentiment-popup-production.css
• Not found in repo, not imported, not deployable as-is. Treat as external reference only.

RED FLAG #1 — Double SentimentProvider mount (Top Phase 2 fix)
• frontend/src/main.jsx wraps <App /> with <SentimentProvider>
• frontend/src/App.jsx wraps its children with <SentimentProvider> again
Risk: duplicate fetch timers, duplicate caches, inconsistent loading/error flips.

RED FLAG #2 — useSentiment name collision / drift
• frontend/src/context/SentimentContext.jsx exports useSentiment() (context, no args)
• frontend/src/hooks/useSentiment.js exports useSentiment(symbol, ttlSec) (hook, args; different return shape)
• frontend/src/hooks/useSentiment.ts exists but is 0-ref (confirmed)

Phase 2 safe-quarantine candidates (0-ref within frontend/src; confirmed)
• frontend/src/hooks/useSentiment.ts
• frontend/src/lib/sentimentAdapter.js

Do-not-move list (referenced by runtime paths)
• frontend/src/components/SentimentPopupAdvanced.jsx
• modal hook useTieredSentiment.*
• frontend/src/styles/sentiment-popup-advanced.css
• frontend/src/components/DashboardShell.jsx
• frontend/src/components/TokenRow.jsx
• frontend/src/components/InsightPanel.jsx
• frontend/src/context/SentimentContext.jsx
• frontend/src/hooks/useSentiment.js
• frontend/src/components/cards/SentimentPanel.jsx
• frontend/src/components/cards/SentimentCard.jsx
• frontend/src/components/InsightsTabbed.jsx
• frontend/src/hooks/useSentimentLatest.js
• frontend/src/adapters/normalizeSentiment.js
• frontend/src/styles/sentiment-v2.css
• frontend/src/styles/sentiment-panel.css
