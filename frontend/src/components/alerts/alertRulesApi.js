import { getBackendBase } from "../../config/api.js";

/**
 * Client for the user-scoped alert rule API (Phase 1/2 backend).
 *
 * Follows the portfolioApi.js precedent rather than the shared `fetchData`
 * helper: these calls carry the Flask session cookie, must surface the
 * server's own validation message, and must never be served from
 * fetchData's 10s response cache (a stale rule list after a mutation would
 * silently undo the user's action).
 *
 * Nothing here touches the legacy /api/alerts feed.
 */

function apiUrl(pathname) {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${getBackendBase()}${path}`;
}

export class AlertApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "AlertApiError";
    this.status = status || 0;
    this.payload = payload || {};
  }

  /** Signed-out is a normal state, not a failure. */
  get isAuthRequired() {
    return this.status === 401;
  }
}

const GENERIC_ERROR = "Could not reach the server.";

/**
 * Only surface a server message that reads like a sentence.
 *
 * Our own validation errors are written for humans ("That target is already at
 * or below the current price ($100.00)."), but proxies and infrastructure emit
 * machine tokens like `backend_unreachable`, which must never appear as UI copy.
 */
export function humanizeError(rawMessage, status) {
  const msg = String(rawMessage || "").trim();
  const looksLikeToken = !msg.includes(" ") || /^[a-z0-9]+(_[a-z0-9]+)+$/i.test(msg);
  if (!msg || looksLikeToken) {
    return status >= 500 || status === 0 ? GENERIC_ERROR : "That didn't work.";
  }
  return msg;
}

async function request(pathname, { method = "GET", body } = {}) {
  const options = {
    method,
    credentials: "include",
    headers: { Accept: "application/json" },
  };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(apiUrl(pathname), options);
  } catch (err) {
    throw new AlertApiError(GENERIC_ERROR, 0, {});
  }

  const contentType = response.headers.get("content-type") || "";
  let payload = {};
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
  }

  if (!response.ok) {
    throw new AlertApiError(
      humanizeError(payload?.error, response.status),
      response.status,
      payload
    );
  }
  return payload;
}

// ── rules ────────────────────────────────────────────────────────────────────

export async function listRules() {
  const data = await request("/api/alert-rules");
  return Array.isArray(data.rules) ? data.rules : [];
}

export async function createRule(payload) {
  const data = await request("/api/alert-rules", { method: "POST", body: payload });
  return data.rule || null;
}

export async function pauseRule(ruleId) {
  const data = await request(`/api/alert-rules/${encodeURIComponent(ruleId)}/pause`, {
    method: "POST",
  });
  return data.rule || null;
}

export async function resumeRule(ruleId) {
  const data = await request(`/api/alert-rules/${encodeURIComponent(ruleId)}/resume`, {
    method: "POST",
  });
  return data.rule || null;
}

export async function deleteRule(ruleId) {
  await request(`/api/alert-rules/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
  return true;
}

// ── recommendations ──────────────────────────────────────────────────────────

export async function listRecommendations({ refresh = false } = {}) {
  const data = await request(
    `/api/alert-recommendations${refresh ? "?refresh=1" : ""}`
  );
  return Array.isArray(data.recommendations) ? data.recommendations : [];
}

export async function acceptRecommendation(recId) {
  const data = await request(
    `/api/alert-recommendations/${encodeURIComponent(recId)}/accept`,
    { method: "POST", body: {} }
  );
  return data.rule || null;
}

export async function dismissRecommendation(recId) {
  await request(`/api/alert-recommendations/${encodeURIComponent(recId)}/dismiss`, {
    method: "POST",
  });
  return true;
}

// ── history ──────────────────────────────────────────────────────────────────

export async function listHistory({ limit = 50 } = {}) {
  const data = await request(`/api/alert-history?limit=${encodeURIComponent(limit)}`);
  return Array.isArray(data.events) ? data.events : [];
}
