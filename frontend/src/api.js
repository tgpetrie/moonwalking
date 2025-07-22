import { createClient } from '@supabase/supabase-js';

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

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// --- Supabase Watchlist Functions ---
// Assumes user authentication is handled and supabase.auth.getUser() returns the current user

export async function getWatchlist() {
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  console.log('[DEBUG] getWatchlist: user', user, 'userError', userError);
  if (!user) {
    console.warn('[DEBUG] getWatchlist: No user found');
    return [];
  }
  const { data, error } = await supabase
    .from('watchlist')
    .select('symbol')
    .eq('user_id', user.id);
  console.log('[DEBUG] getWatchlist: query result', data, 'error', error);
  if (error) {
    console.error('Supabase getWatchlist error:', error);
    return [];
  }
  return data.map(row => row.symbol);
}

export async function addToWatchlist(symbol) {
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  console.log('[DEBUG] addToWatchlist: user', user, 'userError', userError, 'symbol', symbol);
  if (!user) {
    console.warn('[DEBUG] addToWatchlist: No user found');
    return [];
  }
  const { error } = await supabase
    .from('watchlist')
    .insert([{ user_id: user.id, symbol }]);
  if (error) {
    console.error('Supabase addToWatchlist error:', error);
  } else {
    console.log('[DEBUG] addToWatchlist: Inserted', { user_id: user.id, symbol });
  }
  return getWatchlist();
}

export async function removeFromWatchlist(symbol) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { error } = await supabase
    .from('watchlist')
    .delete()
    .eq('user_id', user.id)
    .eq('symbol', symbol);
  if (error) {
    console.error('Supabase removeFromWatchlist error:', error);
  }
  return getWatchlist();
}
