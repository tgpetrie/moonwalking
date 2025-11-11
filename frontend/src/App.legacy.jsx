// Minimal, inert legacy entrypoint kept for reference. This file intentionally
// exports a small placeholder component so it can't break the dev server.
import React from "react";

export default function LegacyApp() {
  return (
    <div style={{ padding: 12, color: "#cbd5e1" }}>
      Legacy app (archived)
    </div>
  );
}
