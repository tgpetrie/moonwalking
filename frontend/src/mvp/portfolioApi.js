import { getBackendBase } from "../config/api.js";

function apiUrl(pathname) {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${getBackendBase()}${path}`;
}

export class PortfolioApiError extends Error {
  constructor(message, response, payload) {
    super(message);
    this.name = "PortfolioApiError";
    this.status = response?.status || 0;
    this.payload = payload || {};
  }
}

async function jsonRequest(pathname) {
  const response = await fetch(apiUrl(pathname), {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    throw new PortfolioApiError(
      payload?.error || `Request failed with status ${response.status}`,
      response,
      payload
    );
  }
  return payload;
}

export function fetchPortfolio({ force = false } = {}) {
  return jsonRequest(`/api/portfolio${force ? "?refresh=1" : ""}`);
}

export function fetchPortfolioMarketContext() {
  return jsonRequest("/data");
}
