import { getApiBaseUrl } from "../../api.js";
import { defaultResolveAnalysis } from "./defaultResolver.js";

const jsonHeaders = { "Content-Type": "application/json" };

export class AskBhabitClientError extends Error {
  constructor(kind, message, details = null) {
    super(message);
    this.name = "AskBhabitClientError";
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
    throw new AskBhabitClientError("network_failure", "Backend returned a non-JSON response.");
  }
  if (!response.ok || payload?.success === false) {
    const err = payload?.error || {};
    throw new AskBhabitClientError(
      err.code === "position_required" ? "backend_validation_failure" : "backend_validation_failure",
      err.message || `Ask Bhabit backend rejected the request (${response.status}).`,
      err
    );
  }
  return payload?.data ?? null;
}

async function request(path, options = {}) {
  try {
    const response = await fetch(endpoint(path), options);
    return await readEnvelope(response);
  } catch (error) {
    if (error instanceof AskBhabitClientError) throw error;
    throw new AskBhabitClientError("network_failure", error?.message || "Ask Bhabit network request failed.");
  }
}

function toBackendPosition(position) {
  return {
    asset_id: position?.asset,
    quantity: position?.quantity,
    entry_price: position?.entryPrice,
    total_cost_basis: position?.costBasis,
    acquisition_date: position?.acquiredAt,
    note: position?.note || null,
  };
}

function toBackendThesis(thesis) {
  if (!thesis) return null;
  return {
    why_entered: thesis.reason || null,
    reconsider_if: thesis.invalidation || null,
    time_horizon: thesis.horizon || null,
    tags: thesis.tags || [],
  };
}

export async function resolveLiveAnalysis({ position, question, isSample }) {
  if (isSample) {
    const fixture = await defaultResolveAnalysis({ position, question, isSample }, { delayMs: 250 });
    return { ...fixture, meta: { ...(fixture.meta || {}), mode: "demo_fixture" } };
  }

  await request("/api/ask-bhabit/position", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(toBackendPosition(position)),
  });

  const thesis = toBackendThesis(position?.thesis);
  if (thesis) {
    await request("/api/ask-bhabit/thesis", {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(thesis),
    });
  }

  return await request("/api/ask-bhabit/analyze", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ question_id: question?.id || null }),
  });
}

export async function fetchLiveEvidence() {
  return await request("/api/ask-bhabit/evidence");
}

export async function fetchLiveSnapshots() {
  return await request("/api/ask-bhabit/snapshots");
}
