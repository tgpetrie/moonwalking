import React, { useEffect, useState } from "react";
import QuickAlertBuilder from "./QuickAlertBuilder.jsx";
import {
  AlertEmpty,
  AlertError,
  AlertLoading,
  AlertSignedOut,
  InlineMessage,
  NOT_ADVICE,
} from "./AlertStates.jsx";
import { describeRule, repeatLabel, statusLabel, statusTone } from "./alertLabels.js";

/**
 * The user's own rules, plus the creation flow.
 *
 * Editing is intentionally absent in this pass: changing a threshold resets
 * arm state, pending confirmation, and cooldown, which is hard to explain in
 * a first UI. Delete and recreate is the honest path.
 *
 * Internal machinery (arm_cycle, fingerprint, armed, reset_pct,
 * percent_rearm_ratio) is never rendered.
 */
export default function ActiveRulesTab({
  rules,
  loading,
  error,
  authRequired,
  onLoad,
  onCreate,
  onSetStatus,
  onRemove,
  prefillSymbol = null,
  onPrefillConsumed = null,
}) {
  const [busyId, setBusyId] = useState(null);
  const [cardError, setCardError] = useState({});
  const [showBuilder, setShowBuilder] = useState(false);

  useEffect(() => {
    onLoad?.();
  }, [onLoad]);

  // A symbol handed over from a For You signal opens the builder prefilled —
  // creating a rule becomes one tap away from the intelligence that prompted it.
  useEffect(() => {
    if (prefillSymbol) setShowBuilder(true);
  }, [prefillSymbol]);

  if (authRequired) return <AlertSignedOut />;

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

  const body = () => {
    if (loading && rules.length === 0) return <AlertLoading label="Loading your alerts…" />;
    if (error) return <AlertError message={error} onRetry={() => onLoad?.({ force: true })} />;
    if (rules.length === 0) {
      return (
        <AlertEmpty
          title="You have no alerts yet"
          detail="Create one above, or enable a suggestion from the Recommended tab."
        />
      );
    }

    return (
      <div className="mw-alerts-list">
        {rules.map((rule) => {
          const paused = rule.status === "paused";
          const pending = rule.pending_since_ts != null;
          return (
            <article key={rule.id} className="mw-alert-card">
              <header className="mw-alert-card__head">
                <span className="mw-alert-card__symbol">{rule.symbol}</span>
                <span
                  className={`mw-alert-card__status mw-alert-card__status--${statusTone(
                    rule.status
                  )}`}
                >
                  {statusLabel(rule.status)}
                </span>
              </header>

              <p className="mw-alert-card__rule">{describeRule(rule)}</p>

              <p className="mw-alert-card__meta">
                {repeatLabel(rule.repeat_mode)}
                {pending ? " · Checking…" : ""}
                {rule.source === "recommended" ? " · From a suggestion" : ""}
              </p>

              <div className="mw-alert-card__actions">
                <button
                  type="button"
                  className="mw-alert-btn"
                  disabled={busyId === rule.id}
                  onClick={() =>
                    run(rule.id, () => onSetStatus(rule.id, paused ? "active" : "paused"))
                  }
                >
                  {paused ? "Resume" : "Pause"}
                </button>
                <button
                  type="button"
                  className="mw-alert-btn mw-alert-btn--quiet"
                  disabled={busyId === rule.id}
                  onClick={() => run(rule.id, () => onRemove(rule.id))}
                >
                  Delete
                </button>
              </div>

              <InlineMessage>{cardError[rule.id]}</InlineMessage>
            </article>
          );
        })}
        <p className="mw-alerts-footnote">{NOT_ADVICE}</p>
      </div>
    );
  };

  return (
    <div>
      <div className="mw-alerts-toolbar">
        <button
          type="button"
          className="mw-alert-btn mw-alert-btn--primary"
          onClick={() => setShowBuilder((v) => !v)}
          aria-expanded={showBuilder}
        >
          {showBuilder ? "Close" : "New alert"}
        </button>
      </div>

      {showBuilder ? (
        <QuickAlertBuilder
          key={prefillSymbol || 'blank'}
          defaultSymbol={prefillSymbol || ''}
          onCreate={onCreate}
          onCreated={() => {
            setShowBuilder(false);
            onPrefillConsumed?.();
          }}
        />
      ) : null}

      {body()}
    </div>
  );
}
