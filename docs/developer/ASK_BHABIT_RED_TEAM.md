# Ask Bhabit Red-Team Checks

This checklist is grounded in the integrated backend and frontend implementation.
It does not add an LLM-as-judge dependency and does not assume universal TTLs or
fixed conflict thresholds.

## Deterministic Guards

- Asset identity is registry-backed for the milestone assets. `SHDW` resolves to
  the Solana Shadow Token mint, and ticker-like `SHADOW` is unsupported rather
  than silently mapped.
- Missing values remain `null` through backend packet construction and frontend
  normalization. UI formatting must show an em dash, not zero.
- Missing-data states stay distinct: `unsupported`, `not_configured`, `stale`,
  `provider_error`, and `conflicting` each render separately.
- Backend source fields, `retrieved_at`, `freshness`, `missing_data_reason`,
  `provider_error`, and `conflicts` must survive the API-to-UI path.
- Snapshot comparison is deterministic and computed outside the model. It must
  not invent catalysts or collapse `only_price_changed` into market-structure
  changes.
- Prompt-injection strings inside asset metadata are treated as data in the JSON
  packet. They are never allowed to become executable UI behavior.
- Public API output must not expose API keys, environment-variable contents, or
  internal prompts.

## Financial-Advice Language

Ask Bhabit is position-aware analysis, not autonomous advice. Provisional audit
helpers should flag high-risk imperative language such as direct buy/sell/hold
commands, guarantees, or promises of profit. This cannot rely on one regex:

- False positives: "sell pressure increased" is market description, not advice.
- False negatives: subtle advice can avoid obvious keywords.
- Current mitigation: deterministic tests cover structure and data provenance;
  copy review should still inspect generated text before broad release.

## Integration Boundaries

- Demo fixtures are allowed only when visibly labeled as demo/fixture mode.
- Live backend mode must never fake a successful model analysis when the backend
  returns `not_configured`.
- Client-side beta allowance is demo-only. Live usage accounting needs a real
  backend allowance before it is shown as funded quota.
- Spot evidence and derivatives evidence remain separate sections. UI labels
  must not combine spot holdings with perp positioning as one exposure.

## Manual Review Before Release

- Confirm SHDW copy never says Shadow Exchange.
- Confirm unsupported derivative rows are explicit for assets without perp
  markets.
- Confirm stale/error/conflicting rows are visually non-neutral.
- Confirm sources can be inspected without exposing secrets or internal prompts.
- Confirm the real app mount is the existing Ask Bhabit dock in
  `frontend/src/components/AskBhabitPanel.jsx`.
