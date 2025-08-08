

// ...existing code...

// API configuration for BHABIT CB4
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

// API endpoints matching your backend
export const API_ENDPOINTS = {
  topBanner: `${API_BASE_URL}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE_URL}/api/component/bottom-banner-scroll`,
  gainersTable: `${API_BASE_URL}/api/component/gainers-table`,
  gainersTable1Min: `${API_BASE_URL}/api/component/gainers-table-1min`,
  losersTable: `${API_BASE_URL}/api/component/losers-table`,
  topMoversBar: `${API_BASE_URL}/api/component/top-movers-bar`,
  crypto: `${API_BASE_URL}/api/crypto`,
  health: `${API_BASE_URL}/api/health`,
  marketOverview: `${API_BASE_URL}/api/market-overview`
};

// Fetch data from API
export const fetchData = async (endpoint) => {
  try {
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
};


// --- Watchlist Functions ---
const WATCHLIST_KEY = 'crypto_watchlist';

export async function getWatchlist() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/watchlist`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(data));
    return data;
  } catch (e) {
    console.error('Watchlist fetch error:', e);
    try {
      const raw = localStorage.getItem(WATCHLIST_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}

export async function addToWatchlist(symbol) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = await res.json();
    const list = result.watchlist || result;
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
    return list;
  } catch (e) {
    console.error('Add to watchlist error:', e);
    return await getWatchlist();
  }
}

export async function removeFromWatchlist(symbol) {
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/watchlist/${encodeURIComponent(symbol)}`,
      { method: 'DELETE' }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = await res.json();
    const list = result.watchlist || result;
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
    return list;
  } catch (e) {
    console.error('Remove from watchlist error:', e);
    return await getWatchlist();
  }
}
