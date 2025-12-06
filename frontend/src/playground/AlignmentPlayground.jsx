// frontend/src/playground/AlignmentPlayground.jsx
import React from "react";
import TokenRow from "../components/TokenRow.jsx";

const mock1mFew = [
  {
    symbol: "BTC",
    name: "Bitcoin",
    current_price: 98420.12,
    price_1m_ago: 97900.0,
    change_1m: 0.53,
  },
  {
    symbol: "ETH",
    name: "Ethereum",
    current_price: 4120.55,
    price_1m_ago: 4050.0,
    change_1m: 1.74,
  },
];

const mock1mMany = [
  {
    symbol: "SOL",
    name: "Solana",
    current_price: 186.32,
    price_1m_ago: 180.0,
    change_1m: 3.51,
  },
  {
    symbol: "LINK",
    name: "Chainlink",
    current_price: 18.03,
    price_1m_ago: 17.5,
    change_1m: 3.03,
  },
  {
    symbol: "DOGE",
    name: "Dogecoin",
    current_price: 0.189,
    price_1m_ago: 0.183,
    change_1m: 3.28,
  },
  {
    symbol: "OP",
    name: "Optimism",
    current_price: 3.42,
    price_1m_ago: 3.3,
    change_1m: 3.64,
  },
  {
    symbol: "ARB",
    name: "Arbitrum",
    current_price: 1.63,
    price_1m_ago: 1.58,
    change_1m: 3.16,
  },
];

const mockGainers3m = mock1mMany.slice(0, 4);
const mockLosers3m = [
  {
    symbol: "BONK",
    name: "Bonk",
    current_price: 0.000026,
    price_3m_ago: 0.000028,
    change_3m: -7.14,
  },
  {
    symbol: "PEPE",
    name: "Pepe",
    current_price: 0.000011,
    price_3m_ago: 0.000012,
    change_3m: -8.33,
  },
  {
    symbol: "SUI",
    name: "Sui",
    current_price: 1.19,
    price_3m_ago: 1.28,
    change_3m: -7.03,
  },
  {
    symbol: "APT",
    name: "Aptos",
    current_price: 8.41,
    price_3m_ago: 9.02,
    change_3m: -6.75,
  },
];

const mockWatchlist = [mock1mMany[0], mockGainers3m[1], mockLosers3m[2]];

export function AlignmentPlayground() {
  return (
    <main className="bh-board bh-alignment-playground">
      {/* 1m few – full-width */}
      <section className="bh-board-row-full">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">1-min Gainers (≤4, full-width)</h2>
          <div className="bh-table">
            {mock1mFew.map((t, i) => (
              <TokenRow
                key={`1m-few-${t.symbol}`}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_1m_ago}
                changePct={t.change_1m}
                onInfo={() => {}}
              />
            ))}
          </div>
        </div>
      </section>

      {/* 1m many – two-column */}
      <section className="bh-board-row-halves">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">1-min Gainers (>4, left)</h2>
          <div className="bh-table">
            {mock1mMany.slice(0, 3).map((t, i) => (
              <TokenRow
                key={`1m-left-${t.symbol}`}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_1m_ago}
                changePct={t.change_1m}
                onInfo={() => {}}
              />
            ))}
          </div>
        </div>

        <div className="bh-board-panel">
          <h2 className="bh-section-header bh-section-header--ghost">
            {/* ghost header keeps rhythm */}
          </h2>
          <div className="bh-table">
            {mock1mMany.slice(3).map((t, i) => (
              <TokenRow
                key={`1m-right-${t.symbol}`}
                rank={3 + i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_1m_ago}
                changePct={t.change_1m}
                onInfo={() => {}}
              />
            ))}
          </div>
        </div>
      </section>

      {/* 3m grid – gainers vs losers */}
      <section className="bh-board-row-halves">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">Top Gainers (3m)</h2>
          <div className="bh-table">
            {mockGainers3m.map((t, i) => (
              <TokenRow
                key={`3m-g-${t.symbol}`}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_3m_ago ?? t.price_1m_ago ?? null}
                changePct={3 + i}
                onInfo={() => {}}
                rowType="gainer"
              />
            ))}
          </div>
        </div>
        <div className="bh-board-panel">
          <h2 className="bh-section-header bh-section-header--losers">
            Top Losers (3m)
          </h2>
          <div className="bh-table">
            {mockLosers3m.map((t, i) => (
              <TokenRow
                key={`3m-l-${t.symbol}`}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_3m_ago}
                changePct={t.change_3m}
                onInfo={() => {}}
                rowType="loser"
              />
            ))}
          </div>
        </div>
      </section>

      {/* Watchlist – full width */}
      <section className="bh-board-row-full">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">Watchlist</h2>
          <div className="bh-table">
            {mockWatchlist.map((t, i) => (
              <TokenRow
                key={`wl-${t.symbol}`}
                rank={i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={t.price_1m_ago ?? t.price_3m_ago ?? null}
                changePct={i === 0 ? 2.3 : i === 1 ? -1.7 : 0.5}
                onInfo={() => {}}
                rowType={i === 1 ? "loser" : "gainer"}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
