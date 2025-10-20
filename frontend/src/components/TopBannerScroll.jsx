import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useBanner1h } from '../hooks/useData';
import Marquee from './banners/Marquee';

const FALLBACK_ITEMS = [
  { symbol: 'BTC', price: 45231.12, pct: 1.42 },
  { symbol: 'ETH', price: 3280.45, pct: 1.18 },
  { symbol: 'SOL', price: 98.13, pct: 2.67 },
  { symbol: 'AVAX', price: 36.44, pct: -0.82 },
  { symbol: 'PEPE', price: 0.0000019, pct: 4.35 },
];

const TopBannerScroll = ({ refreshTrigger }) => {
  const { items, loading, refresh } = useBanner1h();

  React.useEffect(() => {
    if (refreshTrigger !== undefined) refresh();
  }, [refreshTrigger, refresh]);

  const marqueeRows = useMemo(() => {
    const source = (items && items.length ? items : FALLBACK_ITEMS).slice(0, 24);
    const repeats = Math.max(2, Math.ceil(32 / Math.max(source.length, 1)));
    const expanded = [];
    for (let r = 0; r < repeats; r += 1) {
      expanded.push(
        ...source.map((coin, idx) => ({
          ...coin,
          _id: `${coin.symbol}-${r}-${idx}`,
        }))
      );
    }
    return expanded;
  }, [items]);

  if (!marqueeRows.length && loading) return null;

  return (
    <section className="relative overflow-hidden rounded-3xl w-full max-w-full" aria-label="1H Price Change • Live Market Feed">
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-prosto tracking-wide uppercase text-orange">
            1H Price Change • Live Market Feed
          </h3>
        </div>
      </div>
      <div className="relative h-16">
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute inset-0 flex items-center">
          <Marquee speed={50}>
            {marqueeRows.map((coin) => {
              const price = Number(coin.price || 0);
              const pct = Number(coin.pct || 0);
              return (
                <div key={coin._id} className="flex-shrink-0">
                  <div className="flex items-center gap-4 px-4 py-2 rounded-full transition-transform duration-300 hover:scale-[1.02] bg-black/25 shadow-none">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-orange uppercase tracking-wide">{coin.symbol}</span>
                      <span className="text-base font-semibold text-teal tabular-nums">
                        ${Number.isFinite(price) ? (price < 1 ? price.toFixed(4) : price.toFixed(2)) : '—'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 font-bold tabular-nums">
                      <span className={pct >= 0 ? 'text-pos' : 'text-neg'}>
                        {pct >= 0 ? '+' : ''}
                        {Number.isFinite(pct) ? pct.toFixed(3) : '0.000'}%
                      </span>
                      {coin.label ? <span className="text-xs uppercase tracking-wide text-purple/80">{coin.label}</span> : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </Marquee>
        </div>
      </div>
    </section>
  );
};

TopBannerScroll.propTypes = {
  refreshTrigger: PropTypes.any,
};

export default TopBannerScroll;
