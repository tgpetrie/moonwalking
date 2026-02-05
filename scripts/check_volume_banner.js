#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const HEALTH_PATHS = ["/health", "/api/health"];
const PROBE_TIMEOUT_MS = 1500;
const SCAN_PORT_START = 5000;
const SCAN_PORT_END = 5010;
const FALLBACK_BASE = "http://127.0.0.1:5003";
const FRONTEND_ENV_FILE = path.join(__dirname, "../frontend/.env.local");

const sanitizeValue = (value) => {
  if (!value) return null;
  const trimmed = value.toString().trim().replace(/^\s*['\"]?|['\"]?\s*$/g, "");
  return trimmed ? trimmed.replace(/\/+$/, "") : null;
};

const readFrontendBase = () => {
  if (!fs.existsSync(FRONTEND_ENV_FILE)) return null;
  try {
    const contents = fs.readFileSync(FRONTEND_ENV_FILE, "utf8");
    const match = contents.match(/(?:export\s+)?VITE_API_BASE_URL\s*=\s*(.*)/);
    if (!match) return null;
    return sanitizeValue(match[1]);
  } catch (err) {
    console.warn("check_volume_banner: failed to read frontend/.env.local", err.message);
    return null;
  }
};

const logAttempts = (attempts) =>
  attempts
    .map((attempt) => {
      if (attempt.ok) return `${attempt.url} (ok)`;
      return `${attempt.url} (error: ${attempt.error || "failed"})`;
    })
    .join(", ");

const probeHealth = async (candidate, attempts) => {
  if (!candidate) return null;
  for (const suffix of HEALTH_PATHS) {
    const url = `${candidate}${suffix}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      attempts.push({ url, ok: res.ok });
      if (res.ok) {
        return candidate;
      }
    } catch (err) {
      const message = err?.name === "AbortError" ? "timeout" : err?.message || "unreachable";
      attempts.push({ url, ok: false, error: message });
    } finally {
      clearTimeout(timer);
    }
  }
  return null;
};

const scanPorts = async (attempts) => {
  for (let port = SCAN_PORT_START; port <= SCAN_PORT_END; port += 1) {
    const candidate = `http://127.0.0.1:${port}`;
    const found = await probeHealth(candidate, attempts);
    if (found) return found;
  }
  return null;
};

const detectBackendBase = async () => {
  const candidates = [
    readFrontendBase(),
    sanitizeValue(process.env.VITE_API_BASE_URL),
    sanitizeValue(process.env.API_BASE_URL),
    sanitizeValue(process.env.BACKEND_BASE_URL),
    sanitizeValue(process.env.BACKEND_HOST && process.env.BACKEND_PORT ? `http://${process.env.BACKEND_HOST}:${process.env.BACKEND_PORT}` : null),
    FALLBACK_BASE,
  ]
    .filter(Boolean)
    .filter((value, index, list) => list.indexOf(value) === index);

  const attempts = [];
  for (const candidate of candidates) {
    const success = await probeHealth(candidate, attempts);
    if (success) return { base: success, attempts };
  }

  const scanned = await scanPorts(attempts);
  if (scanned) return { base: scanned, attempts };

  const detail = logAttempts(attempts);
  throw new Error(`Backend not reachable. Tried: ${detail || "no candidates"}`);
};

const pick = (obj, keys) => {
  for (const key of keys) {
    if (obj && obj[key] != null) return obj[key];
  }
  return null;
};

(async () => {
  const { base } = await detectBackendBase();
  const url = `${base.replace(/\/$/, "")}/data`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  const payload = data?.data ?? data ?? {};
  const list = payload.banner_1h_volume ?? [];

  console.log(`GET ${url}`);
  console.log(`using backend base ${base}`);
  console.log("banner_1h_volume sample:");
  (list || [])
    .slice(0, 5)
    .forEach((item, idx) => {
      const volumeNow = pick(item, [
        "volume_1h_now",
        "volume_1h",
        "volume_now",
        "vol1h",
        "volume",
        "volume_24h",
      ]);
      const baseline = pick(item, [
        "volume_1h_prev",
        "volume_prev_1h",
        "volume_prev",
        "volume_1h_ago",
      ]);
      const delta = pick(item, ["volume_1h_delta", "volume_change_1h", "volume_change"]);
      const pct = pick(item, [
        "volume_change_1h_pct",
        "volume_1h_pct",
        "volume_change_pct_1h",
        "volume_change_pct",
        "pct",
        "pct_change",
      ]);
      console.log(`- [${idx}]`, {
        symbol: item?.symbol,
        product_id: item?.product_id,
        volumeNow: volumeNow != null,
        baseline: baseline != null,
        delta: delta != null,
        pct: pct != null,
        baseline_ready: item?.baseline_ready,
        baseline_missing_reason: item?.baseline_missing_reason,
      });
    });
})().catch((err) => {
  console.error("check_volume_banner failed:", err.message);
  process.exit(1);
});
