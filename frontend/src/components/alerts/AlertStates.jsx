import React from "react";

/** Calm, useful states. No marketing copy, no alarm language. */

export function AlertLoading({ label = "Loading…" }) {
  return <div className="mw-alerts-state">{label}</div>;
}

export function AlertEmpty({ title, detail }) {
  return (
    <div className="mw-alerts-state mw-alerts-state--empty">
      <p className="mw-alerts-state__title">{title}</p>
      {detail ? <p className="mw-alerts-state__detail">{detail}</p> : null}
    </div>
  );
}

export function AlertError({ message, onRetry }) {
  return (
    <div className="mw-alerts-state mw-alerts-state--error" role="status">
      <p className="mw-alerts-state__title">{message || "Something went wrong."}</p>
      {onRetry ? (
        <button type="button" className="mw-alert-btn" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

/**
 * Signed-out is an expected state, not a crash. No error styling, no retry
 * button that would just fail again.
 */
export function AlertSignedOut() {
  return (
    <div className="mw-alerts-state mw-alerts-state--signedout">
      <p className="mw-alerts-state__title">Sign in to use your own alerts</p>
      <p className="mw-alerts-state__detail">
        Your alerts are private to your account. The Market Feed tab stays
        available either way.
      </p>
    </div>
  );
}

/** Inline per-card message, used instead of toasts (no toast infra yet). */
export function InlineMessage({ tone = "error", children }) {
  if (!children) return null;
  return (
    <p className={`mw-alert-inline mw-alert-inline--${tone}`} role="status">
      {children}
    </p>
  );
}

export const NOT_ADVICE =
  "Alerts are informational only and are not financial advice.";
