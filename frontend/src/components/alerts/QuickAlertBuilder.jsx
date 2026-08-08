import React, { useMemo, useState } from "react";
import { InlineMessage } from "./AlertStates.jsx";
import { DIRECTIONS, TRIGGER_TYPES, WINDOWS } from "./alertLabels.js";

/**
 * Natural-language rule builder.
 *
 *   Alert me when [BTC] [moves up] [5]% during [a rolling 24-hour period]
 *   Alert me when [BTC] [goes above] [$70,000]
 *
 * Only price_cross and percent_move; only 1h/4h/24h. The 7d option does not
 * exist in this component, so it cannot reach the DOM.
 *
 * Client-side validation exists to catch obvious mistakes early, but the
 * server remains the authority — its message is what the user sees on 400.
 */
export default function QuickAlertBuilder({ onCreate, onCreated, defaultSymbol = "" }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [triggerType, setTriggerType] = useState("percent_move");
  const [direction, setDirection] = useState("either");
  const [threshold, setThreshold] = useState("5");
  const [windowValue, setWindowValue] = useState("24h");
  const [repeatMode, setRepeatMode] = useState("once");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const isPercent = triggerType === "percent_move";
  const directions = DIRECTIONS[triggerType] || [];

  const onTriggerTypeChange = (next) => {
    setTriggerType(next);
    // Directions are not shared between trigger types; reset to a valid one.
    setDirection(next === "percent_move" ? "either" : "above");
    setThreshold(next === "percent_move" ? "5" : "");
    setError(null);
  };

  const clientError = useMemo(() => {
    if (!symbol.trim()) return "Choose a coin.";
    const n = Number(threshold);
    if (!Number.isFinite(n) || n <= 0) {
      return isPercent ? "Enter a percentage above zero." : "Enter a price above zero.";
    }
    if (isPercent && n > 100) return "Percentage must be 100 or less.";
    return null;
  }, [symbol, threshold, isPercent]);

  const submit = async (evt) => {
    evt.preventDefault();
    if (clientError) {
      setError(clientError);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const params = { direction, threshold: Number(threshold) };
      if (isPercent) params.window = windowValue;
      await onCreate({
        symbol: symbol.trim().toUpperCase(),
        trigger_type: triggerType,
        params,
        repeat_mode: repeatMode,
      });
      onCreated?.();
    } catch (err) {
      // Surface the server's own wording — it explains *why* precisely.
      setError(err?.message || "Could not create that alert.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="mw-alert-builder" onSubmit={submit}>
      <div className="mw-alert-sentence">
        <span className="mw-alert-sentence__text">Alert me when</span>

        <input
          type="text"
          className="mw-alert-input mw-alert-input--symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="BTC"
          aria-label="Coin"
          maxLength={12}
        />

        <select
          className="mw-alert-select"
          value={triggerType}
          onChange={(e) => onTriggerTypeChange(e.target.value)}
          aria-label="What to watch"
        >
          {TRIGGER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>

        <select
          className="mw-alert-select"
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          aria-label="Direction"
        >
          {directions.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>

        <span className="mw-alert-amount">
          {!isPercent ? <span className="mw-alert-affix">$</span> : null}
          <input
            type="number"
            className="mw-alert-input mw-alert-input--amount"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder={isPercent ? "5" : "70000"}
            aria-label={isPercent ? "Percentage" : "Price"}
            min="0"
            step="any"
            inputMode="decimal"
          />
          {isPercent ? <span className="mw-alert-affix">%</span> : null}
        </span>

        {isPercent ? (
          <>
            <span className="mw-alert-sentence__text">during</span>
            <select
              className="mw-alert-select"
              value={windowValue}
              onChange={(e) => setWindowValue(e.target.value)}
              aria-label="Time window"
            >
              {WINDOWS.map((w) => (
                <option key={w.value} value={w.value}>
                  {w.label}
                </option>
              ))}
            </select>
          </>
        ) : null}
      </div>

      <button
        type="button"
        className="mw-alert-disclosure"
        onClick={() => setShowAdvanced((v) => !v)}
        aria-expanded={showAdvanced}
      >
        {showAdvanced ? "Hide options" : "Customize"}
      </button>

      {showAdvanced ? (
        <div className="mw-alert-advanced">
          <label className="mw-alert-field">
            <span>How often</span>
            <select
              className="mw-alert-select"
              value={repeatMode}
              onChange={(e) => setRepeatMode(e.target.value)}
            >
              <option value="once">Notify once</option>
              <option value="recurring">Notify again after the market resets</option>
            </select>
          </label>
        </div>
      ) : null}

      <div className="mw-alert-builder__actions">
        <button
          type="submit"
          className="mw-alert-btn mw-alert-btn--primary"
          disabled={submitting}
        >
          {submitting ? "Creating…" : "Create alert"}
        </button>
      </div>

      <InlineMessage>{error}</InlineMessage>
    </form>
  );
}
