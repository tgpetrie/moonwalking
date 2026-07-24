// Optional thesis capture — under ten seconds, and fully skippable. This is NOT
// a journal: two short prompts, a horizon, and a few tags. Skipping is a
// first-class path (thesis omitted is a required UI state).
import { useState } from "react";
import PropTypes from "prop-types";
import { THESIS_TAGS, TIME_HORIZON, TIME_HORIZON_LABEL } from "../askBhabitContract.js";

export default function ThesisForm({ onSave, onSkip }) {
  const [reason, setReason] = useState("");
  const [invalidation, setInvalidation] = useState("");
  const [horizon, setHorizon] = useState(TIME_HORIZON.SWING);
  const [tags, setTags] = useState([]);

  const toggleTag = (tag) =>
    setTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));

  const save = (e) => {
    e.preventDefault();
    onSave({ reason: reason.trim(), invalidation: invalidation.trim(), horizon, tags });
  };

  return (
    <form className="abx-card" onSubmit={save} aria-label="Optional thesis">
      <p className="abx-card-title">Add a quick thesis <span style={{ opacity: 0.5 }}>· optional</span></p>

      <div className="abx-field">
        <label className="abx-label" htmlFor="abx-reason">Why did you enter?</label>
        <input id="abx-reason" className="abx-input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Ecosystem growth" />
      </div>
      <div className="abx-field">
        <label className="abx-label" htmlFor="abx-invalidation">What would make you reconsider?</label>
        <input id="abx-invalidation" className="abx-input" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} placeholder="Activity stalls" />
      </div>

      <div className="abx-field">
        <label className="abx-label" htmlFor="abx-horizon">Time horizon</label>
        <select id="abx-horizon" className="abx-select" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
          {Object.values(TIME_HORIZON).map((h) => (
            <option key={h} value={h}>{TIME_HORIZON_LABEL[h]}</option>
          ))}
        </select>
      </div>

      <div className="abx-field">
        <span className="abx-label">Tags <span>(optional)</span></span>
        <div className="abx-tagrow" role="group" aria-label="Thesis tags">
          {THESIS_TAGS.map((tag) => (
            <button
              key={tag}
              type="button"
              className="abx-tag"
              data-active={tags.includes(tag) ? "1" : "0"}
              aria-pressed={tags.includes(tag)}
              onClick={() => toggleTag(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      <div className="abx-actions">
        <button type="submit" className="abx-btn">Save thesis</button>
        <button type="button" className="abx-btn abx-btn-ghost" onClick={onSkip}>Skip for now</button>
      </div>
    </form>
  );
}

ThesisForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  onSkip: PropTypes.func.isRequired,
};
