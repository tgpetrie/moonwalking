import { useState, lazy, Suspense } from 'react';
import PropTypes from 'prop-types';

const SentimentCard = lazy(() => import('./SentimentCard.jsx'));

export default function TokenRow({ row, isWatched = false, onToggleWatch = undefined, isGainer = false }) {
  const [open, setOpen] = useState(false);
  const symbol = (row.symbol || '').toUpperCase().replace(/-USD$/, '');
  const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${symbol}-USD`;
  const price = typeof row.current_price === 'number' ? row.current_price : row.price;
  const pct = typeof row.price_change_percentage_3min === 'number'
    ? row.price_change_percentage_3min
    : (typeof row.change3m === 'number' ? row.change3m : row.change);

  const formatPct = () => {
    if (typeof pct !== 'number' || Number.isNaN(pct)) {
      return '—';
    }
    const prefix = pct >= 0 ? '+' : '';
    return `${prefix}${pct.toFixed(2)}%`;
  };

  const handleRowClick = (e) => {
    // Allow elements with [data-stop] to prevent row navigation (icons, buttons)
    if (e && e.target && typeof e.target.closest === 'function' && e.target.closest('[data-stop]')) return;
    if (typeof window !== 'undefined') {
      window.open(coinbaseUrl, '_blank', 'noopener');
    }
  };

  const handleWatchClick = (event) => {
    event.stopPropagation();
    onToggleWatch?.(symbol);
  };

  const handleSentimentClick = (event) => {
    event.stopPropagation();
    setOpen(true);
  };

  const openStyle = open
    ? {
        backgroundImage:
          'linear-gradient(to right, rgba(255,122,0,0.3), rgba(155,91,255,0.3), rgba(71,167,255,0.3))',
        backgroundSize: '100% 2px',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'bottom left',
      }
    : undefined;

  return (
    <>
      <tr
        className={[
          'group transition-colors cursor-pointer',
          isGainer ? 'hover:bg-[image:var(--row-hover-gain)]' : 'hover:bg-[image:var(--row-hover-lose)]',
          'hover:bg-no-repeat hover:bg-left-bottom hover:bg-[length:100%_2px]'
        ].join(' ')}
        style={openStyle}
        onClick={handleRowClick}
      >
        <td className="px-3 py-2 font-semibold tracking-wide">{symbol || '—'}</td>
        <td className="px-3 py-2 tabular-nums">{typeof price === 'number' ? price.toFixed(4) : '—'}</td>
        <td className="px-3 py-2 tabular-nums">
          <span className={pct >= 0 ? 'pill up' : 'pill down'}>
            {formatPct()}
          </span>
        </td>
        <td className="px-3 py-2 text-center">
          <div className="relative flex flex-col items-center control-cluster">
            <button
              data-stop
              className={`text-[15px] block transition-transform hover:scale-110 ${isWatched ? 'text-yellow-300' : 'text-yellow-400'}`}
              onClick={handleWatchClick}
              title="Toggle watchlist"
              type="button"
            >
              ★
            </button>
            <button
              data-stop
              className="text-[13px] block text-gray-300 hover:text-blue mt-1"
              onClick={handleSentimentClick}
              title={`View ${symbol} sentiment`}
              type="button"
            >
              ℹ️
            </button>
          </div>
        </td>
      </tr>

      {open && (
        <Suspense fallback={null}>
          <SentimentCard symbols={[symbol]} onClose={() => setOpen(false)} />
        </Suspense>
      )}
    </>
  );
}

TokenRow.propTypes = {
  row: PropTypes.shape({
    symbol: PropTypes.string,
    current_price: PropTypes.number,
    price: PropTypes.number,
    price_change_percentage_3min: PropTypes.number,
    change3m: PropTypes.number,
    change: PropTypes.number,
  }).isRequired,
  isWatched: PropTypes.bool,
  onToggleWatch: PropTypes.func,
  isGainer: PropTypes.bool,
};
