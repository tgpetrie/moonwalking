## Purpose
This is the fast map. Run these searches in order so you don’t wander.
Goal: find the **canonical row hook** and the **micro-motion Framer Motion** implementation, then extend them to the other tables + banners.

Scope reminder:
- Include: 1m table, 3m gainers, 3m losers, top price-change banner items, bottom volume banner items
- Exclude: Intelligence Log / terminal panel

---

## 0) Sanity: what am I on?
```bash
git status -sb
git branch --show-current
```


⸻

1) Find the 1m table component (reference behavior)

1A) Locate the 1m component file

```bash
rg -n "GainersTable1Min|1Min|1m gainers|one minute|interval.?=.?1m|window.?=.?1m" frontend/src
rg -n "GainersTable1Min" -S frontend/src
```

1B) Confirm the row markup + class hooks

Once you find the 1m table file, search inside it (or just use rg):

```bash
rg -n "className=.*row|data-state|data-side|is-gain|is-loss|mw-row|bh-row|table-row" frontend/src
```

What you want to extract from 1m:
    •	the row wrapper element type (tr, div, etc.)
    •	the row classname(s)
    •	any gain/loss attributes (data-state="gain|loss", data-side, etc.)
    •	whether it uses motion.tr / motion.div or plain nodes

⸻

2) Find the 3m gainers + 3m losers components (missing behavior)

2A) Locate the 3m table files

```bash
rg -n "GainersTable(?!1Min)|LosersTable|3m gainers|3m losers|window.?=.?3m|interval.?=.?3m" -S frontend/src
```

2B) Compare row hooks between 1m and 3m

Search for row wrapper class usage:

```bash
rg -n "motion\.tr|motion\.div|motion\.li|<tr|<div|<li" frontend/src
rg -n "className=.*(row|table-row|mw-row|bh-row)|data-(state|side)" frontend/src
```

You are looking for:
    •	3m rows not using the same class/attrs as 1m
    •	3m rows not using motion wrapper at all (likely why micro motion isn’t showing)

⸻

3) Find the top banner items (should get glow + micro motion)

3A) Locate banner components

```bash
rg -n "TopBanner|Banner|Scroll|Ticker|ContinuousScrolling|Marquee|1h|hour" -S frontend/src
```

3B) Identify item row markup + class hooks

```bash
rg -n "banner-item|ticker-item|className=.*(item|row)|data-(state|side)" -S frontend/src
rg -n "motion\.div|motion\.li|animate=|variants=|transition=" -S frontend/src
```

Extract:
    •	the item wrapper element and classnames
    •	how gain/loss is represented (if at all)
    •	whether items already use Framer Motion

⸻

4) Find the bottom volume banner items (same rules)

4A) Locate volume banner file

```bash
rg -n "VolumeBanner|volume.*scroll|1h.*vol|vol.*banner|ContinuousScrollingBanner.*vol" -S frontend/src
```

4B) Identify item hook

```bash
rg -n "className=.*(item|row)|data-(state|side)|is-(gain|loss)" -S frontend/src
```


⸻

5) Find the global CSS that controls hover glow

5A) Where are row hover styles defined?

```bash
rg -n "hover.*glow|row-hover|::before|::after|mask-image|radial-gradient|mw-row|bh-row|table-row" -S frontend/src
rg -n "index\.css|globals\.css|app\.css" -S frontend/src
```

Open likely files:
    •	frontend/src/index.css
    •	frontend/src/styles/*.css (if present)

What you want:
    •	the selectors that currently power hover glow (working on 1m)
    •	confirmation that those selectors do not match 3m/banners

⸻

6) Find the micro-motion (Framer Motion) implementation

6A) Locate framer-motion imports

```bash
rg -n "from ['\"]framer-motion['\"]|framer-motion" -S frontend/src
```

6B) Locate variants + transitions used for row micro motion

```bash
rg -n "variants\s*=\s*\{|const\s+\w*Variants|animate\s*=\s*|initial\s*=\s*|transition\s*=\s*\{" -S frontend/src
rg -n "y:\s*|opacity:\s*|duration:\s*|repeat:\s*|repeatType:\s*|ease:" -S frontend/src
```

What you want:
    •	the tiny in-row movement (breathing) definition
    •	confirm it is applied only in 1m right now
    •	confirm it uses opacity + transform (y/x/scale) only

⸻

7) Define the canonical hook (do this before editing)

Once you’ve identified 1m’s working row selector, choose ONE canonical hook:

Preferred:
    •	.mw-row class
    •	plus data-state="gain|loss" (or data-side="gain|loss")

This canonical hook must be applied to:
    •	1m rows
    •	3m gainers rows
    •	3m losers rows
    •	top banner items
    •	bottom volume banner items

Not applied to:
    •	Intelligence Log rows/items

⸻

8) Guard rail: keep Intelligence Log excluded

8A) Find intelligence log component file(s)

```bash
rg -n "Intelligence|Anomaly|Alerts|Log|Terminal|Stream" -S frontend/src
```

8B) Confirm your canonical selectors won’t match it

If Intelligence Log uses .log-row or similar:
    •	do not add .mw-row to it
    •	do not wrap it in .mw-board (see below)

⸻

9) The clean containment trick (recommended)

To avoid accidental bleed:
    •	Add a single wrapper class to the dashboard area only: .mw-board
    •	Then scope all CSS and motion targeting under .mw-board

Search for the dashboard wrapper:

```bash
rg -n "board|dashboard|AppShell|Layout|MainContent" -S frontend/src
rg -n "className=.*(board|shell|wrap|container|main)" -S frontend/src/App*.jsx frontend/src/app*.jsx
```

You want:
    •	.mw-board wraps tables + both banners
    •	Intelligence Log sits outside .mw-board or inside but NOT using .mw-row

⸻

10) Minimal proof commands

After patch:

```bash
git diff --stat
./start_app.sh
```

In UI verify:
    •	Hover glow works on 3m gainers + 3m losers + both banners
    •	Micro motion is visible (subtle but undeniable) on 3m + both banners
    •	Intelligence Log unchanged

Double-run proof (optional but ideal):
    •	start
    •	Ctrl+C
    •	start again

⸻

11) If you get lost: shortest “map me” command

This prints the most relevant motion + row hooks fast:

```bash
rg -n "mw-row|bh-row|table-row|data-state|data-side|row-hover|::before|::after|framer-motion|motion\." -S frontend/src | head -n 200
```

 (See <attachments> above for file contents. You may not need to search or read the file again.)
