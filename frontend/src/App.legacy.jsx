// Minimal, inert legacy entrypoint kept for reference. This file intentionally
// exports a small placeholder component so it can't break the dev server.
import React from "react";

export default function LegacyApp() {
  return (
    <div className="legacy-placeholder">
      Legacy app (archived)
    </div>
  );
}
