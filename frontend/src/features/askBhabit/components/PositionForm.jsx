// Manual position entry — completion under ~1 minute. Required: asset, quantity,
// and either entry price or total cost basis. Optional: acquisition date, note.
// Validation lives in the adapter so the same rules are unit-tested independently.
import { useState } from "react";
import PropTypes from "prop-types";
import { validatePositionDraft } from "../askBhabitAdapter.js";

const EMPTY = { asset: "", quantity: "", entryPrice: "", costBasis: "", acquiredAt: "", note: "" };

export default function PositionForm({ onSubmit, onCancel }) {
  const [draft, setDraft] = useState(EMPTY);
  const [touched, setTouched] = useState(false);

  const { valid, errors, normalized } = validatePositionDraft(draft);
  const set = (key) => (e) => setDraft((d) => ({ ...d, [key]: e.target.value }));
  const showError = (key) => (touched ? errors[key] : null);

  const submit = (e) => {
    e.preventDefault();
    setTouched(true);
    if (!valid) return;
    onSubmit(normalized, { costBasisEntered: draft.costBasis !== "" });
  };

  return (
    <form className="abx-card" onSubmit={submit} noValidate aria-label="Add a position">
      <p className="abx-card-title">Add your position</p>

      <div className="abx-row">
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-asset">Asset</label>
          <input
            id="abx-asset"
            className="abx-input"
            value={draft.asset}
            onChange={set("asset")}
            aria-invalid={Boolean(showError("asset"))}
            placeholder="SOL"
            autoComplete="off"
          />
          {showError("asset") ? <span className="abx-error-text">{errors.asset}</span> : null}
        </div>
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-qty">Quantity</label>
          <input
            id="abx-qty"
            className="abx-input"
            type="number"
            step="any"
            value={draft.quantity}
            onChange={set("quantity")}
            aria-invalid={Boolean(showError("quantity"))}
            placeholder="42"
          />
          {showError("quantity") ? <span className="abx-error-text">{errors.quantity}</span> : null}
        </div>
      </div>

      <div className="abx-row">
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-entry">Entry price</label>
          <input
            id="abx-entry"
            className="abx-input"
            type="number"
            step="any"
            value={draft.entryPrice}
            onChange={set("entryPrice")}
            aria-invalid={Boolean(showError("basis"))}
            placeholder="118.40"
          />
        </div>
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-cost">Total cost basis</label>
          <input
            id="abx-cost"
            className="abx-input"
            type="number"
            step="any"
            value={draft.costBasis}
            onChange={set("costBasis")}
            aria-invalid={Boolean(showError("basis"))}
            placeholder="4972.80"
          />
        </div>
      </div>
      {showError("basis") ? <span className="abx-error-text">{errors.basis}</span> : null}

      <div className="abx-row" style={{ marginTop: 8 }}>
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-date">
            Acquisition date <span>(optional)</span>
          </label>
          <input id="abx-date" className="abx-input" type="date" value={draft.acquiredAt} onChange={set("acquiredAt")} />
        </div>
        <div className="abx-field">
          <label className="abx-label" htmlFor="abx-note">
            Note <span>(optional)</span>
          </label>
          <input id="abx-note" className="abx-input" value={draft.note} onChange={set("note")} placeholder="Why now?" />
        </div>
      </div>

      <div className="abx-actions">
        <button type="submit" className="abx-btn">Save position</button>
        {onCancel ? (
          <button type="button" className="abx-btn abx-btn-ghost" onClick={onCancel}>Cancel</button>
        ) : null}
      </div>
    </form>
  );
}

PositionForm.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  onCancel: PropTypes.func,
};
