// Guided starter questions + an optional free-text box after them. The guided
// options carry the first-value flow; free text is allowed but never required.
import { useState } from "react";
import PropTypes from "prop-types";
import { GUIDED_QUESTIONS } from "../askBhabitContract.js";

export default function GuidedQuestions({ disabled, activeId, onAsk }) {
  const [freeText, setFreeText] = useState("");

  const submitFree = (e) => {
    e.preventDefault();
    const text = freeText.trim();
    if (!text) return;
    onAsk({ id: "free_text", label: text, freeText: text });
  };

  return (
    <div className="abx-card">
      <p className="abx-card-title">Ask about this position</p>
      <div className="abx-guided" role="group" aria-label="Guided questions">
        {GUIDED_QUESTIONS.map((q) => (
          <button
            key={q.id}
            type="button"
            className="abx-guided-btn"
            data-active={activeId === q.id ? "1" : "0"}
            disabled={disabled}
            onClick={() => onAsk({ id: q.id, label: q.label })}
          >
            {q.label}
          </button>
        ))}
      </div>

      <form className="abx-field" style={{ marginTop: 12, marginBottom: 0 }} onSubmit={submitFree}>
        <label className="abx-label" htmlFor="abx-freetext">
          Or ask your own <span>(optional)</span>
        </label>
        <textarea
          id="abx-freetext"
          className="abx-textarea"
          value={freeText}
          disabled={disabled}
          placeholder="e.g. Should I be worried about the funding flip?"
          onChange={(e) => setFreeText(e.target.value)}
        />
        <div className="abx-actions">
          <button type="submit" className="abx-btn" disabled={disabled || !freeText.trim()}>
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}

GuidedQuestions.propTypes = {
  disabled: PropTypes.bool,
  activeId: PropTypes.string,
  onAsk: PropTypes.func.isRequired,
};
