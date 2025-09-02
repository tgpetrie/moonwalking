import { describe, it, expect } from 'vitest';
import { formatPrice, formatPercentage, truncateSymbol, formatCurrency, formatPercent, formatterRegistry } from './formatters.js';

describe('formatters', () => {
  it('formats positive and negative prices with adaptive precision (legacy wrapper)', () => {
    expect(formatPrice(123.456)).toBe('$123.46');
    expect(formatPrice(-0.345678)).toBe('$-0.3457');
  });

  it('formats very small prices with scientific notation', () => {
    const out = formatPrice(1e-10);
    expect(out.startsWith('$')).toBe(true);
    expect(out.includes('e-')).toBe(true);
  });

  it('formats percentage with sign and fraction option (legacy)', () => {
    expect(formatPercentage(0.1234, { fraction: true, sign: true, decimals: 2 })).toBe('+12.34%');
    expect(formatPercentage(-5.4321, { decimals: 1 })).toBe('-5.4%');
  });

  it('truncateSymbol shortens long text and preserves shorter ones', () => {
    expect(truncateSymbol('BITCOIN', 6)).toBe('BITCO…');
    expect(truncateSymbol('ETH', 6)).toBe('ETH');
  });

  it('formatCurrency uses rule table and supports trim & sign', () => {
    // Ensure default registry
    formatterRegistry.set({ currency: 'USD', locale: 'en-US' });
    expect(formatCurrency(2.3456)).toBe('$2.35'); // >=1 rule 2 decimals
    expect(formatCurrency(0.23456)).toBe('$0.2346'); // >=0.1 rule 4 decimals
    expect(formatCurrency(0.0234567)).toBe('$0.02346'); // >=0.01 rule 5 decimals
    expect(formatCurrency(-0.0234567, { sign: true })).toBe('$-0.02346');
    const trimmed = formatCurrency(0.230000, { trim: true });
    expect(trimmed).toBe('$0.23');
  });

  it('formatPercent handles fraction input and sign & trim', () => {
    expect(formatPercent(0.12345, { fromFraction: true, max: 2, sign: true })).toBe('+12.35%');
    expect(formatPercent(-0.5, { fromFraction: true, max: 1 })).toBe('-50%');
    expect(formatPercent(12.5, { fromFraction: false, max: 1, sign: true })).toBe('+12.5%');
  });
});
