# Claude design pass: exported assets

Exported on 2026-11-18 from the Claude design canvas "Moonwalking Radar Design Pass" (Moon theme, homepage and Row anatomy boards). Nothing here is wired into the app yet.

## Brief

- `BUILD_BRIEF.md`: the slice 1 build brief, plus the design-pass decisions made since (phone row fixes, row actions, brand, hover silhouette).

## SVG (vector)

| File | What it is |
|---|---|
| `svg/bhabit-header-logo.svg` | Homepage header: BHABIT lettering, three corner stars and the small moon at its top-right. Fully vector, with flat amber lettering. |
| `svg/bhabit-header-logo-render.svg` | The same layout matching the canvas exactly: the cratered lettering and the moon are embedded PNG renders, the stars are vector. |
| `svg/bhabit-wordmark.svg` | Flat amber wordmark, vector from Figma. Used in the navigation. |
| `svg/moon-rabbit-silhouette.svg` | Moon-and-rabbit hover silhouette, traced to vector paths from the canvas render. |
| `svg/moon-rabbit-mark.svg` | Small moon with the carved rabbit: a vector stand-in for the rendered moon at icon sizes. |
| `svg/stars/gleam-*.svg` | The six corner-star shapes: needle, tall, curve, burst, twin, flare (`currentColor`). |
| `svg/moon-phases/phase-*.svg` | Moon-phase loading idea, new to full (`currentColor`). |
| `svg/icons/row-star.svg`, `row-trade.svg` | Row actions, outline only (`currentColor`). |

## PNG renders (not in this repo)

The lit moon, the cratered letterings, Moonlit Edge and the Moonrise scene are rendered images that the app does not use, so they are left out of this copy to keep the repo small. They live on the design canvas and in the original export (`docs/claude-design-pass/png/` on branch `claude/local-review`, commit `929fdf1`).

## CSS and tokens

| File | What it is |
|---|---|
| `css/tokens.css` | `:root` tokens from the canvas, plus the colors and values added in this pass. |
| `css/tokens.json` | The same tokens as JSON (`base` and `designPass`). |
| `css/moon-theme.css` | Only the design-pass rules: lettering lockup, stars, moon glow, silhouette, rows and actions. |
| `css/mw-kit.css` | The complete canvas stylesheet, as published. |
