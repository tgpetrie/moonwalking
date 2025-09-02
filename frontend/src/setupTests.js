import '@testing-library/jest-dom';

// Silence console noise in tests unless explicitly enabled
const originalLog = console.log;
if (!process.env.VITE_DEBUG_LOGS && !process.env.VITE_DEBUG) {
  console.log = (...args) => {
    if (/\[GainersTable1Min]|\[WebSocket Context]/.test(args[0])) return; // skip verbose
    originalLog(...args);
  };
}