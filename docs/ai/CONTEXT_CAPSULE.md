# Context Capsule (live)
Now: Dashboard is entry; no loader demo. Backend computes 1m/3m deltas + 1h price/volume; bridge emits canonical events.
Recent UI: remove sentiment badge; show ticker only (trim "-USD"); ⓘ opens tabbed SymbolInfoPanel (Info/Volume/Trend) bottom-right.
Pitfalls: redirecting `frontend/index.html` breaks boot; guard arrays & numbers; path casing.
Where: `frontend/` • entry: `src/main.jsx` • tables: `src/components` • hooks: `src/hooks` • api: `src/lib`
