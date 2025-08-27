// Centralized watchlist helper (Codex-aware)
// - Stores items as { symbol, addedPrice?, addedAt? }
// - loadWatchlist() returns array of symbol strings (backwards-compatible)
// - loadWatchlistItems() returns normalized item objects
// - addToWatchlist(symbol, price) saves price and timestamp
// - removeFromWatchlist(symbol)
// - toggleWatchlist(symbol, price?) returns boolean now-in-watchlist

function _normSym(s) {
  return String(s || '').trim().toUpperCase();
}

function _normalizeItem(obj) {
  if (!obj) return null;
  if (typeof obj === 'string') return { symbol: _normSym(obj) };
  const symbol = _normSym(obj.symbol || obj.ticker || obj.s || obj.base);
  if (!symbol) return null;
  const addedPrice = obj.addedPrice ?? obj.priceAtAdd ?? obj.price ?? obj.added_price ?? null;
  const addedAt = obj.addedAt ?? obj.added_at ?? obj.ts ?? obj.timestamp ?? null;
  return { symbol, addedPrice: addedPrice == null ? null : Number(addedPrice), addedAt: addedAt == null ? null : Number(addedAt) };
}

function _emitChange(list) {
  try {
    window.dispatchEvent(new StorageEvent('storage', { key: 'watchlist:symbols' }));
  } catch (e) {}
  try {
    window.dispatchEvent(new CustomEvent('watchlist:changed', { detail: list }));
  } catch (e) {}
}

export function loadWatchlist() {
  // Backwards-compatible: return array of symbol strings
  try {
    const cx = typeof window !== 'undefined' ? (window.codex || window.CODEX || null) : null;
    const api = cx && (cx.watchlist || cx.watch || cx.favorites);
    if (api && typeof api.get === 'function') {
      const list = api.get();
      if (Array.isArray(list)) return list.map(i => (typeof i === 'string' ? _normSym(i) : (_normalizeItem(i)?.symbol || '') )).filter(Boolean);
    } else if (cx && typeof cx.getWatchlist === 'function') {
      const list = cx.getWatchlist();
      if (Array.isArray(list)) return list.map(i => (typeof i === 'string' ? _normSym(i) : (_normalizeItem(i)?.symbol || '') )).filter(Boolean);
    }
  } catch (e) {}
  try {
    const raw = localStorage.getItem('watchlist:symbols');
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    // parsed may be array of strings or objects
    return parsed.map(i => (typeof i === 'string' ? _normSym(i) : (_normalizeItem(i)?.symbol || ''))).filter(Boolean);
  } catch (e) { return []; }
}

export function loadWatchlistItems() {
  // Returns array of normalized item objects: { symbol, addedPrice?, addedAt? }
  try {
    const cx = typeof window !== 'undefined' ? (window.codex || window.CODEX || null) : null;
    const api = cx && (cx.watchlist || cx.watch || cx.favorites);
    if (api && typeof api.get === 'function') {
      const list = api.get();
      if (Array.isArray(list)) return list.map(_normalizeItem).filter(Boolean);
    } else if (cx && typeof cx.getWatchlist === 'function') {
      const list = cx.getWatchlist();
      if (Array.isArray(list)) return list.map(_normalizeItem).filter(Boolean);
    }
  } catch (e) {}
  try {
    const raw = localStorage.getItem('watchlist:symbols');
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.map(_normalizeItem).filter(Boolean);
  } catch (e) { return []; }
}

export function saveWatchlist(list) {
  // Accepts array of symbols or item objects. Store raw list as provided to preserve Codex shape.
  const normalized = Array.isArray(list) ? list : [];
  const uniqBySymbol = [];
  const seen = new Set();
  for (const it of normalized) {
    const item = _normalizeItem(it);
    if (!item) continue;
    if (seen.has(item.symbol)) continue;
    seen.add(item.symbol);
    uniqBySymbol.push(item);
  }
  // Try to hand off to Codex setter if present (keeps original shape if it expects strings)
  try {
    const cx = typeof window !== 'undefined' ? (window.codex || window.CODEX || null) : null;
    const api = cx && (cx.watchlist || cx.watch || cx.favorites);
    const out = uniqBySymbol.map(i => ({ symbol: i.symbol, addedPrice: i.addedPrice, addedAt: i.addedAt }));
    if (api && typeof api.set === 'function') {
      api.set(out);
    } else if (cx && typeof cx.setWatchlist === 'function') {
      cx.setWatchlist(out);
    }
  } catch (e) {}
  try {
    localStorage.setItem('watchlist:symbols', JSON.stringify(uniqBySymbol));
  } catch (e) {}
  _emitChange(uniqBySymbol.map(i => i.symbol));
  return uniqBySymbol;
}

export function addToWatchlist(symbol, price = null) {
  const S = _normSym(symbol);
  const items = loadWatchlistItems();
  if (items.some(it => it.symbol === S)) return saveWatchlist(items);
  const now = Date.now();
  const newItem = { symbol: S, addedPrice: price == null ? null : Number(price), addedAt: now };
  items.push(newItem);
  return saveWatchlist(items);
}

export function removeFromWatchlist(symbol) {
  const S = _normSym(symbol);
  const items = loadWatchlistItems().filter(it => it.symbol !== S);
  return saveWatchlist(items);
}

export function toggleWatchlist(symbol, price = null) {
  const S = _normSym(symbol);
  const items = loadWatchlistItems();
  const idx = items.findIndex(it => it.symbol === S);
  if (idx === -1) {
    items.push({ symbol: S, addedPrice: price == null ? null : Number(price), addedAt: Date.now() });
    saveWatchlist(items);
    return true;
  }
  items.splice(idx, 1);
  saveWatchlist(items);
  return false;
}

export function pctSinceAdded(addedPrice, currentPrice) {
  if (!Number.isFinite(Number(addedPrice)) || !Number.isFinite(Number(currentPrice))) return null;
  const a = Number(addedPrice); const c = Number(currentPrice);
  if (a === 0) return null;
  return ((c - a) / a) * 100;
}

export default {
  loadWatchlist,
  loadWatchlistItems,
  saveWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  toggleWatchlist,
  pctSinceAdded,
};
