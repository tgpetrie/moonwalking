import React from "react";
import { useSentiment } from "../../hooks/useSentiment";

const formatPercent = (value) =>
  typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—";

const formatScore = (value) =>
  typeof value === "number" ? value.toFixed(2) : "—";

export default function SentimentCard({ symbol, ttlSec = 30 }) {
  const { data, error, loading } = useSentiment(symbol, ttlSec);

  if (loading && !data) return <div className="text-xs opacity-70">Loading sentiment…</div>;
  if (error && !data) return <div className="text-xs opacity-70">Unable to load sentiment.</div>;

  const overview = data?.overview ?? {};
  const scores = data?.scores ?? {};
  const social = data?.social ?? {};
  const news = data?.news ?? {};
  const onchain = data?.onchain ?? {};

  return (
    <div className="space-y-3 text-sm">
      <section>
        <div className="opacity-70 text-xs mb-1">Overview</div>
        {(overview.score != null || overview.label) ? (
          <div>
            Score {formatScore(overview.score)} · {overview.label ?? "—"}
          </div>
        ) : (
          <div className="opacity-50">No overview available</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">Scores</div>
        {(scores.bulls ?? scores.bears ?? scores.neutral) ? (
          <div>
            Bulls {scores.bulls ?? 0} · Bears {scores.bears ?? 0} · Neutral {scores.neutral ?? 0}
          </div>
        ) : (
          <div className="opacity-50">No scores yet</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">Social</div>
        {(social.buzz || social.mentions || (social.top && social.top.length)) ? (
          <div className="space-y-1">
            <div>
              Buzz {social.buzz ?? 0} · Mentions {social.mentions ?? 0} · Sources {social.sources ?? 0}
            </div>
            {social.top?.slice(0, 5).map((item, idx) => (
              <div key={idx} className="flex justify-between text-xs">
                <span className="opacity-80">{item.source}</span>
                <span className="tabular-nums">{item.count}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="opacity-50">No social signals</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">News</div>
        {news.articles?.length ? (
          news.articles.slice(0, 4).map((article, idx) => (
            <a
              key={`${article.url || idx}`}
              href={article.url || '#'}
              target="_blank"
              rel="noreferrer"
              className="block truncate hover:underline"
            >
              {article.title || article.url || 'Untitled headline'}
            </a>
          ))
        ) : (
          <div className="opacity-50">No recent headlines</div>
        )}
      </section>

      <section>
        <div className="opacity-70 text-xs mb-1">On-chain</div>
        {(onchain.activeAddrs || onchain.netflow) ? (
          <div>
            Active addrs {onchain.activeAddrs ?? 0} · Netflow {onchain.netflow ?? 0}
          </div>
        ) : (
          <div className="opacity-50">No on-chain data</div>
        )}
      </section>
    </div>
  );
}
