import { useState } from "react";
import "../styles/ask-codex.css";
import AskBhabitExperience from "../features/askBhabit/AskBhabitExperience.jsx";

export default function AskBhabitPanel() {
  const [open, setOpen] = useState(false);

  return (
    <div className="bh-ask-dock" data-open={open ? "1" : "0"}>
      <button
        type="button"
        className="bh-ask-btn"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title="Ask Bhabit"
      >
        <span className="bh-ask-btn-label">ASK BHABIT</span>
      </button>

      {open ? (
        <div className="bh-ask-panel bh-ask-panel-wide" role="dialog" aria-label="Ask Bhabit">
          <div className="bh-ask-head">
            <div className="bh-ask-title">ASK BHABIT</div>
            <span className="bh-ask-beta">LIVE</span>
            <button
              type="button"
              className="bh-ask-close"
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              x
            </button>
          </div>
          <div className="bh-ask-body bh-ask-body-embedded">
            <AskBhabitExperience mode="live" />
          </div>
        </div>
      ) : null}
    </div>
  );
}
