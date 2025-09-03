// Centralized runtime config access for frontend
export const getEnv = () => {
  // Prefer Vite import.meta.env, fallback to window shim used by tests
  const vite = typeof import.meta !== 'undefined' ? (import.meta.env || {}) : {};
  const win = typeof window !== 'undefined' ? (window.importMeta?.env || {}) : {};
  return { ...vite, ...win };
};

export const flags = {
  VITE_DISABLE_WS: (getEnv().VITE_DISABLE_WS ?? 'false').toString().toLowerCase() === 'true',
  VITE_DEBUG_LOGS: (getEnv().VITE_DEBUG_LOGS ?? 'false').toString().toLowerCase() === 'true',
  VITE_ONE_MIN_WS_THROTTLE_MS: Number(getEnv().VITE_ONE_MIN_WS_THROTTLE_MS) || 15000
};
