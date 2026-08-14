# Scorecard Redesign — Handoff

Branch: `codex/scorecard-redesign-compare`

## Pick up here

The redesign works and is honest about its data, but it is **not finished as a
visual design**. Open questions, in the order they matter:

1. **The visual language is still unsettled.** Cards → table → gauges → pie →
   bars, each rejected for a specific reason recorded below. Bars are the
   current default because they encode the right variable, not because the
   design is resolved.
2. **App-wide type hierarchy is broken at the root** — see Design-system
   findings. `h1`/`h2` are forced to 800-weight uppercase everywhere, so nothing
   can read as more important than anything else. This is the single highest
   leverage fix left and it needs a real type scale.
3. **The scorecard has nothing to show until the backend has run for an hour.**
   That is expected, not a bug; see "Empty state is not a bug".

The original scorecard is untouched. The redesign lives beside it so the two can
be opened side by side and judged against each other.

## Product split

- `SentimentPopupAdvanced` — the **live** decision surface. "What is this coin
  doing right now, do I act?"
- `ScorecardPage` / `ScorecardRedesignPage` — the **validation** surface. "When
  we said something in the past, were we right?"

The redesign must never read as a live call. Everything on it is past tense.

## Routes

| Route | Version | Data |
|---|---|---|
| `/scorecard` | Original | Public, sample until live data exists |
| `/scorecard-redesign` | Redesign | Public |
| `/scorecard-compare` | Both, side by side | Public |
| `/app/scorecard` | Original | Members, live |
| `/app/scorecard-redesign` | Redesign | Members, live |
| `/app/scorecard-compare` | Both, side by side | Members, live |
| `/scorecard?variant=redesign` | Redesign | Query-param override |

A version switcher (Original · Redesign · Side by side) renders above all of
them from `ScorecardCompare.jsx`, so neither page knows the other exists.

## Files

| File | Role |
|---|---|
| `frontend/src/components/ScorecardPage.jsx` | **Baseline — do not edit.** Zero diff on this branch. |
| `frontend/src/styles/scorecard.css` | Baseline styles. Also untouched, and deliberately excluded from the radius sweep. |
| `frontend/src/components/ScorecardRedesignPage.jsx` | The redesign. |
| `frontend/src/styles/scorecard-redesign.css` | `.scr-*` namespace so both pages can render at once. |
| `frontend/src/components/ScorecardCompare.jsx` | Version switcher + side-by-side view. |

## Page structure

1. **Hero** — coin as the page heading, provenance chip, compact coin picker,
   three headline numbers, collapsed scoring rule. No prose.
2. **Signal history** — how often each signal category was right.
3. **Board history** — whether landing on a board meant anything, versus
   similar coins that never appeared.
4. **`<COIN>` history** — the same scoring narrowed to one asset.
5. **Internal diagnostics** — collapsed. Grouped totals and scoring params.

## Chart treatments

Switchable at runtime via the `Chart` control. **Default is `bars`.**

- `bars` — one bar per category, length = accuracy, with the overall average
  marked. This is the default because the question on this page is "was it
  right?", which is a rate.
- `split` ("Volume mix") — one sectioned donut per zone. **It encodes share of
  calls made, not accuracy**, and is captioned as such. Accuracy rates across
  categories are independent and do not sum to 100%, so a pie cannot show them.
  When one category dominates, the pie degenerates to a single 100% blob that
  answers nothing — which is exactly what happened in testing.

  The legend's headline number is the **slice share**, so legend and chart
  always agree. An earlier version printed accuracy there while sizing slices by
  volume; two unrelated numbers in one figure read as simply broken. Accuracy
  now sits on the second line, spelled out as "worked N% of the time". Avoid
  bare labels like "N% right" — it is never clear what is being counted.
- `gauges` — a donut per category.

Depth on the donut is gradient and shadow only. A real perspective tilt
foreshortens the far segments and makes equal shares look unequal.

## Collection progress instead of empty charts

When nothing has finished grading, the zone shows `CollectingPanel` — a
progress bar with "N of M graded" and an explanation — rather than an empty
chart. An empty chart implies we measured and found nothing; the truth is that
measurement is still running. Progress comes from
`GET /api/signals/outcomes/status` (`{total, complete, collecting,
horizon_minutes}`).

### Why not cards

Cards were tried first and read as three competing verdicts on the selected
coin — "Strong Buy 62%" beside "Caution 18%" looks like conflicting advice. A
table was tried next and read as a spreadsheet. A single chart with coloured
regions reads as one comparison, which is what it is. No explanatory sentence
fixed the card version; the structure was the problem.

## Data provenance

`resolveSource()` returns one of three states, and they must never be confused:

- **Live data** — measured from real recorded outcomes.
- **Preview data** — a fixed sample so the public page is explorable.
- **Demo data** — the server returned illustrative numbers.

The chip carries the label; the full explanation is a `title` tooltip so it
costs no vertical space. A preview page keeps its sample — and its label — until
live data actually has content, so it can never show live numbers under a
"preview" chip.

## Running it locally

Backend (required, or the whole app shows OFFLINE and flashes):

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install flask flask-cors flask-socketio flask-talisman flask-limiter requests python-dotenv numpy pandas psutil PyYAML websocket-client feedparser vaderSentiment
```

```bash
cd backend && ../.venv/Scripts/python.exe app.py --port 5003 --host 127.0.0.1
```

`backend/requirements.txt` pulls torch and transformers, which are multi-GB and
not needed to boot the data endpoints. The list above is sufficient.

Frontend — **set `VITE_PORT`, do not use `--port`**:

```bash
cd frontend && VITE_PORT=5199 npm run dev
```

`vite.config.js` pins `hmr.port` to `VITE_PORT || 5173`. Passing `--port` moves
the server but leaves the HMR socket on 5173, which fails to connect and makes
the page reload in a loop. That is the "flashing" symptom.

### Working on another machine, without the backend

The public routes fall back to a fixed sample when no live data exists, so the
UI is fully explorable with only the frontend running:

```bash
cd frontend && npm install && VITE_PORT=5199 npm run dev
```

Then open `/scorecard-compare`. The chip reads **Preview data** and stays that
way until a backend actually returns graded outcomes — so you can never mistake
the sample for real results. Design and layout work needs nothing else.

## Empty state is not a bug

A signal is only scored once its full 60-minute window closes, so
`total_graded` stays 0 for the first hour after the backend starts and the
Signal history zone correctly shows its empty message. Boards fill much sooner.

## Design-system findings

Fixed on this branch:

- **Radius scale.** `--radius-base` in `index.css` drives `--r-1/2/3`. Every
  stylesheet except `scorecard.css` now uses it. Set `--radius-base: 0` for hard
  corners. All `999px` pills are gone.
- **Button size scale.** `.mw-button` had exactly one size, so a header auth
  link and a hero CTA rendered identically. Added `.mw-button--sm`.
- **`.mw-button--sm` was defined twice**, ~950 lines apart, the later one
  silently winning. Merged.
- **No `border-box` on buttons** — `min-height: 32px` rendered at 50px because
  padding and borders sat outside it.
- **`#root` is `display: flex`**, so the app shell shrink-wrapped to its content
  (811px inside a 1265px viewport) and squeezed every grid. Fixed with
  `#root > * { flex: 1 1 auto; min-width: 0 }`.

Still open, deliberately not changed — it alters every page's look:

- `.mw-app h1, .mw-app h2 { font-weight: 800; text-transform: uppercase }`
  forces every heading in the app to maximum weight and uppercase. Combined with
  a single button size, nothing can read as more important than anything else.
  This is the root of the hierarchy problem and wants a real type scale.

Also open:

- The demo payload is duplicated between the two pages, deliberately, to keep
  the baseline byte-identical. Collapse it once a winner is picked.
- The 21% overall baseline makes most categories read "well ahead of average".
  A coin-flip or market-drift baseline would be more informative.

## Tests

```bash
cd frontend && npm run verify   # build + 455 tests
```

`ScorecardRedesignPage.test.jsx` and `ScorecardCompare.test.jsx` cover the
redesign. The baseline's own tests are unchanged.
