
import type { RawPost, SentimentRow } from '../../../packages/core/src/index';

/** baseline lexical sentiment + emoji weighting */
export function featuresFromPosts(symbol: string, posts: RawPost[]): SentimentRow {
  const base = symbol.replace('-USD','').toUpperCase();
  const re = new RegExp(`\\b${base}\\b|\\$${base}\\b`, 'i');
  const symPosts = posts.filter(p => re.test(p.text));
  let pos = 0, neg = 0;
  for (const p of symPosts) {
    const t = p.text.toLowerCase();
    pos += (t.match(/\b(buy|moon|pump|bull|ath|rip)\b/g) || []).length;
    neg += (t.match(/\b(dump|bear|rug|scam|down)\b/g) || []).length;
    pos += (t.match(/🚀|🔥|💎/g) || []).length * 0.5;
    neg += (t.match(/💀|😭/g) || []).length * 0.5;
  }
  const mentions = symPosts.length;
  const score = mentions ? (pos - neg) / Math.sqrt(mentions) : 0;
  const srcMix = symPosts.reduce((m, p) => (m[p.src] = (m[p.src] || 0) + 1, m), {} as Record<string, number>);
  return {
    symbol, ts: Date.now(), mentions,
    sent_score: +score.toFixed(3),
    pos, neg, velocity: mentions, source_mix: srcMix
  };
}
