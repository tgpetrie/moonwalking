// Intelligence Feed — network boundary.
//
// Mirrors the Ask Bhabit client: same {success, data} envelope, same error
// shape, so the two features fail identically from the UI's point of view.

import { getApiBaseUrl } from "../../api.js";

export class IntelligenceFeedError extends Error {
  constructor(kind, message, details = null) {
    super(message);
    this.name = "IntelligenceFeedError";
    this.kind = kind;
    this.details = details;
  }
}

const endpoint = (path) => `${getApiBaseUrl().replace(/\/$/, "")}${path}`;

async function readEnvelope(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    throw new IntelligenceFeedError(
      "network_failure",
      "Backend returned a non-JSON response."
    );
  }
  if (!response.ok || payload?.success === false) {
    const err = payload?.error || {};
    const kind = err.code === "unauthorized" ? "unauthorized" : "backend_failure";
    throw new IntelligenceFeedError(
      kind,
      err.message || `Intelligence feed request failed (${response.status}).`,
      err
    );
  }
  return payload?.data ?? null;
}

async function request(path, options = {}) {
  try {
    const response = await fetch(endpoint(path), {
      credentials: "include",
      ...options,
    });
    return await readEnvelope(response);
  } catch (error) {
    if (error instanceof IntelligenceFeedError) throw error;
    throw new IntelligenceFeedError(
      "network_failure",
      error?.message || "Intelligence feed network request failed."
    );
  }
}

export async function fetchIntelligenceEvents({ limit = 20 } = {}) {
  return await request(`/api/intelligence/events?limit=${encodeURIComponent(limit)}`);
}

export async function setIntelligenceEventStatus(eventId, status) {
  return await request(
    `/api/intelligence/events/${encodeURIComponent(eventId)}/status`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }
  );
}
