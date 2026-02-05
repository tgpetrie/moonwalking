// frontend/src/lib/api.js — thin re-export to keep a single source of truth
import { API_ENDPOINTS, fetchAllData, fetchAllDataApi, fetchData, fetchJson } from "../api";

// Alias to match older imports that referenced `endpoints.*`
export const endpoints = {
  ...API_ENDPOINTS,
  metrics: API_ENDPOINTS.data,
  gainers: API_ENDPOINTS.gainersTable3Min || API_ENDPOINTS.gainers,
};

export async function fetchSentiment(symbol) {
  if (!symbol) return null;
  return fetchJson(API_ENDPOINTS.sentiment(symbol));
}

export { fetchAllData, fetchAllDataApi, fetchData, fetchJson };

export default { endpoints, fetchJson, fetchSentiment, fetchAllData, fetchAllDataApi, fetchData };
