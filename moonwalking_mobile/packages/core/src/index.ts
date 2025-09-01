
export type MarketRow = {
  symbol: string;
  price: number;
  changePct1m?: number;
  changePct3m?: number;
  changePct1h?: number;
  volumeChangePct1h?: number;
  px?: number;
  ts: number;
};

export type DataBundle = {
  banner1h: MarketRow[];
  gainers1m: MarketRow[];
  gainers3m: MarketRow[];
  losers3m: MarketRow[];
  volume1h: MarketRow[];
  ts: number;
};

export type PumpDump = {
  symbol: string;
  direction: "PUMP" | "DUMP";
  score: number;
  pct_1m: number;
  pct_3m: number;
  vol_z: number;
  streak: number;
  body: number;
  tags: string[];
  ts: number;
};

export type RawPost = { id:string; ts:number; text:string; src:'discord'|'reddit'|'telegram'; meta?:any };

export type SentimentRow = {
  symbol: string;
  ts: number;
  mentions: number;
  sent_score: number;
  pos: number;
  neg: number;
  velocity: number;
  source_mix: Record<string, number>;
};

export const theme = {
  colors: {
    bg: "#0A0A0D",
    surface: "rgba(255,255,255,0.02)",
    purple: "#8B5CF6",
    orange: "#FF6A00",
    pink: "#FF2D95",
    blue: "#3B82F6",
    white: "#FFFFFF",
    gray: "#9CA3AF",
    line: "rgba(255,255,255,0.06)"
  },
  spacing: (n:number)=> n*8,
  radius: { sm:8, md:12, lg:16, xl:24 }
};

export function fmtPct(n?: number){ return (n==null)? "" : `${n.toFixed(2)}%`; }
export function fmtPrice(n?: number){
  if (n==null) return "";
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(2);
  return n.toFixed(4);
}
