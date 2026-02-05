import React, { useEffect, useState, useMemo } from 'react';
import TopBannerScroll from './TopBannerScroll.jsx';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { normalizeBannerRow } from '../lib/adapters';

// Bottom banner should be a visual copy of the top banner but with volume-focused data.
// We'll fetch bottom banner data, normalize to the same shape TopBannerScroll expects
// (symbol, currentPrice, pctChange) and then render TopBannerScroll with `items=`.

const BottomBannerScroll = ({ refreshTrigger }) => {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const res = await fetchData(API_ENDPOINTS.bottomBanner);
        const rows = res && Array.isArray(res.items) ? res.items : (res && Array.isArray(res.data) ? res.data : (res && Array.isArray(res) ? res : []));

        if (Array.isArray(rows) && rows.length) {
          const mapped = rows.map((r, i) => {
            const nr = normalizeBannerRow(r || {});
            const symbol = nr.symbol || r.symbol || '--';
            const currentPrice = nr.currentPrice ?? r.current_price ?? 0;
            // Use 1h volume change as `pctChange` so styling and sign color map correctly
            const pctChange = r.volume_change_1h ?? nr.volumeChangePct ?? r.volume_change_1h_pct ?? r.volume_change_estimate ?? 0;
            return {
              symbol,
              currentPrice,
              pctChange,
              _raw: r,
              rank: i + 1,
            };
          });

          if (mounted) setItems(mapped.slice(0, 20));
          return;
        }

        // fallback
        if (mounted && items.length === 0) {
          setItems([
            { symbol: 'SUKU', currentPrice: 0.0295, pctChange: 3.51 },
            { symbol: 'HNT', currentPrice: 2.3, pctChange: 0.97 },
            { symbol: 'OCEAN', currentPrice: 0.3162, pctChange: 0.6 },
          ]);
        }
      } catch (err) {
        console.error('BottomBannerScroll load error', err);
        if (mounted && items.length === 0) {
          setItems([
            { symbol: 'SUKU', currentPrice: 0.0295, pctChange: 3.51 },
            { symbol: 'HNT', currentPrice: 2.3, pctChange: 0.97 },
          ]);
        }
      }
    };

    load();

    return () => { mounted = false; };
  }, [refreshTrigger]);

  // TopBannerScroll expects an `items` array with symbols/currentPrice/pctChange
  return <TopBannerScroll items={items} />;
};

export default BottomBannerScroll;
