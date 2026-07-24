// Feedback on an answer: Helpful / Not helpful / Incorrect data / Missing context,
// plus an optional note. Emits once so the parent can instrument answer_rated.
import { useState } from "react";
import PropTypes from "prop-types";
import { FEEDBACK_KIND, FEEDBACK_PRESENTATION } from "../askBhabitContract.js";
import { toneClass } from "./toneClass.js";

export default function FeedbackControls({ onRate }) {
  const [chosen, setChosen] = useState(null);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);

  const pick = (kind) => {
    setChosen(kind);
    onRate({ kind, note: note.trim() });
  };

  const sendNote = () => {
    if (!chosen) return;
    onRate({ kind: chosen, note: note.trim() });
    setSent(true);
  };

  return (
    <div className="abx-card">
      <p className="abx-card-title">Was this useful?</p>
      <div className="abx-feedback">
        {Object.values(FEEDBACK_KIND).map((kind) => {
          const p = FEEDBACK_PRESENTATION[kind];
          return (
            <button
              key={kind}
              type="button"
              className={`abx-feedback-btn ${toneClass(p.tone)}`}
              data-active={chosen === kind ? "1" : "0"}
              aria-pressed={chosen === kind}
              onClick={() => pick(kind)}
            >
              {p.label}
            </button>
          );
        })}
      </div>
      {chosen ? (
        <div className="abx-field" style={{ marginTop: 12, marginBottom: 0 }}>
          <label className="abx-label" htmlFor="abx-feedback-note">
            Add a note <span>(optional)</span>
          </label>
          <textarea
            id="abx-feedback-note"
            className="abx-textarea"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What was off, or what helped?"
          />
          <div className="abx-actions">
            <button type="button" className="abx-btn abx-btn-ghost" onClick={sendNote} disabled={sent}>
              {sent ? "Sent" : "Send note"}
            </button>
            {sent ? <span className="abx-feedback-thanks">Thanks — noted.</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

FeedbackControls.propTypes = {
  onRate: PropTypes.func.isRequired,
};
