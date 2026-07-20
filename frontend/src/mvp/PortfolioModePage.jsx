import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchPortfolio, fetchPortfolioMarketContext } from "./portfolioApi.js";
import {
  concentrationLabel,
  deriveHoldingRead,
  indexLiveRankings,
} from "./portfolioSignals.js";

const moneyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

function money(value) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? moneyFormatter.format(parsed) : "Unavailable";
}

function number(value, maximumFractionDigits = 8) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(parsed);
}

function percent(value, { signed = false } = {}) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "Unavailable";
  return `${signed && parsed > 0 ? "+" : ""}${parsed.toFixed(2)}%`;
}

function dateTime(value) {
  if (!value) return "Pending";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Pending";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function CostBasisStatus({ holding }) {
  const basis = holding?.cost_basis || {};
  if (holding?.is_cash) return <span className="mw-portfolio-basis is-complete">Cash</span>;
  const label =
    basis.status === "complete"
      ? "Complete"
      : basis.status === "partial"
        ? "Partial"
        : "Unavailable";
  return (
    <span className={`mw-portfolio-basis is-${basis.status || "unavailable"}`}>
      {label} cost basis
    </span>
  );
}

function SetupState({ state, onRetry, onConnectCoinbase }) {
  const code = state?.code || "coinbase_not_configured";
  const ownerOnly = code === "portfolio_owner_only";
  const unsafe = code === "unsafe_coinbase_permissions";
  const dependency = code === "coinbase_auth_dependency_missing";

  let title = "Connect a View-only Coinbase portfolio";
  let copy =
    "Add the owner email, Coinbase key name, and private key as encrypted Railway variables. The key must be scoped to one portfolio with View only.";

  if (ownerOnly) {
    title = "This portfolio is private";
    copy = "Sign in with the configured owner account to view Coinbase balances and fills.";
  } else if (unsafe) {
    title = "Unsafe Coinbase permissions blocked";
    copy = "Replace this key with a portfolio-specific key that has View enabled and both Trade and Transfer disabled.";
  } else if (dependency) {
    title = "Coinbase authentication support is missing";
    copy = "Install the backend deployment requirements, then restart the service.";
  }

  const showOAuthButton = !ownerOnly && code === "coinbase_not_configured" && onConnectCoinbase;

  return (
    <section className="mw-panel mw-portfolio-setup">
      <div className="mw-portfolio-setup__mark" aria-hidden="true">P</div>
      <div>
        <p className="mw-eyebrow">Private Portfolio Mode</p>
        <h2>{title}</h2>
        <p>{state?.error || copy}</p>
        {!ownerOnly && !showOAuthButton ? (
          <div className="mw-portfolio-secret-list" aria-label="Required server variables">
            <code>COINBASE_PORTFOLIO_OWNER_EMAIL</code>
            <code>COINBASE_API_KEY_NAME</code>
            <code>COINBASE_API_KEY_SECRET</code>
          </div>
        ) : null}
        <div className="mw-inline-actions">
          {showOAuthButton ? (
            <button
              type="button"
              className="mw-button mw-button--primary"
              onClick={onConnectCoinbase}
            >
              Connect Coinbase OAuth
            </button>
          ) : (
            <button type="button" className="mw-button mw-button--primary" onClick={onRetry}>
              Check Again
            </button>
          )}
          <span className="mw-portfolio-safety-note">No trading routes are enabled.</span>
        </div>
      </div>
    </section>
  );
}

function HoldingCard({ holding, liveRow }) {
  const read = deriveHoldingRead(holding, liveRow);
  const basis = holding.cost_basis || {};
  const pnlKnown = holding.unrealized_pnl_usd !== null
    && holding.unrealized_pnl_usd !== undefined
    && holding.unrealized_pnl_usd !== ""
    && Number.isFinite(Number(holding.unrealized_pnl_usd));

  return (
    <article className="mw-panel mw-holding-card">
      <div className="mw-holding-card__topline">
        <div>
          <span className="mw-holding-card__symbol">{holding.symbol}</span>
          <span className="mw-holding-card__name">{holding.name}</span>
        </div>
        <span className={`mw-holding-read is-${read.tone}`}>
          {read.label}{read.score !== null ? ` · ${read.score}` : ""}
        </span>
      </div>

      <p className="mw-holding-card__read-copy">{read.explanation}</p>

      <div className="mw-holding-card__metrics">
        <div><span>Value</span><strong>{money(holding.market_value_usd)}</strong></div>
        <div><span>Quantity</span><strong>{number(holding.quantity)}</strong></div>
        <div><span>Allocation</span><strong>{percent(holding.allocation_pct)}</strong></div>
        <div><span>24h move</span><strong>{percent(holding.price_change_24h_pct, { signed: true })}</strong></div>
      </div>

      <div className="mw-holding-card__detail-grid">
        <div><span>Position impact</span><strong>{concentrationLabel(holding.allocation_pct)}</strong></div>
        <div>
          <span>Unrealized result</span>
          <strong className={pnlKnown && Number(holding.unrealized_pnl_usd) < 0 ? "is-negative" : "is-positive"}>
            {pnlKnown
              ? `${money(holding.unrealized_pnl_usd)} · ${percent(holding.unrealized_pnl_pct, { signed: true })}`
              : "Unknown until cost basis is complete"}
          </strong>
        </div>
        <div>
          <span>Cost basis</span>
          <strong>
            <CostBasisStatus holding={holding} />
            {basis.average_price ? ` · ${money(basis.average_price)} average` : ""}
          </strong>
        </div>
        <div><span>Historical plan</span><strong>Not enough proof</strong></div>
      </div>

      {basis.status === "partial" ? (
        <p className="mw-holding-card__truth-note">
          {number(basis.unknown_quantity)} {holding.symbol} has no verified Advanced Trade fill cost. It may have been transferred in, so BHABIT will not invent an acquisition price.
        </p>
      ) : null}
      <div className="mw-holding-card__plan-lock">
        Protection levels, target ranges, and historical probabilities stay locked until comparable-event evidence is statistically adequate.
      </div>
    </article>
  );
}

function OpenOrders({ orders }) {
  return (
    <section className="mw-panel mw-portfolio-orders">
      <div className="mw-panel__header">
        <div><h3>Open Orders</h3><span>Read-only reconciliation</span></div>
        <span className="mw-status-chip">{orders.length ? `${orders.length} open` : "None open"}</span>
      </div>
      {orders.length ? (
        <div className="mw-table-shell">
          <table className="mw-table">
            <thead><tr><th>Asset</th><th>Side</th><th>Size</th><th>Limit</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.order_id}>
                  <td><strong>{order.symbol}</strong><span>{dateTime(order.created_at)}</span></td>
                  <td>{order.side || "Unavailable"}</td>
                  <td>{number(order.base_size ?? order.quote_size)}</td>
                  <td>{money(order.limit_price)}</td>
                  <td>{order.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="mw-portfolio-empty-copy">No open Coinbase orders were returned for this portfolio.</p>}
    </section>
  );
}

export default function PortfolioModePage() {
  const [portfolio, setPortfolio] = useState(null);
  const [marketContext, setMarketContext] = useState(null);
  const [state, setState] = useState({ loading: true, error: null });

  const load = useCallback(async ({ force = false } = {}) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    const [portfolioResult, marketResult] = await Promise.allSettled([
      fetchPortfolio({ force }),
      fetchPortfolioMarketContext(),
    ]);
    if (marketResult.status === "fulfilled") setMarketContext(marketResult.value);
    if (portfolioResult.status === "fulfilled") {
      setPortfolio(portfolioResult.value);
      setState({ loading: false, error: null });
      return;
    }
    setState({
      loading: false,
      error: portfolioResult.reason?.payload || {
        code: "coinbase_unavailable",
        error: portfolioResult.reason?.message || "Portfolio data is unavailable.",
      },
    });
  }, []);

  const handleDisconnectCoinbase = useCallback(async () => {
    if (!window.confirm("Disconnect your Coinbase OAuth connection?")) return;

    try {
      const response = await fetch("/api/oauth/coinbase/disconnect", { method: "POST" });
      if (response.ok) {
        load({ force: true });
      } else {
        setState((current) => ({
          ...current,
          error: {
            code: "disconnect_error",
            error: "Failed to disconnect Coinbase OAuth.",
          },
        }));
      }
    } catch (error) {
      console.error("Failed to disconnect Coinbase OAuth:", error);
      setState((current) => ({
        ...current,
        error: {
          code: "disconnect_error",
          error: "Failed to disconnect Coinbase OAuth.",
        },
      }));
    }
  }, [load]);

  useEffect(() => { load(); }, [load]);

  const rankings = useMemo(() => indexLiveRankings(marketContext), [marketContext]);
  const holdings = Array.isArray(portfolio?.holdings) ? portfolio.holdings : [];
  const cryptoHoldings = holdings.filter((holding) => !holding.is_cash);
  const cashHoldings = holdings.filter((holding) => holding.is_cash);
  const summary = portfolio?.summary || {};

  if (state.loading && !portfolio) {
    return (
      <section className="mw-panel mw-portfolio-loading" aria-live="polite">
        <p className="mw-eyebrow">Private Portfolio Mode</p>
        <h2>Loading Coinbase portfolio</h2>
        <p>Checking owner access, View-only permissions, balances, and fills.</p>
      </section>
    );
  }
  if (state.error && !portfolio) {
    return <SetupState state={state.error} onRetry={() => load({ force: true })} onConnectCoinbase={handleConnectCoinbase} />;
  }

  return (
    <div className="mw-stack mw-portfolio-mode">
      <section className="mw-panel mw-portfolio-command">
        <div>
          <div className="mw-portfolio-command__eyebrow-row">
            <p className="mw-eyebrow">Private Portfolio Mode</p>
            <span className="mw-status-chip mw-status-chip--accent">View only</span>
            {portfolio?.status === "stale" ? <span className="mw-status-chip">Stale</span> : null}
          </div>
          <h2>Your Coinbase trading cockpit</h2>
          <p>Balances, cost-basis truth, and BHABIT market-condition reads. No trading or transfer action exists in Stage 1.</p>
        </div>
        <div className="mw-portfolio-command__refresh">
          <span>Updated {dateTime(portfolio?.updated_at)}</span>
          <button type="button" className="mw-button mw-button--ghost" disabled={state.loading} onClick={() => load({ force: true })}>
            {state.loading ? "Refreshing" : "Refresh Coinbase"}
          </button>
          <button type="button" className="mw-button mw-button--ghost" onClick={handleDisconnectCoinbase}>
            Disconnect OAuth
          </button>
        </div>
      </section>

      {state.error ? <p className="mw-auth-feedback mw-auth-feedback--error">{state.error.error}</p> : null}

      <section className="mw-portfolio-summary" aria-label="Portfolio summary">
        <article className="mw-panel mw-portfolio-stat is-primary"><span>Total portfolio</span><strong>{money(summary.total_value_usd)}</strong><small>{cryptoHoldings.length} crypto holdings</small></article>
        <article className="mw-panel mw-portfolio-stat"><span>Cash available</span><strong>{money(summary.cash_value_usd)}</strong><small>{cashHoldings.map((holding) => holding.symbol).join(" · ") || "No cash balance"}</small></article>
        <article className="mw-panel mw-portfolio-stat"><span>Known unrealized P&amp;L</span><strong className={Number(summary.known_unrealized_pnl_usd) < 0 ? "is-negative" : "is-positive"}>{money(summary.known_unrealized_pnl_usd)}</strong><small>Only complete cost basis included</small></article>
        <article className="mw-panel mw-portfolio-stat"><span>Cost-basis coverage</span><strong>{percent(summary.cost_basis_coverage_pct)}</strong><small>{summary.open_order_count || 0} open orders</small></article>
      </section>

      <section className="mw-portfolio-holdings" aria-label="Portfolio holdings">
        <div className="mw-portfolio-section-title">
          <div><p className="mw-eyebrow">Holdings</p><h2>One uncomplicated answer per position</h2></div>
          <span>Labels describe current evidence, not promised outcomes.</span>
        </div>
        {cryptoHoldings.length ? (
          <div className="mw-portfolio-holding-grid">
            {cryptoHoldings.map((holding) => (
              <HoldingCard key={holding.account_id || holding.symbol} holding={holding} liveRow={rankings[holding.symbol]} />
            ))}
          </div>
        ) : <article className="mw-panel mw-portfolio-empty-copy">Coinbase returned no non-cash holdings for this portfolio.</article>}
      </section>

      <OpenOrders orders={Array.isArray(portfolio?.open_orders) ? portfolio.open_orders : []} />

      <section className="mw-panel mw-portfolio-proof">
        <div><p className="mw-eyebrow">Historical calibration</p><h3>Not enough proof</h3></div>
        <p>BHABIT is collecting forward outcomes, but Stage 1 does not yet claim target probabilities, protection prices, or expected results for portfolio holdings.</p>
      </section>
    </div>
  );
}
