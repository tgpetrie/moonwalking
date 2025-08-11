// Vercel serverless function: /api/ask-codex.js
// Robust OpenAI chat proxy with validation, model whitelist, optional streaming.
// No rate limiting or caching by default (stubs included for future use).

const ALLOWED_MODELS = new Set([
  'gpt-4o-mini',
  'gpt-4o',
  'gpt-4.1-mini',
  'gpt-3.5-turbo'
]);

// Simple (disabled by default) in-memory cache structure
const ENABLE_CACHE = false; // flip to true later if desired
const CACHE_TTL_MS = 30_000;
const cacheStore = new Map(); // key -> { expires, data }

function cacheKey(model, query) {
  return model + '::' + query.trim().toLowerCase();
}

function getCached(model, query) {
  if (!ENABLE_CACHE) return null;
  const key = cacheKey(model, query);
  const hit = cacheStore.get(key);
  if (!hit) return null;
  if (Date.now() > hit.expires) {
    cacheStore.delete(key);
    return null;
  }
  return hit.data;
}

function setCached(model, query, data) {
  if (!ENABLE_CACHE) return;
  cacheStore.set(cacheKey(model, query), { expires: Date.now() + CACHE_TTL_MS, data });
}

export default async function handler(req, res) {
  const started = Date.now();
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!process.env.OPENAI_API_KEY) {
    return res.status(500).json({ error: 'Missing OpenAI API key' });
  }

  let { query, model = 'gpt-4o-mini', stream = false, temperature = 0.2 } = req.body || {};

  // Basic sanitization & validation
  if (typeof query !== 'string') {
    return res.status(400).json({ error: 'Query must be a string' });
  }
  query = query.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '').trim();
  if (!query) {
    return res.status(400).json({ error: 'Empty query' });
  }
  if (query.length > 4000) {
    return res.status(413).json({ error: 'Query too long (max 4000 chars)' });
  }

  if (!ALLOWED_MODELS.has(model)) {
    model = 'gpt-4o-mini'; // fallback to a safe default
  }

  if (typeof temperature !== 'number' || Number.isNaN(temperature)) temperature = 0.2;
  temperature = Math.min(1, Math.max(0, temperature));

  // Development gating example (optional): uncomment to restrict prod usage
  // if (process.env.NODE_ENV === 'production') {
  //   return res.status(403).json({ error: 'Endpoint disabled in production' });
  // }

  // Cache check (non-stream only)
  if (!stream) {
    const cached = getCached(model, query);
    if (cached) {
      return res.status(200).json({ reply: cached.reply, cached: true, model });
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25_000); // 25s timeout

  const payload = {
    model,
    messages: [
      {
        role: 'system',
        content: 'You are a concise React/JS/crypto assistant helping debug and optimize a WebSocket-based crypto dashboard. Prefer actionable answers.'
      },
      { role: 'user', content: query }
    ],
    temperature,
    stream
  };

  try {
    const upstream = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    if (!upstream.ok) {
      const errText = await upstream.text().catch(() => '');
      return res.status(upstream.status).json({ error: 'Upstream error', detail: errText.slice(0, 300) });
    }

    if (stream) {
      // Stream SSE style
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const reader = upstream.body.getReader();
      const encoder = new TextEncoder();

      const send = (obj) => {
        const line = `data: ${JSON.stringify(obj)}\n\n`;
        res.write(line);
      };

      send({ event: 'start', model });
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = new TextDecoder().decode(value);
        accumulated += chunk;
        // Raw OpenAI stream lines start with 'data:' lines
        const lines = chunk.split('\n').filter(Boolean);
        for (const l of lines) {
          if (l.startsWith('data:')) {
            const jsonPart = l.replace(/^data:\s*/, '');
            if (jsonPart === '[DONE]') continue;
            try {
              const parsed = JSON.parse(jsonPart);
              const delta = parsed.choices?.[0]?.delta?.content;
              if (delta) send({ event: 'delta', token: delta });
            } catch (_) {
              // ignore malformed lines
            }
          }
        }
      }
      send({ event: 'end' });
      return res.end();
    }

    const data = await upstream.json();
    const reply = data.choices?.[0]?.message?.content || 'No reply received';

    setCached(model, query, { reply });

    const latencyMs = Date.now() - started;
    return res.status(200).json({ reply, model, latencyMs });
  } catch (e) {
    const aborted = e.name === 'AbortError';
    return res.status(500).json({ error: aborted ? 'Request timeout' : 'Request failed' });
  } finally {
    clearTimeout(timeout);
  }
}
