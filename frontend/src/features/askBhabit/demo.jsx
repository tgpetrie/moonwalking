// Isolated preview harness for the Ask Bhabit feature. Not part of the app
// bundle — served only via /askBhabit.html during development.
import React from "react";
import ReactDOM from "react-dom/client";
import AskBhabitExperience from "./AskBhabitExperience.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <div style={{ minHeight: "100vh", background: "#050308", padding: "32px 16px" }}>
      <AskBhabitExperience />
    </div>
  </React.StrictMode>
);
