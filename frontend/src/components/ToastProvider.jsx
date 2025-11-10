import React from 'react';

// Minimal ToastProvider placeholder. The full app may provide toast context/portal.
// This keeps the production build working while preserving existing layout.
export default function ToastProvider({ children }) {
  return <>{children}</>;
}
