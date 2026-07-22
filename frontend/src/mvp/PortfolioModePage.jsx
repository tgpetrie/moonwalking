import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchPortfolioIntel,
  fetchPortfolioMarketContext,
  fetchCoinbaseOAuthStatus,
  coinbaseAuthorizeUrl,
  disconnectCoinbaseOAuth,
} from "./portfolioApi.js";
import {
  concentrationLabel,
  deriveHoldingRead,
  describePosture,
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

function finiteOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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

  let title = "Connect your Coinbase account";
  let copy =
    "Sign in with Coinbase to load your balances and fills. BHABIT requests read-only access — no trading or transfer scopes are granted.";

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

  // Offer the personal-OAuth path for every recoverable setup state — anything
  // that isn't "another owner's private portfolio", an unsafe key, or a missing
  // backend dependency. Connecting your own Coinbase account resolves all of
  // those (server-config codes included), so it should be the primary CTA.
  const showOAuthButton = Boolean(onConnectCoinbase) && !ownerOnly && !unsafe && !dependency;

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

function HoldingIntel({ intel }) {
  if (!intel) return null;
  const posture = describePosture(intel);
  const history = intel.history || {};
  const board = intel.board || {};
  const hasHistory = history.sample_size >= 5 && history.follow_through_pct !== null
    && history.follow_through_pct !== undefined;
  const change1m = finiteOrNull(board.change_1m);
  const change3m = finiteOrNull(board.change_3m);
  const volChange = finiteOrNull(board.volume_change_1h_pct);
  const hasBoard = change1m !== null || change3m !== null || volChange !== null;

  return (
    <div className="mw-holding-intel">
      <div className="mw-holding-intel__header">
        <span className={`mw-posture-chip is-${posture.tone}`}>
          {posture.label}
          {posture.confidence !== null ? ` · ${posture.confidence}` : ""}
        </span>
        {intel.active_alert_count ? (
          <span className="mw-holding-intel__alerts">
            {intel.active_alert_count} active alert{intel.active_alert_count === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
      {posture.shortRead ? (
        <p className="mw-holding-intel__read">{posture.shortRead}</p>
      ) : null}
      {hasBoard ? (
        <div className="mw-holding-intel__board">
          {change1m !== null ? <span>1m {percent(change1m, { signed: true })}</span> : null}
          {change3m !== null ? <span>3m {percent(change3m, { signed: true })}</span> : null}
          {volChange !== null ? <span>1h vol {percent(volChange, { signed: true })}</span> : null}
        </div>
      ) : null}
      {hasHistory ? (
        <p className="mw-holding-intel__history">
          Historical follow-through <strong>{percent(history.follow_through_pct)}</strong>
          {" "}across {history.sample_size} comparable signals
          {finiteOrNull(history.median_favorable_pct) !== null
            ? ` · median favorable ${percent(history.median_favorable_pct, { signed: true })}`
            : ""}
        </p>
      ) : (
        <p className="mw-holding-intel__history is-muted">
          Not enough comparable-signal history yet.
        </p>
      )}
    </div>
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

      <HoldingIntel intel={holding.intel} />

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
              {orders.map((order) => {
                const intel = order.intel || {};
                const hint = intel.order_type_hint
                  ? intel.order_type_hint.replace(/_/g, " ")
                  : null;
                const distance = finiteOrNull(intel.distance_from_current_pct);
                return (
                  <Fragment key={order.order_id}>
                    <tr>
                      <td><strong>{order.symbol}</strong><span>{dateTime(order.created_at)}</span></td>
                      <td>{order.side || "Unavailable"}</td>
                      <td>{number(order.base_size ?? order.quote_size)}</td>
                      <td>{money(order.limit_price)}</td>
                      <td>{order.status}</td>
                    </tr>
                    {hint || intel.context ? (
                      <tr className="mw-order-intel-row">
                        <td colSpan={5}>
                          {hint ? <span className="mw-order-intel-tag">{hint}</span> : null}
                          {distance !== null ? (
                            <span className="mw-order-intel-distance">
                              {percent(distance, { signed: true })} from current
                            </span>
                          ) : null}
                          {intel.context ? (
                            <span className="mw-order-intel-context">{intel.context}</span>
                          ) : null}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
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
  const [oauthConnected, setOauthConnected] = useState(false);
  const [state, setState] = useState({ loading: true, error: null });

  const refreshOAuthStatus = useCallback(async () => {
    try {
      const status = await fetchCoinbaseOAuthStatus();
      setOauthConnected(Boolean(status?.connected));
    } catch {
      setOauthConnected(false);
    }
  }, []);

  const load = useCallback(async ({ force = false } = {}) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    const [portfolioResult, marketResult] = await Promise.allSettled([
      fetchPortfolioIntel({ force }),
      fetchPortfolioMarketContext(),
    ]);
    refreshOAuthStatus();
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
  }, [refreshOAuthStatus]);

  // Full-page navigation: the browser is handed to Coinbase's consent screen and
  // returned to /mvp/portfolio by the backend callback once tokens are stored.
  const handleConnectCoinbase = useCallback(() => {
    window.location.href = coinbaseAuthorizeUrl();
  }, []);

  const handleDisconnectCoinbase = useCallback(async () => {
    if (!window.confirm("Disconnect your Coinbase OAuth connection?")) return;
    try {
      await disconnectCoinbaseOAuth();
      setOauthConnected(false);
      load({ force: true });
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
  const intelSummary = portfolio?.intel_summary || null;
  const intelAvailable = Boolean(portfolio?.intel_available);

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
          {oauthConnected ? (
            <button type="button" className="mw-button mw-button--ghost" onClick={handleDisconnectCoinbase}>
              Disconnect OAuth
            </button>
          ) : null}
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
          {intelAvailable && intelSummary ? (
            <span className="mw-intel-coverage" title="Holdings with a live BHABIT signal">
              Signal coverage {percent(intelSummary.signal_coverage_pct)}
              {" · "}
              {intelSummary.holdings_with_signals}/{intelSummary.total_holdings} holdings
            </span>
          ) : (
            <span>Labels describe current evidence, not promised outcomes.</span>
          )}
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
