import { useMemo, useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { baselineOrNull } from "../utils/num.js";
import "./ui/skeleton.css";

// Reordering mode presets for 1-minute gainers table
// smooth: Default, balanced feel — fast enough to catch rockets, stable enough to avoid twitchy noise
// predator: Optional aggressive mode — tighter timing for traders who want immediate response
const PRESETS = {
  smooth: {
    alpha: 0.30,         // EMA smoothing coefficient (lower = smoother, less reactive to spikes)
    commitMs: 420,       // How often we allow UI reorders (ms)
    minStayMs: 2200,     // Min time a row stays visible once shown (prevents rapid churn)
    swapMargin: 0.18,    // Challenger must beat incumbent by this % to swap positions
    bubblePasses: 2,     // Number of bubble sort passes for hysteresis reordering
    vanishGraceMs: 1600, // Keep recently-seen coins briefly if they drop out of feed
    bufferRows: 8,       // Extra rows beyond visible to reduce cutoff thrashing
    spring: { type: "spring", stiffness: 520, damping: 40, mass: 0.9 },
  },
  predator: {
    alpha: 0.55,         // More reactive to raw changes
    commitMs: 320,       // Much faster commits
    minStayMs: 900,      // Shorter locks
    swapMargin: 0.08,    // Easier to swap positions
    bubblePasses: 4,     // More aggressive bubble passes
    vanishGraceMs: 800,  // Shorter grace period
    bufferRows: 6,       // Tighter buffer
    spring: { type: "spring", stiffness: 760, damping: 34, mass: 0.75 },
  },
};

// Read mode from localStorage: smooth (default) or predator
// Set via: localStorage.setItem("mw_1m_mode", "predator"); location.reload();
function getModePreset() {
  try {
    if (typeof window === "undefined" || !window.localStorage) return { mode: "smooth", ...PRESETS.smooth };
    const mode = (window.localStorage.getItem("mw_1m_mode") || "smooth").toLowerCase();
    return PRESETS[mode] ? { mode, ...PRESETS[mode] } : { mode: "smooth", ...PRESETS.smooth };
  } catch {
    return { mode: "smooth", ...PRESETS.smooth };
  }
}

const PRESET = getModePreset();
const { alpha: EMA_ALPHA, commitMs: COMMIT_MS, minStayMs: MIN_STAY_MS, swapMargin: SWAP_MARGIN, bubblePasses: BUBBLE_PASSES, vanishGraceMs: VANISH_GRACE_MS, bufferRows: BUFFER_ROWS, spring: SPRING_CONFIG } = PRESET;

const SkeletonGrid1m = ({ rows = 4 }) => {
  return (
    <div className="bh-skel-grid bh-skel-grid--1m" role="status" aria-label="Loading 1-minute movers">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bh-skel-row">
          <div className="bh-skel bh-skel-chip" />
          <div className="bh-skel bh-skel-line" />
          <div className="bh-skel bh-skel-pill" />
          <div className="bh-skel bh-skel-icon" />
        </div>
      ))}
    </div>
  );
};

const getRowIdentity = (row = {}) => {
  if (row?.product_id) return String(row.product_id);
  if (row?.symbol) return String(row.symbol);
  return null;
};

const buildRowKey = (row) => {
  const base = getRowIdentity(row);
  if (base) return String(base);
  const alt = row?.ticker ?? row?.base ?? row?.rank;
  return alt ? String(alt) : undefined;
};

const pct1mOf = (row) => {
  const raw =
    row?.change_1m ??
    row?.price_change_percentage_1min ??
    row?.pct_change ??
    row?.pct ??
    row?.changePct ??
    0;

  const n = typeof raw === "string" ? Number(String(raw).replace(/[%+]/g, "")) : Number(raw);
  return Number.isFinite(n) ? n : 0;
};

const priceOf = (row) => {
  const n = Number(row?.current_price ?? row?.price ?? row?.current ?? 0);
  return Number.isFinite(n) ? n : 0;
};

const buildSig = (rows = []) =>
  rows
    .map((row) => {
      const id = getRowIdentity(row) || row?.ticker || row?.base || "";
      const pct = pct1mOf(row);
      const price = priceOf(row);
      return `${id}:${pct.toFixed(4)}:${price.toFixed(8)}`;
    })
    .join("|");
export default function GainersTable1Min({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading } = useDataFeed();

  // Use props if provided, otherwise fall back to hook data
  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  const gainers1m = useMemo(() => {
    const list = Array.isArray(tokensProp)
      ? tokensProp
      : (() => {
          const src = data?.gainers_1m;
          if (Array.isArray(src)) return src;
          if (src && Array.isArray(src.data)) return src.data;
          return [];
        })();

    const sorted = list
      .map((row) => {
        const symbol = row?.symbol ?? row?.ticker ?? row?.base ?? row?.product_id ?? "";
        const changeRaw =
          row?.change_1m ??
          row?.price_change_percentage_1min ??
          row?.pct_change ??
          row?.pct ??
          row?.changePct ??
          0;
        const change = Number(changeRaw);
        const baselineOrNullPrev = baselineOrNull(
          row?.previous_price_1m ??
            row?.price_1m_ago ??
            row?.previous_price ??
            row?.prev_price ??
            row?.initial_price_1min ??
            null
        );

        return {
          ...row,
          symbol: symbol || row?.symbol,
          change_1m: Number.isFinite(change) ? change : 0,
          previous_price_1m: baselineOrNullPrev,
          current_price: row?.current_price ?? row?.price ?? row?.current,
        };
      })
      .filter((r) => Number(r.change_1m) > 0)
      .sort((a, b) => Number(b.change_1m) - Number(a.change_1m));

    const seen = new Set();
    const deduped = [];
    sorted.forEach((row) => {
      const ident = getRowIdentity(row);
      if (!ident) {
        deduped.push(row);
        return;
      }
      const key = String(ident).toUpperCase();
      if (seen.has(key)) return;
      seen.add(key);
      deduped.push(row);
    });

    return deduped;
  }, [data, tokensProp]);

  const MAX_ROWS_PER_COLUMN = 4;
  const MAX_VISIBLE_COLLAPSED = 8;
  const MAX_VISIBLE_EXPANDED = 16;

  const [expanded, setExpanded] = useState(false);
  const [displayRows, setDisplayRows] = useState([]);
  // Desired candidates snapshot (sorted by score); committed display updates on COMMIT_MS cadence
  const targetRef = useRef([]);        // desired candidates (sorted)
  const targetSigRef = useRef("");     // signature of desired candidates
  const currentSigRef = useRef("");    // signature of last committed displayRows

  // Per-symbol stabilization meta:
  // ema score, last seen, and min-stay window once shown
  const metaRef = useRef(new Map());

  // Keep a live ref so the commit loop reads the latest displayRows without stale closures
  const displayRef = useRef([]);

  const lastValueRef = useRef(new Map());

  useEffect(() => {
    displayRef.current = displayRows;
  }, [displayRows]);

  const filteredRows = useMemo(
    () =>
      (gainers1m || [])
        .filter(Boolean)
        .filter((row) => row.symbol || row.product_id),
    [gainers1m]
  );
  const maxVisible = expanded ? MAX_VISIBLE_EXPANDED : MAX_VISIBLE_COLLAPSED;

  // Build a stabilized, scored candidate list whenever input rows change.
  // We compute EMA per symbol and sort by EMA score.
  // We keep a BUFFER beyond visible so the cutoff doesn't thrash.
  // Vanish grace: keep recently-visible coins briefly even if they drop out.
  useEffect(() => {
    const now = Date.now();
    const meta = metaRef.current;

    const PRUNE_AFTER_MS = 2 * 60 * 1000;
    for (const [rid, m] of meta.entries()) {
      if (!m?.lastSeenAt) continue;
      if (now - m.lastSeenAt > PRUNE_AFTER_MS) meta.delete(rid);
    }

    // Build scored list from current feed
    const feedMap = new Map();
    const scored = (filteredRows || [])
      .map((row) => {
        const id = getRowIdentity(row);
        const pctNow = pct1mOf(row);

        if (id) {
          feedMap.set(id, row);
          const prev = meta.get(id) || {};
          const prevEma = Number.isFinite(prev.ema) ? prev.ema : pctNow;
          const ema = prevEma * (1 - EMA_ALPHA) + pctNow * EMA_ALPHA;

          meta.set(id, {
            ...prev,
            ema,
            lastPct: pctNow,
            lastSeenAt: now,
          });

          return { ...row, __score: ema };
        }

        return { ...row, __score: pctNow };
      })
      .filter((r) => pct1mOf(r) > 0)
      .sort((a, b) => Number(b.__score) - Number(a.__score));

    // Vanish grace: include recently-visible coins that dropped out temporarily
    const currentVisible = new Set((displayRef.current || []).map(r => getRowIdentity(r)).filter(Boolean));
    const graceCandidates = [];

    for (const rid of currentVisible) {
      if (feedMap.has(rid)) continue; // Already in scored list
      const m = meta.get(rid);
      if (!m || !m.lastSeenAt) continue;
      if (now - m.lastSeenAt > VANISH_GRACE_MS) continue;

      // Inject with decayed score
      const decayedScore = (m.ema || 0) * 0.92;
      if (decayedScore > 0) {
        // Reconstruct row from meta (minimal proxy)
        graceCandidates.push({
          symbol: rid,
          product_id: rid,
          change_1m: m.lastPct || 0,
          current_price: 0, // Stale data marker
          __score: decayedScore,
          __grace: true, // Mark as grace period entry
        });
      }
    }

    const allCandidates = [...scored, ...graceCandidates]
      .sort((a, b) => Number(b.__score) - Number(a.__score));

    const desired = allCandidates.slice(0, maxVisible + BUFFER_ROWS);

    targetRef.current = desired;
    targetSigRef.current = buildSig(desired);

    // Optional debug logging
    try {
      if (localStorage.getItem("mw_debug_1m") === "1") {
        console.log(`[1m] mode=${PRESET.mode} scored=${scored.length} grace=${graceCandidates.length} desired=${desired.length}`);
      }
    } catch {}

    // First paint: commit immediately so UI doesn't stay empty
    if (!displayRef.current.length && desired.length) {
      const first = desired.slice(0, maxVisible);
      currentSigRef.current = buildSig(first);
      setDisplayRows(first);
    }
  }, [filteredRows, maxVisible]);

  // Commit loop: merges desired list with current display using:
  // - min-stay window (MIN_STAY_MS)
  // - hysteresis swap margin (SWAP_MARGIN)
  // - stable merge order (reduces jumpiness)
  // Runs on COMMIT_MS cadence.
  useEffect(() => {
    const id = setInterval(() => {
      const desired = Array.isArray(targetRef.current) ? targetRef.current : [];
      if (!desired.length) return;

      const now = Date.now();
      const meta = metaRef.current;

      const desiredMap = new Map();
      const desiredIds = [];
      for (const r of desired) {
        const rid = getRowIdentity(r);
        if (!rid) continue;
        desiredMap.set(rid, r);
        desiredIds.push(rid);
      }

      const prevRows = Array.isArray(displayRef.current) ? displayRef.current : [];
      const prevIds = prevRows.map((r) => getRowIdentity(r)).filter(Boolean);
      const prevSet = new Set(prevIds);

      const isLocked = (rid) => {
        const m = meta.get(rid);
        return m && Number.isFinite(m.minStayUntil) && m.minStayUntil > now;
      };

      // Merge ordering: keep current on-screen order where possible, append new candidates
      const mergedIds = [
        ...prevIds.filter((rid) => desiredMap.has(rid)),     // keep existing ordering
        ...desiredIds.filter((rid) => !prevSet.has(rid)),    // add new entrants
      ];

      const nextIds = [];
      const nextSet = new Set();

      const pushId = (rid) => {
        if (!rid || nextSet.has(rid)) return;
        const row = desiredMap.get(rid);
        if (!row) return;
        nextIds.push(rid);
        nextSet.add(rid);

        // When a coin becomes visible, give it a min-stay lease
        const m = meta.get(rid) || {};
        if (!Number.isFinite(m.minStayUntil) || m.minStayUntil < now) {
          meta.set(rid, { ...m, minStayUntil: now + MIN_STAY_MS });
        }
      };

      // Step 0: include locked rows first
      for (const rid of prevIds) {
        if (nextIds.length >= maxVisible) break;
        if (!isLocked(rid)) continue;
        if (!desiredMap.has(rid)) continue;
        pushId(rid);
      }

      // Step A: keep what we can from merged order (stable feel)
      for (const rid of mergedIds) {
        if (nextIds.length >= maxVisible) break;
        pushId(rid);
      }

      // Step B: if we still have room, fill with top desired ids
      if (nextIds.length < maxVisible) {
        for (const rid of desiredIds) {
          if (nextIds.length >= maxVisible) break;
          pushId(rid);
        }
      }

      let nextRows = nextIds.map((rid) => desiredMap.get(rid)).filter(Boolean);

      // Hysteresis re-order pass (bounded bubble)
      // Allows rockets to climb quickly without re-sorting every tick
      const score = (r) => Number(r?.__score ?? pct1mOf(r));
      for (let pass = 0; pass < BUBBLE_PASSES; pass++) {
        let swapped = false;
        for (let i = 0; i < nextRows.length - 1; i++) {
          const a = nextRows[i];
          const b = nextRows[i + 1];
          if (!a || !b) continue;
          const sa = score(a);
          const sb = score(b);
          if (sb - sa > SWAP_MARGIN) {
            nextRows[i] = b;
            nextRows[i + 1] = a;
            swapped = true;
          }
        }
        if (!swapped) break;
      }

      // Optional debug: log top 5 after reorder
      try {
        if (localStorage.getItem("mw_debug_1m") === "1" && nextRows.length > 0) {
          const top5 = nextRows.slice(0, 5).map(r => `${getRowIdentity(r)}:${score(r).toFixed(2)}`).join(' ');
          console.log(`[1m] commit: ${top5}`);
        }
      } catch {}

      const nextSig = buildSig(nextRows);
      if (nextSig === currentSigRef.current) return;

      currentSigRef.current = nextSig;
      setDisplayRows(nextRows);
    }, COMMIT_MS);

    return () => clearInterval(id);
  }, [maxVisible]);

  const rowsWithPulse = useMemo(() => {
    const map = lastValueRef.current;
    return displayRows.map((row) => {
      const key = getRowIdentity(row);
      const price = priceOf(row);
      const pct = pct1mOf(row);
      const prev = key ? map.get(key) : null;
      const priceChanged = prev ? prev.price !== price : false;
      const pctChanged = prev ? prev.pct !== pct : false;
      if (key) {
        map.set(key, { price, pct });
      }
      return { row, priceChanged, pctChanged };
    });
  }, [displayRows]);
  const isSingleColumn = displayRows.length > 0 && displayRows.length <= MAX_ROWS_PER_COLUMN;
  const skeletonSingle = filteredRows.length <= MAX_ROWS_PER_COLUMN;

  const hasData = displayRows.length > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="panel-row--1m panel-row--grid-skeleton">
          <SkeletonGrid1m rows={4} cols={4} />
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className={`panel-row--1m ${isSingleColumn ? "panel-row--single" : ""}`}>
          <div className="bh-table">
            <div className="token-row token-row--empty">
              <div style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                No 1-minute movers to show right now.
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const leftLimit = displayRows.length > MAX_VISIBLE_COLLAPSED ? 8 : 4;
  const leftColumn = rowsWithPulse.slice(0, leftLimit);
  const rightColumn = rowsWithPulse.slice(leftLimit, leftLimit * 2);
  const hasSecondColumn = rightColumn.length > 0;
  const density = hasSecondColumn ? "normal" : "tight";

  return (
    <div className="gainers-table">
      <div className={`panel-row--1m ${isSingleColumn ? "panel-row--single" : ""}`}>
        <div className="bh-table">
          <AnimatePresence initial={false} mode="popLayout">
            {leftColumn.map(({ row: token, priceChanged, pctChanged }, index) => {
              const rowKey = buildRowKey(token);
              return (
                <motion.div
                  key={rowKey}
                  layout
                  layoutId={rowKey}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={SPRING_CONFIG}
                >
                  <TokenRowUnified
                    token={token}
                    rank={index + 1}
                    changeField="change_1m"
                    side="gainer"
                    renderAs="div"
                    onInfo={onInfo}
                    onToggleWatchlist={onToggleWatchlist}
                    isWatchlisted={watchlist.includes(token.symbol)}
                    density={density}
                    pulsePrice={priceChanged}
                    pulsePct={pctChanged}
                    pulseDelayMs={index * 18}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {hasSecondColumn && (
          <div className="bh-table">
            <AnimatePresence initial={false} mode="popLayout">
              {rightColumn.map(({ row: token, priceChanged, pctChanged }, index) => {
                const absoluteIndex = leftLimit + index;
                const rowKey = buildRowKey(token);
                return (
                <motion.div
                  key={rowKey}
                  layout
                  layoutId={rowKey}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={SPRING_CONFIG}
                >
                    <TokenRowUnified
                      token={token}
                      rank={absoluteIndex + 1}
                      changeField="change_1m"
                      side="gainer"
                      renderAs="div"
                      onInfo={onInfo}
                      onToggleWatchlist={onToggleWatchlist}
                      isWatchlisted={watchlist.includes(token.symbol)}
                      density={density}
                      pulsePrice={priceChanged}
                      pulsePct={pctChanged}
                      pulseDelayMs={absoluteIndex * 18}
                    />
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
      {filteredRows.length > MAX_VISIBLE_COLLAPSED && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded
              ? "Show less"
              : `Show more (${Math.min(filteredRows.length, MAX_VISIBLE_EXPANDED) - MAX_VISIBLE_COLLAPSED} more)`}
          </button>
        </div>
      )}
    </div>
  );
}
