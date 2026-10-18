# Design System v1 Verification

Date: 2026-10-18
Branch: `codex/design-system-integration`

## Production compatibility

The candidate on `codex/design-system-production` combines the foundation
with the production release at `6235e2d2`. The merge is clean and preserves
the release's existing backend files byte-for-byte. Its frontend verification
passes 429 tests in 37 files. Five additional font shorthands in the release's
risk panels also use Raleway through `--font-numeric`.

Claude's six-file retention hotfix is independent and is not included here.
No production deployment was made.

## Automated checks

- Clean frontend install: `npm ci --ignore-scripts` passed.
- `npm run verify` passed: generated CSS and Figma manifest match their source,
  production build succeeded, and all 336 tests in 31 files passed.
- Repository `npm run guardrails` passed.
- `git diff --check` passed.
- CI now runs token verification, production build, and the frontend suite.

The token tests cover alias preservation, rem-to-pixel Figma conversion,
duplicate CSS mappings, missing aliases, and cycles. Component tests cover
field label/description relationships, busy buttons, disabled links, and
checkbox interaction.

## Browser checks

| Surface | Viewports | Result |
|---|---|---|
| Login | 320, 768, 1440px | No page overflow or clipped heading/button text |
| Signup | 320, 768, 1440px | Same containment; all required fields visible |
| Component gallery | 320, 768, 1440px | Responsive grids and consistent page gutters |
| Live board | 375, 1440px | No page overflow; live price font resolves to Raleway with tabular numerals |

Also verified: gallery field entry and checkbox interaction, Login-to-Signup
navigation, unauthenticated Watchlists redirect to Login, and no console
warnings/errors in the inspected browser routes. Screenshots were captured
for desktop, tablet, and phone review.

## Delivery boundary

This release establishes foundations and reusable primitives, migrates the
public/auth controls, and applies shared shell shape and spacing rules.
Dashboard, Watchlists, and Portfolio retain existing component markup for
incremental migration. The Figma deliverables are token source, a generated
Plugin API adapter manifest, and the library construction contract. No Figma
library has been published, and browser review is not a formal WCAG audit.

The build retains existing browser-data/bundle-size warnings and two existing
React test `act()` warnings. The dependency install reports existing audit
findings; dependency upgrades are outside this styling change.
