// src/lib/api.js
export const API_BASE =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, '') ||
  `${window.location.protocol}//${window.location.hostname}:5001`;

export async function getJSON(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${path}${text ? ` — ${text.slice(0, 120)}` : ''}`);
  }
  return res.json();
}
