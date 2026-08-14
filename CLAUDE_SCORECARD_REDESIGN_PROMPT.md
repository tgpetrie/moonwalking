# Scorecard Redesign Brief for Claude

Work on branch: `codex/scorecard-redesign-compare`

Goal:
Redesign the scorecard page so it feels understandable to a normal user in the first 10 seconds. The current page has too much raw data and too much internal terminology. Keep the useful data, but make it easier to scan, explain, and act on.

Important constraints:
- Do not remove the current implementation.
- Keep the existing scorecard page available as the baseline.
- Add a separate redesign path so the old and new versions can be compared side by side if needed.
- Preserve the existing data fetching and tests unless a change is necessary for the redesign.
- Prefer user language over internal language.
- Make every metric answer one of these questions:
  - What is this?
  - Why should I care?
  - What can I do with it?

Recommended design direction:
- Put the active coin or focus asset at the top before the page title.
- Make the hero answer:
  - what coin / asset this view is about
  - whether the data is live, preview, or demo
  - what the user can do next
- Reduce the number of competing sort/filter controls.
- Convert dense metrics into a smaller number of actionable summary cards.
- Add click-to-expand explanations on cards:
  - plain English explanation
  - what the metric means
  - when to trust it
  - what a user should do with it
- Keep board summary and signal summary, but make them feel like user-facing insights, not analytics internals.
- If a section is only helpful to power users, hide it behind an optional toggle.

UX priorities:
- The page should make sense without reading every label.
- The page should clearly distinguish:
  - signal scorecards
  - board scorecards
  - coin drilldown
- The page should explain "ready" vs "learning" in plain language.
- The page should explain "follow-through", "reversed", and "edge vs random" in user language.
- The page should suggest what action a user might take after reading each card.

Suggested structure:
1. Hero
   - coin / asset focus
   - one-sentence summary
   - one or two key headline metrics
2. "What is working"
   - a simplified signal summary
3. "How boards are behaving"
   - board summary cards
4. "Coin drilldown"
   - search / inspect a coin
5. Optional advanced details
   - the deeper stats for power users

Implementation guidance:
- Keep the existing route intact.
- Add a redesign route or variant for comparison, such as:
  - `/scorecard-redesign`
  - `/scorecard?variant=redesign`
  - or a feature flag in the app shell
- If it helps, add a small route switcher or header toggle so the old and new versions can be opened quickly in the browser.
- Make sure the redesign is responsive.
- Avoid burying the coin name at the bottom of the page.
- Avoid labels like "Most tested" if they do not help users make decisions.

Acceptance criteria:
- A user can tell what asset the scorecard is about without scrolling.
- A user can understand the main sections without knowing internal terminology.
- A user can click into a card and get a human explanation.
- The old version remains available for comparison.
- The new version does not break the existing tests or build.

Suggested first pass:
- Start by simplifying the hero and the summary cards.
- Then add explanatory details to the signal and board cards.
- Finally, wire up the compare route or toggle.

