import PropTypes from 'prop-types';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import InfoIcon from './InfoIcon.jsx';
import SentimentCard from './SentimentCard.jsx';
import { useSentiment } from '../../hooks/useSentiment';

const numberFormatter = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0.00';
  return num.toFixed(2);
};

function AnimatedNumber({ value }) {
  const motionValue = useMotionValue(Number(value ?? 0));
  const spring = useSpring(motionValue, {
    stiffness: 240,
    damping: 28,
    mass: 0.8,
  });
  const [display, setDisplay] = useState(numberFormatter(value));

  useEffect(() => {
    const unsubscribe = spring.on('change', (latest) => {
      setDisplay(numberFormatter(latest));
    });
    return () => {
      unsubscribe();
    };
  }, [spring]);

  useEffect(() => {
    motionValue.set(Number(value ?? 0));
  }, [motionValue, value]);

  return <motion.span>{display}</motion.span>;
}

AnimatedNumber.propTypes = {
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export default function AnimatedRow({ coin, index, changeDirection, changeLabel, onRowClick }) {
  const delta =
    Number(
      coin.change ??
        coin.delta ??
        coin.price_change_percentage_1min ??
        coin.price_change_percentage ??
        coin.gain ??
        coin.pct ??
        coin.change_pct ??
        0
    ) || 0;
  const price =
    Number(coin.price ?? coin.current ?? coin.current_price ?? coin.last ?? coin.close ?? coin.latest ?? 0) || 0;
  const isGain = delta >= 0;
  const lineClass = isGain ? 'gain' : 'loss';
  const glow = isGain ? 'var(--glow-gain)' : 'var(--glow-loss)';
  const flashCls = useMemo(() => {
    if (changeDirection === 'up') return 'cell-flash-up';
    if (changeDirection === 'down') return 'cell-flash-down';
    return '';
  }, [changeDirection]);

  const buttonRef = useRef(null);
  const popoverRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const symbol = coin.symbol ?? coin.pair ?? coin.asset ?? '';

  const sentiment = useSentiment(symbol, { prefetch: true });

  const handleInfoClick = (event) => {
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    setPosition({
      x: Math.round(rect.right + 12),
      y: Math.round(rect.top + window.scrollY - 6),
    });
    setOpen((prev) => !prev);
  };

  useEffect(() => {
    if (!open) return undefined;
    const handleOutside = (event) => {
      if (
        popoverRef.current &&
        (popoverRef.current === event.target || popoverRef.current.contains(event.target))
      ) {
        return;
      }
      if (
        buttonRef.current &&
        (buttonRef.current === event.target || buttonRef.current.contains(event.target))
      ) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('touchstart', handleOutside, { passive: true });
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('touchstart', handleOutside);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const syncPosition = () => {
      if (!buttonRef.current) return;
      const rect = buttonRef.current.getBoundingClientRect();
      setPosition({
        x: Math.round(rect.right + 12),
        y: Math.round(rect.top + window.scrollY - 6),
      });
    };
    const handleScroll = () => syncPosition();
    const handleResize = () => syncPosition();
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleResize);
    syncPosition();
    return () => {
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleResize);
    };
  }, [open]);

  return (
    <>
      <motion.tr
        layout
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.04, type: 'spring', stiffness: 280, damping: 24 }}
        whileHover={{ scale: 1.015, boxShadow: glow, filter: 'brightness(1.08)' }}
        className={`table-row ${lineClass}`}
        onClick={() => onRowClick?.(coin)}
      >
        <td className="px-3 py-2 font-mono text-gray-100 whitespace-nowrap">
          <div className="inline-flex items-center gap-2">
            <span>{symbol}</span>
            <span ref={buttonRef}>
              <InfoIcon onClick={handleInfoClick} title="View sentiment" />
            </span>
          </div>
        </td>
        <td className={`px-3 py-2 text-right ${isGain ? 'text-orange-400' : 'text-purple-300'} ${flashCls}`}>
          {delta >= 0 ? '+' : ''}
          <AnimatedNumber value={delta} />
          %
        </td>
        <td className="px-3 py-2 text-right text-gray-300 font-mono">
          {Number.isFinite(price) ? price.toFixed(4).replace(/0+$/, '').replace(/\.$/, '') : '—'}
        </td>
        <td className="px-3 py-2 text-right text-gray-400 text-xs uppercase tracking-wide hidden sm:table-cell">
          {changeLabel}
        </td>
      </motion.tr>
      <SentimentCard
        ref={popoverRef}
        open={open}
        x={position.x}
        y={position.y}
        symbol={symbol}
        sentiment={sentiment}
      />
    </>
  );
}

AnimatedRow.propTypes = {
  coin: PropTypes.object.isRequired,
  index: PropTypes.number.isRequired,
  changeDirection: PropTypes.oneOfType([PropTypes.string, PropTypes.oneOf([undefined])]),
  changeLabel: PropTypes.string,
  onRowClick: PropTypes.func,
};

AnimatedRow.defaultProps = {
  changeLabel: 'Δ%',
  onRowClick: undefined,
};
