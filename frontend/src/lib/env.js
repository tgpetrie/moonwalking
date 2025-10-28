// Centralized environment helpers for frontend
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const SOCKET_BASE = (import.meta.env.VITE_WS_URL || '').replace(/\/$/, '');
export const POLL_MS = Number(import.meta.env.VITE_POLL_MS || 10000);

export const useRuntime = () => ({ apiBase: API_BASE, socketBase: SOCKET_BASE, pollMs: POLL_MS });
export const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:5001";
