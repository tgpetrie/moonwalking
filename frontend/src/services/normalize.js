export function normalizeComponentPayload(payload) {
  const rows = Array.isArray(payload?.data)
    ? payload.data
    : Array.isArray(payload?.rows)
    ? payload.rows
    : [];

  const count = Number.isFinite(payload?.count) ? payload.count : rows.length;

  return {
    rows,
    count,
    component: payload?.component,
    raw: payload,
  };
}
