// src/components/TopBannerScroll.jsx
import { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchWithSWR } from '../api';

function normalize(raw) {
  let rows =
    (Array.isArray(raw) && raw) ||
    raw?.data ||
    raw?.items ||
    raw?.banner ||
    [];
  if (!Array.isArray(rows)) rows = [];
  return rows.map((r, i) => ({
    id: r.id ?? r.symbol ?? r.ticker ?? i,
    text: r.text ?? r.title ?? `${(r.symbol || r.ticker || '').toUpperCase()} ${r.delta ?? ''}`,
  }));
}

export default function TopBannerScroll() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const raw = await fetchWithSWR(API_ENDPOINTS.topBanner);
        const norm = normalize(raw);
        if (!cancel) setItems(norm);
      } catch {}
    })();
    return () => {
      cancel = true;
    };
  }, []);

  if (!items.length) return null;

  return (
    <div className="banner banner--top">
      <div className="banner__track">
        {items.map((it) => (
          <span className="banner__item" key={it.id}>{it.text}</span>
        ))}
      </div>
    </div>
  );
}