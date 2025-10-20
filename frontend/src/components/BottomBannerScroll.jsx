import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useBannerVolume1h } from '../hooks/useData';
import Marquee from './banners/Marquee';

const FALLBACK_VOLUME_ROWS = [
  { symbol: 'SUKU', price: 0.0295, pct: 3.51, volume24h: 25_000_000 },
  { symbol: 'HNT', price: 2.3, pct: 0.97, volume24h: 18_000_000 },
  { symbol: 'OCEAN', price: 0.3162, pct: 0.6, volume24h: 15_000_000 },
  { symbol: 'PENGU', price: 0.01605, pct: 0.56, volume24h: 12_000_000 },
  { symbol: 'MUSE', price: 7.586, pct: 0.53, volume24h: 10_000_000 },
];

const formatAbbrev = (value = 0) => {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2).replace(/\.0+$/, '')}T`;
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2).replace(/\.0+$/, '')}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2).replace(/\.0+$/, '')}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(1).replace(/\.0+$/, '')}K`;
  return `${sign}${abs.toFixed(0)}`;
};

const BottomBannerScroll = ({ refreshTrigger }) => {
  const { items, loading, refresh } = useBannerVolume1h();

  React.useEffect(() => {
    if (refreshTrigger !== undefined) refresh();
  }, [refreshTrigger, refresh]);

  const marqueeRows = useMemo(() => {
    const source = (items && items.length ? items : FALLBACK_VOLUME_ROWS).slice(0, 24);
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
    <section className="relative overflow-hidden rounded-3xl w-full max-w-full" aria-label="1H Volume Change • Live Market Feed">
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-prosto tracking-wide uppercase text-orange">
            1H Volume Change • Live Market Feed
          </h3>
        </div>
      </div>
      <div className="relative h-16">
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute inset-0 flex items-center">
          <Marquee speed={52}>
            {marqueeRows.map((coin) => {
              const pct = Number(coin.pct || coin.volumeChange || 0);
              return (
                <div key={coin._id} className="flex-shrink-0">
                  <div className="flex items-center gap-4 px-4 py-2 rounded-full bg-black/25 hover:scale-[1.02] transition-transform duration-300">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-orange uppercase tracking-wide">{coin.symbol}</span>
                      <span className="text-base font-semibold text-teal tabular-nums">
                        ${formatAbbrev(Number(coin.volume24h ?? coin.notional ?? 0))}
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

BottomBannerScroll.propTypes = {
  refreshTrigger: PropTypes.any,
};

export default BottomBannerScroll;
