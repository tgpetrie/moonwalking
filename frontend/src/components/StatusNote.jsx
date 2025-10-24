// Unified status note for loading / error / empty states
export default function StatusNote({ state, message }) {
  const base = "mt-6 text-center text-sm";
  if (state === "loading") return <p className={`${base} opacity-70`}>Loading…</p>;
  if (state === "error")   return <p className={`${base} text-purple-300/80`}>Failed to load — try refresh</p>;
  return <p className={`${base} opacity-70`}>{message || "No data available"}</p>;
}
