// src/api.js
// always fetch relative to the Vite dev server, let Vite proxy to 5001
export async function fetchData(path = "/data") {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status}`);
  }
  return res.json();
}

