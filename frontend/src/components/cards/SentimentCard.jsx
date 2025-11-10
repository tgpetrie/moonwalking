import React from "react";
import { useSentiment } from "../../hooks/useSentiment.js";

export default function SentimentCard({ symbol, ttlSec = 30 }) {
  const { data, error, isLoading } = useSentiment(symbol, ttlSec);

  if (!symbol) return <div className="text-xs opacity-70">No asset selected.</div>;
  if (isLoading && !data) return <div className="text-xs opacity-70">Loading sentiment…</div>;
  if (error && !data) return <div className="text-xs opacity-70">Unable to load sentiment.</div>;

  const o = data?.overview,
    sc = data?.scores,
    so = data?.social,
    nw = data?.news,
    oc = data?.onchain;

  const num = (v) =>
    typeof v === "number"
      ? Math.abs(v) >= 100
        ? v.toFixed(0)
        : Math.abs(v) >= 10
        ? v.toFixed(1)
        : v.toFixed(2)
      : v;

  return (
    <div className="space-y-3 text-sm">
      <section>
        <div className="opacity-70 text-xs mb-1">Overview</div>
        {o?.score != null || o?.label ? (
          <div>
            Score {num(o?.score)} · {o?.label ?? "—"}
          </div>
        ) : (
          <div className="opacity-50">No overview available</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">Scores</div>
        {sc ? (
          <div>
            Bulls {sc.bulls ?? 0} · Bears {sc.bears ?? 0} · Neutral {sc.neutral ?? 0}
          </div>
        ) : (
          <div className="opacity-50">No scores yet</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">Social</div>
        {so && (so.buzz || so.mentions || (so.top && so.top.length)) ? (
          <div className="space-y-1">
            <div>
              Buzz {so.buzz ?? 0} · Mentions {so.mentions ?? 0} · Sources {so.sources ?? 0}
            </div>
            {so.top?.slice(0, 5).map((t, i) => (
              <div key={i} className="flex justify-between">
                <span className="opacity-80">{t.source}</span>
                <span className="tabular-nums">{t.count}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="opacity-50">No social signals</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">News</div>
        {nw?.articles?.length ? (
          nw.articles.slice(0, 4).map((a, i) => (
            <a
              key={i}
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="block truncate hover:underline"
            >
              {a.title || a.url}
            </a>
          ))
        ) : (
          <div className="opacity-50">No recent headlines</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">On-chain</div>
        {oc && (oc.activeAddrs || oc.netflow) ? (
          <div>
            Active addrs {oc.activeAddrs ?? 0} · Netflow {oc.netflow ?? 0}
          </div>
        ) : (
          <div className="opacity-50">No on-chain data</div>
        )}
      </section>
    </div>
  );
}
