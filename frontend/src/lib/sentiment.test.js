import { describe, it, expect } from 'vitest';
import { inferSentiment, colorForSentiment } from './sentiment';

describe('sentiment helpers', () => {
  it('infers sentiment from deltas', () => {
    expect(inferSentiment({ price_change_percentage_1min: 2 })).toBe('positive');
    expect(inferSentiment({ price_change_percentage_3min: -1.2 })).toBe('negative');
    expect(inferSentiment({})).toBe('neutral');
  });
  it('maps to UI classes', () => {
    expect(colorForSentiment({ price_change_percentage_1min: 2 })).toBe('text-bhabit-blue');
    expect(colorForSentiment({ price_change_percentage_1min: -1 })).toBe('text-bhabit-pink');
    expect(colorForSentiment({ price_change_percentage_1min: 0 })).toBe('text-zinc-400');
  });
});
