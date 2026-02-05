import React from 'react';

// Minimal ToastProvider placeholder used during build/restoration.
// This intentionally keeps behavior simple: it provides a wrapper
// for components that expect a Toast/notification provider but
// defers a richer implementation to future restores.
export default function ToastProvider({ children }) {
  return <>{children}</>;
}
