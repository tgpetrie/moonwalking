import { PumpDump, DataBundle, MarketRow } from '../../../packages/core/src/index'
import type { RawPost, SentimentRow } from '../../../packages/core/src/index'
import { featuresFromPosts } from './sentiment_aggregate'
import { DiscordConnector, RedditConnector, TelegramConnector } from './connectors'

export interface Env {
  MW_KV: KVNamespace
  WATCHLIST_DO: DurableObjectNamespace
  CRON_SECRET: string
  ALERTS_Q?: Queue<any> // optional on Free plan
}

const PRODUCTS = [
  'BTC-USD',
  'ETH-USD',
  'SOL-USD',
  'ADA-USD',
  'AVAX-USD',
  'DOGE-USD',
  'XRP-USD',
  'LTC-USD',
  'LINK-USD',
  'MATIC-USD',
]

const KV_KEYS = {
  DATA: 'mw:data:bundle',
  SIGNALS: 'mw:signals',
  C_NOW: 'mw:candle:now',
  C_1M: 'mw:candle:1m',
  C_3M: 'mw:candle:3m',
  C_60M: 'mw:candle:60m',
  VOLSTATS: 'mw:volstats:1h',
  PX_G1M: 'mw:px:gainers1m',
  PX_G3M: 'mw:px:gainers3m',
  DEVICES: 'mw:devices',
  DEV_PREFIX: 'mw:dev:',
  SENT_LAST: 'mw:sent:last',
  SENT_LATEST_PREFIX: 'mw:sent:latest:',
}

type Candle = {
  ts: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const json = (obj: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(obj), {
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers || {}) },
  })
const bad = (msg: string, status = 400) => json({ error: msg }, { status })

export class WatchlistDO {
  state: DurableObjectState
  constructor(state: DurableObjectState) {
    this.state = state
  }
  async fetch(req: Request) {
    const url = new URL(req.url)
    if (req.method === 'GET' && url.pathname === '/') {
      const wl = (await this.state.storage.get<string[]>('wl')) || []
      return json({ watchlist: wl })
    }
    if (req.method === 'POST' && url.pathname === '/add') {
      const body = (await req.json().catch(() => ({}))) as { symbol?: string }
      const { symbol } = body
      if (!symbol) {
        return bad('symbol required')
      }
      const wl = (await this.state.storage.get<string[]>('wl')) || []
      if (!wl.includes(symbol)) {
        wl.push(symbol)
      }
      await this.state.storage.put('wl', wl)
      return json({ ok: true, watchlist: wl })
    }
    if (req.method === 'POST' && url.pathname === '/remove') {
      const body = (await req.json().catch(() => ({}))) as { symbol?: string }
      const { symbol } = body
      if (!symbol) {
        return bad('symbol required')
      }
      const wl = (await this.state.storage.get<string[]>('wl')) || []
      const next = wl.filter((s) => s !== symbol)
      await this.state.storage.put('wl', next)
      return json({ ok: true, watchlist: next })
    }
    return bad('not found', 404)
  }
}

const pct = (from?: number, to?: number) =>
  from && to && from !== 0 ? ((to - from) / from) * 100 : undefined
const bodyRatio = (c: Candle) => {
  const r = c.high - c.low
  return r > 0 ? Math.abs(c.close - c.open) / r : 0
}
const zscore = (v: number, mean: number, std: number) => (std > 1e-9 ? (v - mean) / std : 0)
const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))

function welfordUpdate(s: { n: number; mean: number; m2: number; std: number }, x: number) {
  const n1 = s.n + 1
  const delta = x - s.mean
  const mean = s.mean + delta / n1
  const m2 = s.m2 + delta * (x - mean)
  const std = n1 > 1 ? Math.sqrt(m2 / (n1 - 1)) : 0
  return { n: n1, mean, m2, std }
}

async function fetchCoinbaseTickers(): Promise<Record<string, number>> {
  const out: Record<string, number> = {}
  await Promise.all(
    PRODUCTS.map(async (p) => {
      try {
        const r = await fetch(`https://api.exchange.coinbase.com/products/${p}/ticker`)
        if (!r.ok) {
          return
        }
        const j = (await r.json()) as any
        if (j?.price) {
          out[p] = parseFloat(j.price)
        }
      } catch {}
    })
  )
  return out
}

async function updatePx(env: Env, table: MarketRow[], key: string) {
  const prev = JSON.parse((await env.MW_KV.get(key)) || '{}')
  const present = new Set(table.map((r) => r.symbol))
  const next: Record<string, number> = {}
  const syms = new Set<string>([...Object.keys(prev), ...present])
  for (const s of syms) {
    const was = prev[s] || 0
    const is = present.has(s) ? was + 1 : 0
    next[s] = is
  }
  await env.MW_KV.put(key, JSON.stringify(next))
  for (const r of table) r.px = next[r.symbol] || 1
}

function computeSignals(args: {
  latest: Record<string, Candle>
  c1m: Record<string, Candle>
  c3m: Record<string, Candle>
  volstats: Record<string, { mean: number; std: number }>
  streaks: Record<string, number>
}): PumpDump[] {
  const out: PumpDump[] = []
  const now = Date.now()
  for (const sym of Object.keys(args.latest)) {
    const nowC = args.latest[sym],
      c1 = args.c1m[sym],
      c3 = args.c3m[sym]
    if (!nowC || !c1 || !c3) {
      continue
    }
    const p1 = pct(c1.close, nowC.close)
    const p3 = pct(c3.close, nowC.close)
    if (p1 == null || p3 == null) {
      continue
    }
    const stat = args.volstats[sym] || { mean: 0, std: 0 }
    const vz = zscore(nowC.volume, stat.mean, stat.std)
    const b = bodyRatio(nowC)
    const st = args.streaks[sym] || 0
    if (Math.abs(p1) < 0.8 || Math.abs(p3) < 1.2 || vz < 1.0 || b < 0.35) {
      continue
    }
    const direction = p1 > 0 ? 'PUMP' : 'DUMP'
    let x = 0.6 * (p1 / 1.0) + 0.4 * (p3 / 1.0) + 0.8 * vz + 0.2 * st + 0.5 * ((b - 0.35) * 3)
    if (direction === 'DUMP') {
      x = -x
    }
    const score = sigmoid(x)
    const tags: string[] = []
    if (Math.abs(p1) >= 2) {
      tags.push('fast-move')
    }
    if (Math.abs(p3) >= 3) {
      tags.push('impulse-3m')
    }
    if (vz >= 2) {
      tags.push('vol-spike')
    }
    if (Math.abs(st) >= 3) {
      tags.push('streak')
    }
    out.push({
      symbol: sym,
      direction,
      score: +score.toFixed(3),
      pct_1m: +p1.toFixed(3),
      pct_3m: +p3.toFixed(3),
      vol_z: +vz.toFixed(2),
      streak: st,
      body: +b.toFixed(2),
      tags,
      ts: now,
    })
  }
  return out.sort((a, b) => b.score - a.score).slice(0, 20)
}

async function buildBundle(env: Env, prices: Record<string, number>): Promise<DataBundle> {
  const now = Date.now()
  const prevNow = JSON.parse((await env.MW_KV.get(KV_KEYS.C_NOW)) || '{}')
  const c1m = JSON.parse((await env.MW_KV.get(KV_KEYS.C_1M)) || '{}')
  const c3m = JSON.parse((await env.MW_KV.get(KV_KEYS.C_3M)) || '{}')
  const c60 = JSON.parse((await env.MW_KV.get(KV_KEYS.C_60M)) || '{}')
  const volstats = JSON.parse((await env.MW_KV.get(KV_KEYS.VOLSTATS)) || '{}')

  await env.MW_KV.put(KV_KEYS.C_3M, JSON.stringify(c1m))
  await env.MW_KV.put(KV_KEYS.C_1M, JSON.stringify(prevNow))

  const latest: Record<string, Candle> = {}
  for (const [sym, price] of Object.entries(prices)) {
    const prev = prevNow[sym] as Candle | undefined
    const base: Candle = prev || {
      ts: now,
      open: price,
      high: price,
      low: price,
      close: price,
      volume: 0,
    }
    const high = Math.max(base.high, price)
    const low = Math.min(base.low, price)
    latest[sym] = {
      ts: now,
      open: base.open,
      high,
      low,
      close: price,
      volume: (base.volume || 0) + 1,
    }
  }
  await env.MW_KV.put(KV_KEYS.C_NOW, JSON.stringify(latest))

  for (const [sym, c] of Object.entries(latest)) {
    const s = volstats[sym] || { n: 0, mean: 0, m2: 0, std: 0 }
    volstats[sym] = welfordUpdate(s, (c as Candle).volume)
  }
  await env.MW_KV.put(KV_KEYS.VOLSTATS, JSON.stringify(volstats))

  const rows: MarketRow[] = Object.entries(latest).map(([symbol, c]) => {
    const r: MarketRow = { symbol, price: c.close, ts: now }
    const one = (c1m[symbol] as Candle | undefined)?.close
    const thr = (c3m[symbol] as Candle | undefined)?.close
    const six = (c60[symbol] as Candle | undefined)?.close
    r.changePct1m = pct(one, c.close)
    r.changePct3m = pct(thr, c.close)
    r.changePct1h = pct(six, c.close)
    return r
  })

  const by = (key: keyof MarketRow, asc = false) =>
    [...rows]
      .filter((r) => r[key] != null)
      .sort((a, b) => {
        const av = a[key] as number
        const bv = b[key] as number
        return asc ? av - bv : bv - av
      })

  const gainers1m = by('changePct1m').slice(0, 8)
  const gainers3m = by('changePct3m').slice(0, 10)
  const losers3m = by('changePct3m', true).slice(0, 10)
  const banner1h = by('changePct1h').slice(0, 10)
  const volume1h: MarketRow[] = []

  await updatePx(env, gainers1m, KV_KEYS.PX_G1M)
  await updatePx(env, gainers3m, KV_KEYS.PX_G3M)

  return { banner1h, gainers1m, gainers3m, losers3m, volume1h, ts: now }
}

function allowedThreshold(s: PumpDump) {
  return s.score >= 0.85 && s.vol_z >= 2
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url)
    const deviceId = req.headers.get('X-Device-Id') || 'anon'

    if (req.method === 'GET' && url.pathname === '/data') {
      const s = await env.MW_KV.get(KV_KEYS.DATA)
      if (!s) {
        return bad('no data', 404)
      }
      return new Response(s, { headers: { 'content-type': 'application/json' } })
    }

    if (req.method === 'GET' && url.pathname === '/signals/pumpdump') {
      const s = await env.MW_KV.get(KV_KEYS.SIGNALS)
      if (!s) {
        return bad('no signals', 404)
      }
      return new Response(s, { headers: { 'content-type': 'application/json' } })
    }

    if (url.pathname.startsWith('/watchlist')) {
      const id = env.WATCHLIST_DO.idFromName(deviceId)
      const stub = env.WATCHLIST_DO.get(id)
      if (req.method === 'GET' && url.pathname === '/watchlist') {
        return stub.fetch('https://do/')
      }
      if (req.method === 'POST' && url.pathname === '/watchlist/add') {
        return stub.fetch('https://do/add', { method: 'POST', body: await req.text() })
      }
      if (req.method === 'POST' && url.pathname === '/watchlist/remove') {
        return stub.fetch('https://do/remove', { method: 'POST', body: await req.text() })
      }
    }

    if (req.method === 'POST' && url.pathname === '/devices/register') {
      const body = (await req.json().catch(() => null)) as any
      const token = body?.token as string
      if (!token) {
        return bad('token required')
      }
      const devKey = KV_KEYS.DEV_PREFIX + deviceId
      await env.MW_KV.put(devKey, JSON.stringify({ expoToken: token }))
      const set = JSON.parse((await env.MW_KV.get(KV_KEYS.DEVICES)) || '[]')
      if (!set.includes(deviceId)) {
        set.push(deviceId)
        await env.MW_KV.put(KV_KEYS.DEVICES, JSON.stringify(set))
      }
      return json({ ok: true })
    }

    // Sentiment endpoint
    if (req.method === 'GET' && url.pathname === '/sentiment') {
      const syms = (url.searchParams.get('symbols') || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const out: SentimentRow[] = []
      for (const sym of syms) {
        const s = await env.MW_KV.get(KV_KEYS.SENT_LATEST_PREFIX + sym)
        if (s) {
          out.push(JSON.parse(s))
        }
      }
      return json(out)
    }

    if (req.method === 'POST' && url.pathname === '/mock/seed') {
      const key = req.headers.get('X-Cron-Secret')
      if (key !== env.CRON_SECRET) {
        return bad('unauthorized', 401)
      }
      const now = Date.now()
      const sample: DataBundle = {
        banner1h: [{ symbol: 'SOL-USD', price: 150, changePct1h: 4.2, ts: now } as any],
        gainers1m: [{ symbol: 'BTC-USD', price: 62000, changePct1m: 1.1, ts: now } as any],
        gainers3m: [{ symbol: 'ETH-USD', price: 3200, changePct3m: 1.9, ts: now } as any],
        losers3m: [{ symbol: 'DOGE-USD', price: 0.12, changePct3m: -2.5, ts: now } as any],
        volume1h: [{ symbol: 'SOL-USD', price: 150, volumeChangePct1h: 8.0, ts: now } as any],
        ts: now,
      }
      const signals: PumpDump[] = [
        {
          symbol: 'SOL-USD',
          direction: 'PUMP',
          score: 0.91,
          pct_1m: 1.3,
          pct_3m: 2.4,
          vol_z: 2.1,
          streak: 3,
          body: 0.6,
          tags: ['vol-spike', 'streak'],
          ts: now,
        },
      ]
      await env.MW_KV.put(KV_KEYS.DATA, JSON.stringify(sample))
      await env.MW_KV.put(KV_KEYS.SIGNALS, JSON.stringify(signals))
      return json({ ok: true })
    }

    return bad('not found', 404)
  },

  async scheduled(controller: ScheduledController, env: Env) {
    const prices = await fetchCoinbaseTickers()
    const bundle = await buildBundle(env, prices)
    await env.MW_KV.put(KV_KEYS.DATA, JSON.stringify(bundle))

    const latest = JSON.parse((await env.MW_KV.get(KV_KEYS.C_NOW)) || '{}')
    const c1m = JSON.parse((await env.MW_KV.get(KV_KEYS.C_1M)) || '{}')
    const c3m = JSON.parse((await env.MW_KV.get(KV_KEYS.C_3M)) || '{}')
    const vstatsFull = JSON.parse((await env.MW_KV.get(KV_KEYS.VOLSTATS)) || '{}')
    const vstats = Object.fromEntries(
      Object.entries(vstatsFull).map(([k, v]: any) => [k, { mean: v.mean, std: v.std }])
    )
    const streaks = JSON.parse((await env.MW_KV.get(KV_KEYS.PX_G1M)) || '{}')
    const signals = computeSignals({ latest, c1m, c3m, volstats: vstats, streaks })
    await env.MW_KV.put(KV_KEYS.SIGNALS, JSON.stringify(signals))

    const trigSyms = new Set(
      signals.filter((s) => s.score >= 0.85 && s.vol_z >= 2).map((s) => s.symbol)
    )
    if (trigSyms.size) {
      const devices = JSON.parse((await env.MW_KV.get(KV_KEYS.DEVICES)) || '[]') as string[]
      for (const dev of devices) {
        const id = env.WATCHLIST_DO.idFromName(dev)
        const wlRes = await env.WATCHLIST_DO.get(id).fetch('https://do/')
        const wlJson = (await wlRes.json().catch(() => ({ watchlist: [] }))) as {
          watchlist?: string[]
        }
        const watch: string[] = wlJson.watchlist || []
        if (watch.some((s) => trigSyms.has(s))) {
          const devData = JSON.parse((await env.MW_KV.get(KV_KEYS.DEV_PREFIX + dev)) || '{}')
          if (devData?.expoToken && env.ALERTS_Q) {
            await env.ALERTS_Q.send({
              token: devData.expoToken,
              title: 'Moonwalking Signal',
              body: 'Watchlist pump/dump triggered',
              ts: Date.now(),
            })
          }
        }
      }
    }

    // Sentiment ingest/aggregate (stubs return empty until wired)
    const lastTs = Number(await env.MW_KV.get(KV_KEYS.SENT_LAST)) || Date.now() - 2 * 60 * 1000
    const now = Date.now()
    const connectors = [
      new DiscordConnector('', []),
      new RedditConnector('', '', []),
      new TelegramConnector('', []),
    ]
    let posts: RawPost[] = []
    for (const c of connectors) {
      try {
        posts = posts.concat(await c.pullSince(lastTs))
      } catch {}
    }
    await env.MW_KV.put(KV_KEYS.SENT_LAST, String(now))

    for (const sym of PRODUCTS) {
      const row = featuresFromPosts(sym, posts)
      await env.MW_KV.put(KV_KEYS.SENT_LATEST_PREFIX + sym, JSON.stringify(row))
    }
  },

  async queue(batch: MessageBatch<any>, env: Env) {
    const payloads = batch.messages.map((m) => ({
      to: m.body.token,
      sound: 'default',
      title: m.body.title || 'Moonwalking',
      body: m.body.body || 'Signal',
      data: { ts: m.body.ts },
    }))
    try {
      await fetch('https://exp.host/--/api/v2/push/send', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payloads),
      })
    } catch (e) {}
  },
} satisfies ExportedHandler<Env>
