export class Hub {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.cacheSecs = 60;
  }

  async fetch(request) {
    const { pathname, searchParams } = new URL(request.url);

    if (pathname === '/server-info') {
      return json({ ok: true, mode: 'originless', ts: Date.now() });
    }

    // ---- WATCHLIST ----
    if (pathname === '/watchlist') {
      if (request.method === 'GET')  return this.watchlistGet();
      if (request.method === 'POST') return this.watchlistAdd(await request.json().catch(() => ({})));
      if (request.method === 'DELETE') return this.watchlistRemove(await request.json().catch(() => ({})));
      return new Response('Method Not Allowed', { status: 405 });
    }

    // ---- SENTIMENT ----
    if (pathname === '/sentiment') {
      const symbols = (searchParams.get('symbols') || (this.env.COIN_LIST || 'BTC,ETH'))
        .split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
      return this.sentimentFor(symbols);
    }

    // ---- SIGNALS (optional stub) ----
    if (pathname === '/signals/pumpdump') {
      return json({ ok: true, signals: [], ts: Date.now() });
    }

    return new Response('Not Found', { status: 404 });
  }

  // ===== Watchlist (stateful) =====
  async watchlistGet() {
    const wl = (await this.state.storage.get('watchlist')) || [];
    return json({ watchlist: wl });
  }
  async watchlistAdd(body) {
    const wl = (await this.state.storage.get('watchlist')) || [];
    const symbol = (body?.symbol || '').toString().toUpperCase();
    if (!symbol) return json({ error: 'symbol required' }, 400);
    if (!wl.includes(symbol)) wl.push(symbol);
    await this.state.storage.put('watchlist', wl);
    return json({ ok: true, watchlist: wl });
  }
  async watchlistRemove(body) {
    const wl = (await this.state.storage.get('watchlist')) || [];
    const symbol = (body?.symbol || '').toString().toUpperCase();
    const next = wl.filter(s => s !== symbol);
    await this.state.storage.put('watchlist', next);
    return json({ ok: true, watchlist: next });
  }

  // ===== Sentiment (ported from Python) =====
  async sentimentFor(symbols) {
    const now = Date.now();
    const cacheKey = `sentiment_${symbols.sort().join(',')}`;
    const last = await this.state.storage.get(`${cacheKey}_last_ts`);
    const cached = await this.state.storage.get(`${cacheKey}_cached`);
    if (cached && last && (now - last) / 1000 < this.cacheSecs) {
      return new Response(JSON.stringify(cached), {
        headers: { 'content-type': 'application/json', 'x-cache': 'HIT' }
      });
    }

    // Ported logic from Python social_sentiment.py
    const data = symbols.map(symbol => this._generateMockSentiment(symbol, now));

    await this.state.storage.put(`${cacheKey}_cached`, data);
    await this.state.storage.put(`${cacheKey}_last_ts`, now);
    return new Response(JSON.stringify(data), {
      headers: { 'content-type': 'application/json', 'x-cache': 'MISS' }
    });
  }

  _generateMockSentiment(symbol, now) {
    // Port of _generate_mock_sentiment
    let baseSentiment = 0.5;
    const upperSymbol = symbol.toUpperCase();

    if (['BTC', 'BITCOIN'].includes(upperSymbol)) baseSentiment = 0.65;
    else if (['ETH', 'ETHEREUM'].includes(upperSymbol)) baseSentiment = 0.6;
    else if (['DOGE', 'DOGECOIN'].includes(upperSymbol)) baseSentiment = 0.55;

    const sentimentScore = Math.max(0, Math.min(1, baseSentiment + (Math.random() - 0.5) * 0.4));

    const twitterMentions = Math.floor(Math.random() * 4950) + 50;
    const redditPosts = Math.floor(Math.random() * 490) + 10;
    const telegramMessages = Math.floor(Math.random() * 1900) + 100;

    const positiveRatio = sentimentScore * 0.8 + Math.random() * 0.2;
    const negativeRatio = (1 - sentimentScore) * 0.6 + Math.random() * 0.2;
    let neutralRatio = 1 - positiveRatio - negativeRatio;
    const total = positiveRatio + negativeRatio + neutralRatio;
    const pos = positiveRatio / total;
    const neg = negativeRatio / total;
    const neu = neutralRatio / total;

    const trendingKeywords = this._getTrendingKeywords(upperSymbol);
    const influencerMentions = this._getMockInfluencerMentions(upperSymbol);

    return {
      symbol: upperSymbol,
      overall_sentiment: {
        score: Math.round(sentimentScore * 1000) / 1000,
        label: this._getSentimentLabel(sentimentScore),
        confidence: Math.round((0.7 + Math.random() * 0.25) * 1000) / 1000
      },
      sentiment_distribution: {
        positive: Math.round(pos * 1000) / 1000,
        negative: Math.round(neg * 1000) / 1000,
        neutral: Math.round(neu * 1000) / 1000
      },
      social_metrics: {
        twitter: {
          mentions_24h: twitterMentions,
          sentiment_score: Math.round((sentimentScore + (Math.random() - 0.5) * 0.2) * 1000) / 1000,
          trending_rank: twitterMentions > 500 ? Math.floor(Math.random() * 100) + 1 : null
        },
        reddit: {
          posts_24h: redditPosts,
          comments_24h: redditPosts * (Math.floor(Math.random() * 12) + 3),
          sentiment_score: Math.round((sentimentScore + (Math.random() - 0.5) * 0.3) * 1000) / 1000,
          top_subreddits: [`r/${upperSymbol}`, 'r/CryptoCurrency', 'r/altcoins'].slice(0, Math.floor(Math.random() * 3) + 1)
        },
        telegram: {
          messages_24h: telegramMessages,
          active_groups: Math.floor(Math.random() * 45) + 5,
          sentiment_score: Math.round((sentimentScore + (Math.random() - 0.5) * 0.2) * 1000) / 1000
        }
      },
      trending_topics: trendingKeywords,
      influencer_mentions: influencerMentions,
      fear_greed_index: Math.floor(Math.random() * 60) + 20,
      volume_correlation: Math.round((0.3 + Math.random() * 0.5) * 1000) / 1000,
      price_correlation: Math.round((-0.2 + Math.random() * 0.9) * 1000) / 1000,
      last_updated: new Date(now).toISOString(),
      data_sources: ['Twitter', 'Reddit', 'Telegram', 'Discord'],
      note: 'Mock data for demonstration - integrate with real social APIs'
    };
  }

  _getSentimentLabel(score) {
    if (score >= 0.7) return 'Very Bullish';
    if (score >= 0.6) return 'Bullish';
    if (score >= 0.4) return 'Neutral';
    if (score >= 0.3) return 'Bearish';
    return 'Very Bearish';
  }

  _getTrendingKeywords(symbol) {
    const baseKeywords = [
      `$${symbol}`, `${symbol}USD`, 'hodl', 'buy', 'sell', 
      'moon', 'dip', 'pump', 'dump', 'bullish', 'bearish'
    ];

    if (symbol === 'BTC') baseKeywords.push('bitcoin', 'btc', 'digital gold', 'store of value');
    else if (symbol === 'ETH') baseKeywords.push('ethereum', 'defi', 'smart contracts', 'gas fees');
    else if (symbol === 'DOGE') baseKeywords.push('dogecoin', 'meme coin', 'elon', 'tesla');

    const selected = baseKeywords.sort(() => 0.5 - Math.random()).slice(0, Math.min(8, baseKeywords.length));
    return selected.map(keyword => ({
      keyword,
      mentions: Math.floor(Math.random() * 990) + 10,
      sentiment_score: Math.round((0.2 + Math.random() * 0.6) * 100) / 100,
      growth_24h: Math.round((-50 + Math.random() * 250) * 10) / 10
    })).sort((a, b) => b.mentions - a.mentions).slice(0, 6);
  }

  _getMockInfluencerMentions(symbol) {
    const mockInfluencers = [
      { name: 'CryptoAnalyst', followers: 145000, verified: true },
      { name: 'BlockchainExpert', followers: 89000, verified: true },
      { name: 'AltcoinDaily', followers: 230000, verified: false },
      { name: 'CoinBureau', followers: 180000, verified: true },
      { name: 'TheCryptoDog', followers: 95000, verified: false }
    ];

    const numMentions = Math.floor(Math.random() * 3) + 1;
    const selected = mockInfluencers.sort(() => 0.5 - Math.random()).slice(0, numMentions);
    return selected.map(inf => {
      const sentiments = ['bullish', 'bearish', 'neutral'];
      const sentiment = sentiments[Math.floor(Math.random() * sentiments.length)];
      return {
        influencer: inf.name,
        followers: inf.followers,
        verified: inf.verified,
        sentiment,
        engagement: Math.floor(Math.random() * 4950) + 50,
        timestamp: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
        preview: `Just analyzed ${symbol} and I'm feeling ${sentiment} about the current setup...`
      };
    });
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json' }
  });
}
