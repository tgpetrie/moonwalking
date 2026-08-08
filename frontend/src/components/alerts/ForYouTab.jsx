import React, { useEffect, useMemo, useState } from "react";
import { useData } from "../../context/DataContext";
import { useWatchlist } from "../../context/WatchlistContext.jsx";
import {
  AlertEmpty,
  AlertError,
  AlertLoading,
  InlineMessage,
  NOT_ADVICE,
} from "./AlertStates.jsx";
import { timeAgo } from "./alertLabels.js";
import useHoldingSymbols from "./useHoldingSymbols.js";
import {
  buildForYouStream,
  holdingSymbolsFrom,
  KINDS,
  REASON_LABELS,
} from "./intelligenceEvents.js";

const KIND_LABELS = {
  [KINDS.YOUR_ALERT]: "Your alert",
  [KINDS.SUGGESTION]: "Suggested",
  [KINDS.MARKET]: "Market signal",
};

/**
 * "For You" — one ranked stream answering the product's founding question:
 * what is happening across the coins I hold, watch, or track, without me
 * having to know what to ask.
 *
 * Merges three existing sources (no new backend):
 *  - your fired alert events   (alert history, last 48h)
 *  - pending suggestions       (inline, enable/dismiss right here)
 *  - market signals            (legacy feed, filtered to personally relevant coins)
 *
 * Every row is actionable: Details opens the coin popup (where Chart Read
 * already lives), Set alert prefills the builder — rules as an action attached
 * to intelligence, not a destination you must seek out.
 */
export default function ForYouTab({
  events,
  recommendations,
  rules,
  loading,
  errors,
  authRequired,
  onLoad,
  onAccept,
  onDismiss,
  onOpenCoinSentiment = null,
  onSetAlertFor = null,
}) {
  const [busyId, setBusyId] = useState(null);
  const [cardError, setCardError] = useState({});

  useEffect(() => {
    onLoad?.();
  }, [onLoad]);

  // Context access is guarded so the tab renders (market-only or empty)
  // even outside providers — e.g. in isolation tests or future embeds.
  // The hook call itself is unconditional; only its missing-provider throw
  // is absorbed, so hook ordering rules are respected.
  const data = useData() || {};
  let watchlistCtx = {};
  try {
    watchlistCtx = useWatchlist() || {};
  } catch {
    watchlistCtx = {};
  }
  const watchHas = typeof watchlistCtx.has === "function" ? watchlistCtx.has : () => false;

  const marketAlerts = useMemo(() => {
    const active = Array.isArray(data.activeAlerts) ? data.activeAlerts : [];
    const recent = Array.isArray(data.alertsRecent) ? data.alertsRecent : [];
    return [...active, ...recent];
  }, [data.activeAlerts, data.alertsRecent]);

  // Real portfolio holdings (existing portfolio API, lazily fetched, errors
  // swallowed) merged with the basis-derived proxy. The proxy costs nothing
  // and still covers users whose portfolio call fails but who accepted a
  // portfolio-based suggestion. If both are empty, watchlist and rule
  // relevance carry the stream — holdings are additive, never a prerequisite.
  const portfolioHoldings = useHoldingSymbols({ enabled: !authRequired });
  const holdings = useMemo(() => {
    const merged = new Set(portfolioHoldings);
    for (const sym of holdingSymbolsFrom({ recommendations, rules })) merged.add(sym);
    return merged;
  }, [portfolioHoldings, recommendations, rules]);
  const ruleSymbols = useMemo(
    () => new Set((rules || []).map((r) => String(r.symbol || "").toUpperCase())),
    [rules]
  );

  const stream = useMemo(
    () =>
      buildForYouStream({
        userEvents: authRequired ? [] : events,
        recommendations: authRequired ? [] : recommendations,
        marketAlerts,
        isHolding: (s) => holdings.has(s),
        isWatchlisted: (s) => {
          try {
            return Boolean(watchHas(s));
          } catch {
            return false;
          }
        },
        hasRuleFor: (s) => ruleSymbols.has(s),
      }),
    [events, recommendations, marketAlerts, holdings, ruleSymbols, watchHas, authRequired]
  );

  const anyLoading = loading.recs || loading.events || loading.rules;
  const firstError = errors.recs || errors.events || errors.rules;

  if (anyLoading && stream.length === 0 && !authRequired) {
    return <AlertLoading label="Gathering what matters for you…" />;
  }

  if (stream.length === 0) {
    if (firstError) {
      return <AlertError message={firstError} onRetry={() => onLoad?.({ force: true })} />;
    }
    return (
      <AlertEmpty
        title="Nothing needs your attention right now"
        detail={
          authRequired
            ? "Sign in and add coins to your portfolio or watchlist, and relevant signals will appear here."
            : "Signals about coins you hold, watch, or track will appear here as they happen."
        }
      />
    );
  }

  const run = async (id, fn) => {
    setBusyId(id);
    setCardError((prev) => ({ ...prev, [id]: null }));
    try {
      await fn();
    } catch (err) {
      setCardError((prev) => ({ ...prev, [id]: err?.message || "That didn't work." }));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mw-alerts-list">
      {authRequired ? (
        <p className="mw-foryou-note">
          Sign in to see your own alerts and suggestions here too.
        </p>
      ) : null}

      {stream.map((item) => (
        // One shared card component, but each kind keeps its own visual
        // semantics (accent + label): a fired rule of yours, a suggestion
        // awaiting consent, and an ambient market signal mean different
        // things and must never blur together.
        <article
          key={item.id}
          className={`mw-alert-card mw-alert-card--${item.kind}`}
        >
          <header className="mw-alert-card__head">
            <span className="mw-alert-card__symbol">
              {item.symbol}
              <span className={`mw-alert-kind mw-alert-kind--${item.kind}`}>
                {KIND_LABELS[item.kind]}
              </span>
            </span>
            <span className="mw-alert-card__badge">
              {/* A fired alert's reason is self-evident from its kind chip —
                  repeating "You track this" would be noise. Market items and
                  suggestions carry their admission reason explicitly. */}
              {item.kind === KINDS.YOUR_ALERT ? "" : REASON_LABELS[item.reason] || ""}
              {item.ts
                ? `${item.kind === KINDS.YOUR_ALERT ? "" : " · "}${timeAgo(item.ts / 1000)}`
                : ""}
            </span>
          </header>

          <p className="mw-alert-card__rule">{item.headline}</p>
          {item.detail ? (
            <p className="mw-alert-card__explanation">{item.detail}</p>
          ) : null}

          {item.kind === KINDS.SUGGESTION ? (
            <div className="mw-alert-card__actions">
              <button
                type="button"
                className="mw-alert-btn mw-alert-btn--primary"
                disabled={busyId === item.raw.id}
                onClick={() => run(item.raw.id, () => onAccept(item.raw.id))}
              >
                {busyId === item.raw.id ? "Working…" : "Enable"}
              </button>
              <button
                type="button"
                className="mw-alert-btn"
                disabled={busyId === item.raw.id}
                onClick={() => run(item.raw.id, () => onDismiss(item.raw.id))}
              >
                Dismiss
              </button>
            </div>
          ) : (
            <div className="mw-alert-card__actions">
              {onOpenCoinSentiment ? (
                <button
                  type="button"
                  className="mw-alert-btn"
                  onClick={() => onOpenCoinSentiment(item.symbol)}
                >
                  Details
                </button>
              ) : null}
              {item.kind === KINDS.MARKET && onSetAlertFor ? (
                <button
                  type="button"
                  className="mw-alert-btn"
                  onClick={() => onSetAlertFor(item.symbol)}
                >
                  Set alert
                </button>
              ) : null}
            </div>
          )}

          <InlineMessage>{cardError[item.raw?.id]}</InlineMessage>
        </article>
      ))}
      <p className="mw-alerts-footnote">{NOT_ADVICE}</p>
    </div>
  );
}
