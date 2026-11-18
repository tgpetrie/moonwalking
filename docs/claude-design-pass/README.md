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

## PNG (renders)

The lit moon, the cratered lettering and the Moonrise scene are rendered images, so they ship as PNG.

| File | Use |
|---|---|
| `png/moon-rabbit-1024.png` | Moon Rabbit: white carved rabbit, purple eye, calmer terrain. |
| `png/moon-rabbit-icon-192.png` | Navigation mark. |
| `png/moonlit-edge-1024.png`, `png/moonlit-edge-icon-192.png` | Moonlit Edge direction. |
| `png/moonrise-1800x1000.png` | Moonrise scene for social images and loading screens. |
| `png/bhabit-amber-crater.png` | Header lettering, amber with craters (1500×414, letters inset 29.5px). |
| `png/bhabit-moon-rock.png`, `png/bhabit-deep-space.png` | The two alternative letterings. |
| `png/moon-rabbit-silhouette-1024.png` | Raster original of the hover silhouette. |

## CSS and tokens

| File | What it is |
|---|---|
| `css/tokens.css` | `:root` tokens from the canvas, plus the colors and values added in this pass. |
| `css/tokens.json` | The same tokens as JSON (`base` and `designPass`). |
| `css/moon-theme.css` | Only the design-pass rules: lettering lockup, stars, moon glow, silhouette, rows and actions. |
| `css/mw-kit.css` | The complete canvas stylesheet, as published. |
