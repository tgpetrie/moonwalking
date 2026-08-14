import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import { getBackendBase } from "../config/api.js";
import PortfolioModePage from "./PortfolioModePage.jsx";
import ScorecardPage from "../components/ScorecardPage.jsx";
import "../styles/mvp-shell.css";

const APP_DASHBOARD_PATH = "/app/dashboard";
const APP_WATCHLISTS_PATH = "/app/watchlists";
const APP_PORTFOLIO_PATH = "/app/portfolio";
const APP_SCORECARD_PATH = "/app/scorecard";
const APP_SETTINGS_PATH = "/app/settings";
const PUBLIC_SCORECARD_PATH = "/scorecard";

const protectedPaths = new Set([
  APP_DASHBOARD_PATH,
  APP_WATCHLISTS_PATH,
  APP_PORTFOLIO_PATH,
  APP_SCORECARD_PATH,
  APP_SETTINGS_PATH,
]);

const legacyMemberRouteMap = {
  "/watchlists": APP_WATCHLISTS_PATH,
  "/portfolio": APP_PORTFOLIO_PATH,
  "/settings": APP_SETTINGS_PATH,
};

const publicShowcase = [
  {
    title: "Growth Radar",
    subtitle: "A public sample watchlist for high-conviction tech names.",
    tags: ["Public", "Tech", "Momentum"],
  },
  {
    title: "Macro Pulse",
    subtitle: "Track the major indicators you want available on every device.",
    tags: ["Public", "Macro", "Daily"],
  },
  {
    title: "Creator Tools",
    subtitle: "A teaser list for founders following the AI tooling landscape.",
    tags: ["Public", "AI", "Tools"],
  },
];

const tierCards = [
  {
    name: "Public Tier",
    summary: "Browse the product, explore examples, and view public portfolios.",
    bullets: ["Homepage access", "Public examples", "Profile discovery"],
  },
  {
    name: "Free Account",
    summary: "Create, manage, and sync your watchlists across devices.",
    bullets: ["Saved watchlists", "Dashboard access", "Portfolio basics"],
  },
  {
    name: "Premium Later",
    summary: "Unlock deeper controls once the core workflow is stable.",
    bullets: ["More watchlists", "Private sharing", "Analytics"],
  },
];

const initialWatchlists = [
  {
    id: "tech-stocks",
    name: "Tech Stocks",
    description: "High-conviction names tied to AI infrastructure and software.",
    notes:
      "Prioritize companies with durable margins, obvious platform leverage, and room for multiple expansion.",
    updatedAt: "2026-03-11T15:02:00.000Z",
    items: [
      {
        id: "tsla",
        itemKey: "TSLA",
        itemType: "Stock",
        title: "Tesla",
        notes: "EV leader, watch delivery cadence and autonomy commentary.",
        position: 1,
      },
      {
        id: "nvda",
        itemKey: "NVDA",
        itemType: "Stock",
        title: "Nvidia",
        notes: "AI demand proxy with hyperscaler exposure.",
        position: 2,
      },
      {
        id: "msft",
        itemKey: "MSFT",
        itemType: "Stock",
        title: "Microsoft",
        notes: "Cloud + copilots; track enterprise AI monetization.",
        position: 3,
      },
    ],
  },
  {
    id: "crypto-core",
    name: "Crypto",
    description: "Liquid core assets and infrastructure names.",
    notes:
      "Focus on liquidity, regulatory catalysts, and whether moves are broad or isolated.",
    updatedAt: "2026-03-11T13:24:00.000Z",
    items: [
      {
        id: "btc",
        itemKey: "BTC",
        itemType: "Crypto",
        title: "Bitcoin",
        notes: "Long-term benchmark asset.",
        position: 1,
      },
      {
        id: "eth",
        itemKey: "ETH",
        itemType: "Crypto",
        title: "Ethereum",
        notes: "Watch fee trends and ETF narrative.",
        position: 2,
      },
      {
        id: "sol",
        itemKey: "SOL",
        itemType: "Crypto",
        title: "Solana",
        notes: "Monitor developer momentum and outages.",
        position: 3,
      },
    ],
  },
  {
    id: "ai-tools",
    name: "AI Tools",
    description: "Private market and public-adjacent tools to revisit weekly.",
    notes:
      "Mix of public comps and private products worth tracking for competitive positioning.",
    updatedAt: "2026-03-10T21:48:00.000Z",
    items: [
      {
        id: "openai",
        itemKey: "OPENAI",
        itemType: "Private",
        title: "OpenAI",
        notes: "Follow platform launches and enterprise adoption.",
        position: 1,
      },
      {
        id: "anthropic",
        itemKey: "ANTHROPIC",
        itemType: "Private",
        title: "Anthropic",
        notes: "Track model releases and API traction.",
        position: 2,
      },
      {
        id: "adbe",
        itemKey: "ADBE",
        itemType: "Stock",
        title: "Adobe",
        notes: "Creative workflow moat with AI distribution leverage.",
        position: 3,
      },
    ],
  },
];

const initialPortfolio = {
  displayName: "Jane Doe",
  bio: "Investor tracking growth sectors, platform companies, and category-defining tools.",
  website: "https://example.com",
  visibility: "public",
  headline: "Building a portable research workflow",
  featuredWatchlistIds: ["tech-stocks", "crypto-core"],
};

const initialSettings = {
  notifications: true,
  marketAlerts: false,
  rememberSessions: true,
  theme: "midnight",
};

const initialSessions = [
  {
    id: "session-macbook",
    deviceName: "MacBook Pro",
    location: "San Francisco, CA",
    lastSeenAt: "2026-03-11T15:06:00.000Z",
  },
  {
    id: "session-phone",
    deviceName: "iPhone",
    location: "Austin, TX",
    lastSeenAt: "2026-03-11T12:44:00.000Z",
  },
  {
    id: "session-office",
    deviceName: "Work Chrome",
    location: "Remote",
    lastSeenAt: "2026-03-10T20:12:00.000Z",
  },
];

const defaultSession = {
  isAuthenticated: false,
  name: "Jane Doe",
  email: "jane@example.com",
  username: "janedoe",
  plan: "Free Account",
};

const API_BASE = getBackendBase();

function buildApiUrl(pathname) {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${API_BASE}${path}`;
}

async function apiRequest(pathname, options = {}) {
  const { method = "GET", body } = options;
  const requestOptions = {
    method,
    credentials: "include",
    headers: {},
  };
  if (body !== undefined) {
    requestOptions.headers["Content-Type"] = "application/json";
    requestOptions.body = JSON.stringify(body);
  }

  const response = await fetch(buildApiUrl(pathname), requestOptions);
  const contentType = response.headers.get("content-type") || "";
  let payload = {};
  if (contentType.includes("application/json")) {
    payload = await response.json();
  }
  if (!response.ok) {
    const message =
      payload?.error ||
      payload?.message ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function classNames(...values) {
  return values.filter(Boolean).join(" ");
}

function createId(prefix) {
  const token = Math.random().toString(36).slice(2, 9);
  return `${prefix}-${token}`;
}

function slugifyUsername(value) {
  return String(value || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "watcher";
}

function titleize(value) {
  return String(value || "")
    .toLowerCase()
    .split(/[\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeSymbol(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.]/g, "");
}

function formatItemTitle(symbol) {
  if (!symbol) return "New Item";
  if (symbol.length <= 5 && !symbol.includes(".")) return symbol;
  return titleize(symbol.replace(/\./g, " "));
}

function guessItemType(symbol) {
  if (!symbol) return "Asset";
  if (["BTC", "ETH", "SOL"].includes(symbol)) return "Crypto";
  if (symbol.length <= 5) return "Stock";
  return "Private";
}

function formatRelativeTime(value) {
  if (!value) return "Just now";
  const ts = new Date(value).getTime();
  const deltaMinutes = Math.max(1, Math.round((Date.now() - ts) / 60000));
  if (deltaMinutes < 60) return `${deltaMinutes} min${deltaMinutes === 1 ? "" : "s"} ago`;
  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) return `${deltaHours} hr${deltaHours === 1 ? "" : "s"} ago`;
  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays} day${deltaDays === 1 ? "" : "s"} ago`;
}

function formatDateTime(value) {
  if (!value) return "Pending";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function initials(name) {
  const parts = String(name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2);
  if (!parts.length) return "MW";
  return parts.map((part) => part.charAt(0).toUpperCase()).join("");
}

function matchRoute(pathname) {
  if (
    protectedPaths.has(pathname) ||
    pathname === "/" ||
    pathname === PUBLIC_SCORECARD_PATH ||
    pathname === "/login" ||
    pathname === "/signup" ||
    Object.prototype.hasOwnProperty.call(legacyMemberRouteMap, pathname)
  ) {
    return { name: pathname, params: {} };
  }
  if (pathname.startsWith("/u/")) {
    return {
      name: "/u/:username",
      params: { username: decodeURIComponent(pathname.replace("/u/", "") || "janedoe") },
    };
  }
  return { name: "404", params: {} };
}

function useRouter() {
  const [pathname, setPathname] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const handlePopState = () => setPathname(window.location.pathname || "/");
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (nextPath, options = {}) => {
    if (!nextPath) return;
    const next = nextPath.startsWith("/") ? nextPath : `/${nextPath}`;
    if (next !== window.location.pathname) {
      if (options.replace) {
        window.history.replaceState({}, "", next);
      } else {
        window.history.pushState({}, "", next);
      }
    }
    startTransition(() => setPathname(next));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return { pathname, navigate };
}

function AppLink({ to, navigate, className, children, accent = false, external = false }) {
  return (
    <a
      href={to}
      className={classNames(className, accent && "mw-link-accent")}
      onClick={(event) => {
        if (
          external ||
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}

function PublicHeader({ navigate, session, currentPath }) {
  const navItems = [
    { label: "Live Board", to: "/" },
    { label: "Scorecard Preview", to: PUBLIC_SCORECARD_PATH },
  ];

  return (
    <header className="mw-public-header">
      <div className="mw-logo-lockup">
        <AppLink to="/" navigate={navigate} className="mw-logo-link">
          <span className="mw-logo-mark">M</span>
          <span className="mw-logo-type">Moonwalking</span>
        </AppLink>
      </div>
      <nav className="mw-public-nav" aria-label="Primary">
        {navItems.map((item) => (
          <a
            key={item.label}
            href={item.to}
            className={classNames(
              "mw-public-nav__link",
              currentPath === item.to && "is-active"
            )}
            onClick={(event) => {
              if (item.to.startsWith("/#")) return;
              event.preventDefault();
              navigate(item.to);
            }}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <div className="mw-public-actions">
        {session.isAuthenticated ? (
          <>
            <AppLink to={APP_WATCHLISTS_PATH} navigate={navigate} className="mw-button mw-button--ghost">
              Watchlists
            </AppLink>
            <button type="button" className="mw-button mw-button--primary">
              {session.plan}
            </button>
          </>
        ) : (
          <>
            <AppLink to="/login" navigate={navigate} className="mw-button mw-button--ghost">
              Login
            </AppLink>
            <AppLink to="/signup" navigate={navigate} className="mw-button mw-button--primary" accent>
              Sign Up
            </AppLink>
          </>
        )}
      </div>
    </header>
  );
}

function PublicFooter() {
  return (
    <footer className="mw-public-footer">
      <div className="mw-footer-brand">
        <span className="mw-logo-mark">M</span>
        <span>Moonwalking</span>
      </div>
      <div className="mw-footer-links">
        <a href="/">Live Board</a>
        <a href="/login">Login</a>
        <a href="/signup">Sign Up</a>
      </div>
    </footer>
  );
}

function HomePage({ navigate }) {
  return (
    <div className="mw-home">
      <section className="mw-hero-card">
        <div className="mw-hero-copy">
          <p className="mw-eyebrow">Account-backed watchlists for a live market workflow</p>
          <h1>Access your watchlists anywhere</h1>
          <p className="mw-hero-text">
            Create an account, save watchlists to your Moonwalking server, and pick up
            where you left off from another connected browser.
          </p>
          <div className="mw-hero-actions">
            <AppLink to="/signup" navigate={navigate} className="mw-button mw-button--primary" accent>
              Get Started
            </AppLink>
            <AppLink to={PUBLIC_SCORECARD_PATH} navigate={navigate} className="mw-button mw-button--ghost">
              Open Scorecard Preview
            </AppLink>
            <a href="#public-tier" className="mw-button mw-button--ghost">
              Explore Public Tier
            </a>
          </div>
        </div>
        <div className="mw-hero-rail">
          <div className="mw-hero-stat">
            <span className="mw-hero-stat__label">Sync status</span>
            <strong>Cross-device ready</strong>
            <span>Backend-backed watchlists, not browser-only state.</span>
          </div>
          <div className="mw-hero-grid">
            <article className="mw-surface">
              <span className="mw-surface__eyebrow">Browse publicly</span>
              <h3>Explore before you commit</h3>
              <p>Let guests see the value before asking them to create an account.</p>
            </article>
            <article className="mw-surface">
              <span className="mw-surface__eyebrow">Save to your account</span>
              <h3>Every list follows the user</h3>
              <p>Load the same watchlists at home, on mobile, or on a new machine.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="mw-section" id="features">
        <div className="mw-section-heading">
          <p className="mw-eyebrow">How it works</p>
          <h2>Move from public exploration to personal tracking fast.</h2>
        </div>
        <div className="mw-step-grid">
          {[
            { title: "Browse publicly", copy: "Preview public content, pricing tiers, and example lists." },
            { title: "Create an account", copy: "Use signup or login to unlock your personal workspace." },
            { title: "Save watchlists", copy: "Create lists, add items, and keep notes close to each asset." },
            { title: "Access them anywhere", copy: "Sign in from another device and load the same saved data." },
          ].map((step, index) => (
            <article key={step.title} className="mw-step-card">
              <span className="mw-step-number">0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mw-section">
        <div className="mw-section-heading">
          <p className="mw-eyebrow">Feature highlights</p>
          <h2>The product basics are intentionally tight.</h2>
        </div>
        <div className="mw-feature-grid">
          {[
            {
              title: "Cloud-synced watchlists",
              copy: "Watchlists live in the backend so they can be fetched after login on any device.",
            },
            {
              title: "Secure login",
              copy: "Session-backed account access with room to add device controls later.",
            },
            {
              title: "Personal dashboard",
              copy: "Surface recent lists, counts, shortcuts, and completion signals in one place.",
            },
            {
              title: "Public or private presence",
              copy: "Keep a public-facing portfolio or switch to private until you want to share.",
            },
          ].map((feature) => (
            <article key={feature.title} className="mw-surface">
              <h3>{feature.title}</h3>
              <p>{feature.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mw-section" id="public-tier">
        <div className="mw-section-heading">
          <p className="mw-eyebrow">Public preview</p>
          <h2>Let prospects see the service before they sign in.</h2>
        </div>
        <div className="mw-showcase-grid">
          {publicShowcase.map((card) => (
            <article key={card.title} className="mw-showcase-card">
              <div className="mw-tag-row">
                {card.tags.map((tag) => (
                  <span key={tag} className="mw-tag">
                    {tag}
                  </span>
                ))}
              </div>
              <h3>{card.title}</h3>
              <p>{card.subtitle}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mw-section" id="pricing">
        <div className="mw-section-heading">
          <p className="mw-eyebrow">Tier preview</p>
          <h2>Keep version 1 focused, then expand from a stable core.</h2>
        </div>
        <div className="mw-pricing-grid">
          {tierCards.map((tier) => (
            <article key={tier.name} className="mw-pricing-card">
              <h3>{tier.name}</h3>
              <p>{tier.summary}</p>
              <ul>
                {tier.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function AuthPage({ mode, navigate, onSubmit, isSubmitting = false, errorMessage = "" }) {
  const [formState, setFormState] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    remember: true,
    acceptTerms: true,
  });

  const isSignup = mode === "signup";

  const handleChange = (key) => (event) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setFormState((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit(formState, mode);
  };

  return (
    <section className="mw-auth-layout">
      <div className="mw-auth-card">
        <p className="mw-eyebrow">{isSignup ? "Create your account" : "Welcome back"}</p>
        <h1>{isSignup ? "Save watchlists to your Moonwalking account." : "Return to your dashboard."}</h1>
        <p>
          {isSignup
            ? "Sign up, then move straight into the live board and saved watchlists."
            : "Log in to load the watchlists saved to your account on this Moonwalking server."}
        </p>
        <form className="mw-auth-form" onSubmit={handleSubmit}>
          {isSignup ? (
            <label className="mw-field">
              <span>Full Name</span>
              <input
                type="text"
                placeholder="Jane Doe"
                value={formState.name}
                onChange={handleChange("name")}
                required
              />
            </label>
          ) : null}
          <label className="mw-field">
            <span>Email</span>
            <input
              type="email"
              placeholder="jane@example.com"
              value={formState.email}
              onChange={handleChange("email")}
              required
            />
          </label>
          <label className="mw-field">
            <span>Password</span>
            <input
              type="password"
              placeholder="Enter your password"
              value={formState.password}
              onChange={handleChange("password")}
              required
            />
          </label>
          {isSignup ? (
            <label className="mw-field">
              <span>Confirm Password</span>
              <input
                type="password"
                placeholder="Confirm your password"
                value={formState.confirmPassword}
                onChange={handleChange("confirmPassword")}
                required
              />
            </label>
          ) : null}

          <div className="mw-checkbox-group">
            {isSignup ? (
              <label className="mw-check">
                <input
                  type="checkbox"
                  checked={formState.acceptTerms}
                  onChange={handleChange("acceptTerms")}
                />
                <span>I agree to the terms and privacy policy.</span>
              </label>
            ) : (
              <label className="mw-check">
                <input
                  type="checkbox"
                  checked={formState.remember}
                  onChange={handleChange("remember")}
                />
                <span>Remember me on this device.</span>
              </label>
            )}
          </div>

          <button
            type="submit"
            className="mw-button mw-button--primary mw-button--block"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : isSignup ? "Create Account" : "Log In"}
          </button>
          {errorMessage ? <p className="mw-auth-feedback mw-auth-feedback--error">{errorMessage}</p> : null}
        </form>
        <div className="mw-auth-links">
          {isSignup ? (
            <p>
              Already have an account?{" "}
              <AppLink to="/login" navigate={navigate}>
                Log in
              </AppLink>
            </p>
          ) : (
            <>
              <a href="#forgot">Forgot password?</a>
              <p>
                Need an account?{" "}
                <AppLink to="/signup" navigate={navigate}>
                  Sign up
                </AppLink>
              </p>
            </>
          )}
        </div>
      </div>

      <aside className="mw-auth-side">
        <article className="mw-surface">
          <span className="mw-surface__eyebrow">Core value</span>
          <h3>Watchlists tied to your account</h3>
          <p>Your saved assets follow your login across browsers connected to this server.</p>
        </article>
        <article className="mw-surface">
          <span className="mw-surface__eyebrow">Product loop</span>
          <h3>Live signals become saved context</h3>
          <p>Move from the real-time board to persistent tracking without losing your baseline.</p>
        </article>
      </aside>
    </section>
  );
}

function MemberShell({
  session,
  navigate,
  currentPath,
  watchlists,
  children,
  onLogout,
}) {
  const navItems = [
    { label: "Live Board", to: "/", external: true },
    { label: "Dashboard", to: APP_DASHBOARD_PATH },
    { label: "Watchlists", to: APP_WATCHLISTS_PATH },
    { label: "Portfolio", to: APP_PORTFOLIO_PATH },
    { label: "Scorecard", to: APP_SCORECARD_PATH },
    { label: "Settings", to: APP_SETTINGS_PATH },
  ];

  const totalItems = watchlists.reduce((count, watchlist) => count + watchlist.items.length, 0);

  return (
    <div className="mw-member-shell">
      <aside className="mw-sidebar">
        <div className="mw-sidebar__brand">
          <span className="mw-logo-mark">M</span>
          <div>
            <strong>Moonwalking</strong>
            <span>Account workspace</span>
          </div>
        </div>

        <div className="mw-user-card">
          <div className="mw-avatar">{initials(session.name)}</div>
          <div>
            <strong>{session.name}</strong>
            <span>@{session.username}</span>
          </div>
        </div>

        <nav className="mw-sidebar__nav" aria-label="Workspace">
          {navItems.map((item) => (
            <AppLink
              key={item.to}
              to={item.to}
              navigate={navigate}
              external={item.external}
              className={classNames(
                "mw-sidebar__link",
                currentPath === item.to && "is-active"
              )}
            >
              {item.label}
            </AppLink>
          ))}
        </nav>

        <div className="mw-sidebar__meta">
          <div>
            <span>Watchlists</span>
            <strong>{watchlists.length}</strong>
          </div>
          <div>
            <span>Saved items</span>
            <strong>{totalItems}</strong>
          </div>
        </div>

        <div className="mw-sidebar__footer">
          <AppLink to={`/u/${session.username}`} navigate={navigate} className="mw-button mw-button--ghost mw-button--block">
            View Public Profile
          </AppLink>
          <button type="button" className="mw-button mw-button--ghost mw-button--block" onClick={onLogout}>
            Logout
          </button>
        </div>
      </aside>

      <main className="mw-workspace">
        <header className="mw-member-header">
          <div>
            <p className="mw-eyebrow">Member workspace</p>
            <h1>{navItems.find((item) => item.to === currentPath)?.label || "Workspace"}</h1>
          </div>
          <div className="mw-member-header__meta">
            <span className="mw-status-chip">
              {session.isAuthenticated ? "Authenticated session" : "Preview mode"}
            </span>
            <span className="mw-status-chip mw-status-chip--accent">{session.plan}</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function DashboardPage({ session, watchlists, portfolio, navigate }) {
  const savedItems = watchlists.reduce((count, watchlist) => count + watchlist.items.length, 0);
  const profileCompletion = Math.round(
    ([
      portfolio.displayName,
      portfolio.bio,
      portfolio.website,
      portfolio.visibility,
      portfolio.featuredWatchlistIds.length > 0 ? "featured" : "",
    ].filter(Boolean).length /
      5) *
      100
  );

  const recentLists = [...watchlists]
    .sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt))
    .slice(0, 3);

  return (
    <div className="mw-stack">
      <section className="mw-board">
        <article className="mw-panel mw-panel--hero">
          <div>
            <p className="mw-eyebrow">Welcome back</p>
            <h2>{session.name}</h2>
            <p>
              Your saved watchlists are ready to load anywhere you sign in. Keep the
              product loop tight: build lists, refine them, and share the public profile later.
            </p>
          </div>
          <div className="mw-inline-actions">
            <AppLink to={APP_WATCHLISTS_PATH} navigate={navigate} className="mw-button mw-button--primary">
              New Watchlist
            </AppLink>
            <AppLink to={APP_PORTFOLIO_PATH} navigate={navigate} className="mw-button mw-button--ghost">
              View Portfolio
            </AppLink>
          </div>
        </article>

        <div className="mw-stat-grid">
          <article className="mw-panel mw-stat-card">
            <span>Watchlists</span>
            <strong>{watchlists.length}</strong>
          </article>
          <article className="mw-panel mw-stat-card">
            <span>Saved Items</span>
            <strong>{savedItems}</strong>
          </article>
          <article className="mw-panel mw-stat-card">
            <span>Profile Complete</span>
            <strong>{profileCompletion}%</strong>
          </article>
        </div>
      </section>

      <section className="mw-dashboard-grid">
        <article className="mw-panel">
          <div className="mw-panel__header">
            <h3>Recent Watchlists</h3>
            <span>Updated recently</span>
          </div>
          <ul className="mw-list">
            {recentLists.map((watchlist) => (
              <li key={watchlist.id} className="mw-list__row">
                <div>
                  <strong>{watchlist.name}</strong>
                  <span>{watchlist.items.length} items</span>
                </div>
                <span>{formatRelativeTime(watchlist.updatedAt)}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="mw-panel">
          <div className="mw-panel__header">
            <h3>Quick Actions</h3>
            <span>Keep the workflow moving</span>
          </div>
          <div className="mw-action-grid">
            <AppLink to={APP_WATCHLISTS_PATH} navigate={navigate} className="mw-action-card">
              <strong>Manage watchlists</strong>
              <span>Create, rename, filter, and refine the core data.</span>
            </AppLink>
            <AppLink to={APP_PORTFOLIO_PATH} navigate={navigate} className="mw-action-card">
              <strong>Open Portfolio Mode</strong>
              <span>Review private Coinbase holdings, cost-basis coverage, and current BHABIT reads.</span>
            </AppLink>
            <AppLink to={APP_SETTINGS_PATH} navigate={navigate} className="mw-action-card">
              <strong>Review settings</strong>
              <span>Handle sessions, passwords, notifications, and account controls.</span>
            </AppLink>
          </div>
        </article>
      </section>
    </div>
  );
}

function WatchlistsPage({
  watchlists,
  selectedWatchlistId,
  setSelectedWatchlistId,
  onCreateWatchlist,
  onRenameWatchlist,
  onDeleteWatchlist,
  onAddItem,
  onRemoveItem,
  onUpdateWatchlistNotes,
  onUpdateItemNotes,
  syncMessage = "",
}) {
  const selectedWatchlist =
    watchlists.find((watchlist) => watchlist.id === selectedWatchlistId) || watchlists[0];
  const [nameDraft, setNameDraft] = useState(selectedWatchlist?.name || "");
  const [itemDraft, setItemDraft] = useState("");
  const [filterQuery, setFilterQuery] = useState("");
  const [sortBy, setSortBy] = useState("position");
  const deferredFilter = useDeferredValue(filterQuery);

  useEffect(() => {
    setNameDraft(selectedWatchlist?.name || "");
  }, [selectedWatchlist?.id, selectedWatchlist?.name]);

  const visibleItems = useMemo(() => {
    const nextItems = [...(selectedWatchlist?.items || [])];
    const query = deferredFilter.trim().toLowerCase();
    const filtered = query
      ? nextItems.filter((item) => {
          return [item.title, item.itemKey, item.itemType, item.notes]
            .join(" ")
            .toLowerCase()
            .includes(query);
        })
      : nextItems;

    filtered.sort((left, right) => {
      if (sortBy === "title") return left.title.localeCompare(right.title);
      if (sortBy === "type") return left.itemType.localeCompare(right.itemType);
      if (sortBy === "updated") return right.position - left.position;
      return left.position - right.position;
    });

    return filtered;
  }, [deferredFilter, selectedWatchlist?.items, sortBy]);

  if (!selectedWatchlist) {
    return (
      <section className="mw-panel">
        <h2>No watchlists yet</h2>
        <p>Create the first watchlist to start shaping the member workflow.</p>
        <button type="button" className="mw-button mw-button--primary" onClick={onCreateWatchlist}>
          Create Watchlist
        </button>
      </section>
    );
  }

  return (
    <section className="mw-watchlists-layout">
      <aside className="mw-panel mw-watchlists-sidebar">
        <div className="mw-panel__header">
          <div>
            <h3>Watchlists</h3>
            <span>Cloud-saved collections</span>
          </div>
          <button type="button" className="mw-button mw-button--primary" onClick={onCreateWatchlist}>
            + New Watchlist
          </button>
        </div>

        <div className="mw-watchlist-list">
          {watchlists.map((watchlist) => (
            <button
              key={watchlist.id}
              type="button"
              className={classNames(
                "mw-watchlist-chip",
                watchlist.id === selectedWatchlist.id && "is-active"
              )}
              onClick={() => setSelectedWatchlistId(watchlist.id)}
            >
              <strong>{watchlist.name}</strong>
              <span>{watchlist.items.length} items</span>
            </button>
          ))}
        </div>
      </aside>

      <div className="mw-watchlists-main">
        <article className="mw-panel">
          <div className="mw-panel__header">
            <div>
              <span className="mw-eyebrow">Selected watchlist</span>
              <h2>{selectedWatchlist.name}</h2>
              <p>Last updated {formatRelativeTime(selectedWatchlist.updatedAt)}</p>
            </div>
            <div className="mw-inline-actions">
              <button
                type="button"
                className="mw-button mw-button--ghost"
                onClick={() => onRenameWatchlist(selectedWatchlist.id, nameDraft)}
              >
                Rename
              </button>
              <button
                type="button"
                className="mw-button mw-button--ghost mw-button--danger"
                onClick={() => onDeleteWatchlist(selectedWatchlist.id)}
              >
                Delete
              </button>
            </div>
          </div>

          <div className="mw-watchlist-toolbar">
            <label className="mw-field">
              <span>Watchlist Name</span>
              <input
                type="text"
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
              />
            </label>
            <label className="mw-field mw-field--grow">
              <span>Search or Add Item</span>
              <div className="mw-inline-field">
                <input
                  type="text"
                  placeholder="Type a symbol or name"
                  value={itemDraft}
                  onChange={(event) => setItemDraft(event.target.value)}
                />
                <button
                  type="button"
                  className="mw-button mw-button--primary"
                  onClick={() => {
                    onAddItem(selectedWatchlist.id, itemDraft);
                    setItemDraft("");
                  }}
                >
                  Add
                </button>
              </div>
            </label>
          </div>

          <div className="mw-watchlist-filters">
            <label className="mw-field mw-field--grow">
              <span>Filter Items</span>
              <input
                type="text"
                placeholder="Filter by name, symbol, type, or note"
                value={filterQuery}
                onChange={(event) => setFilterQuery(event.target.value)}
              />
            </label>
            <div className="mw-pill-row">
              {[
                { value: "position", label: "Manual" },
                { value: "title", label: "Title" },
                { value: "type", label: "Type" },
                { value: "updated", label: "Newest" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={classNames(
                    "mw-pill",
                    sortBy === option.value && "is-active"
                  )}
                  onClick={() => setSortBy(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mw-table-shell">
            <table className="mw-table">
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Type</th>
                  <th>Notes</th>
                  <th aria-label="Remove item" />
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => (
                  <tr key={`${item.id}:${item.notes}`}>
                    <td>
                      <strong>{item.title}</strong>
                      <span>{item.itemKey}</span>
                    </td>
                    <td>{item.itemType}</td>
                    <td>
                      <input
                        type="text"
                        defaultValue={item.notes}
                        onBlur={(event) =>
                          onUpdateItemNotes(selectedWatchlist.id, item.id, event.target.value)
                        }
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="mw-table__remove"
                        onClick={() => onRemoveItem(selectedWatchlist.id, item.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="mw-panel">
          <div className="mw-panel__header">
            <div>
              <h3>Notes</h3>
              <span>Save context next to each list</span>
            </div>
            <span
              className={classNames(
                "mw-status-chip",
                !syncMessage && "mw-status-chip--accent"
              )}
            >
              {syncMessage ? "Sync issue" : "Backend synced"}
            </span>
          </div>
          {syncMessage ? <p className="mw-auth-feedback mw-auth-feedback--error">{syncMessage}</p> : null}
          <textarea
            className="mw-notes-area"
            key={`${selectedWatchlist.id}:${selectedWatchlist.notes}`}
            defaultValue={selectedWatchlist.notes}
            onBlur={(event) =>
              onUpdateWatchlistNotes(selectedWatchlist.id, event.target.value)
            }
          />
        </article>
      </div>
    </section>
  );
}

function SettingsPage({ session, settings, sessions, onUpdateSettings, onLogOutOtherSessions }) {
  return (
    <div className="mw-settings-grid">
      <article className="mw-panel">
        <div className="mw-panel__header">
          <div>
            <h3>Profile</h3>
            <span>Name, email, and account context.</span>
          </div>
        </div>
        <div className="mw-form-grid">
          <label className="mw-field">
            <span>Name</span>
            <input type="text" value={session.name} readOnly />
          </label>
          <label className="mw-field">
            <span>Email</span>
            <input type="email" value={session.email} readOnly />
          </label>
        </div>
      </article>

      <article className="mw-panel">
        <div className="mw-panel__header">
          <div>
            <h3>Security</h3>
            <span>Device visibility and session control.</span>
          </div>
          <button type="button" className="mw-button mw-button--ghost">
            Change Password
          </button>
        </div>
        <div className="mw-session-list">
          {sessions.map((device) => (
            <div key={device.id} className="mw-session-row">
              <div>
                <strong>{device.deviceName}</strong>
                <span>{device.location}</span>
              </div>
              <span>{formatDateTime(device.lastSeenAt)}</span>
            </div>
          ))}
        </div>
        <button type="button" className="mw-button mw-button--ghost mw-button--block" onClick={onLogOutOtherSessions}>
          Log Out All Devices
        </button>
      </article>

      <article className="mw-panel">
        <div className="mw-panel__header">
          <div>
            <h3>Preferences</h3>
            <span>Notifications and theme controls.</span>
          </div>
        </div>
        <div className="mw-settings-list">
          <label className="mw-switch-row">
            <div>
              <strong>Email updates</strong>
              <span>Get account activity and summary emails.</span>
            </div>
            <input
              type="checkbox"
              checked={settings.notifications}
              onChange={(event) => onUpdateSettings("notifications", event.target.checked)}
            />
          </label>
          <label className="mw-switch-row">
            <div>
              <strong>Watchlist alerts</strong>
              <span>Reserved for future notification rules.</span>
            </div>
            <input
              type="checkbox"
              checked={settings.marketAlerts}
              onChange={(event) => onUpdateSettings("marketAlerts", event.target.checked)}
            />
          </label>
          <label className="mw-switch-row">
            <div>
              <strong>Remember sessions</strong>
              <span>Keep returning devices signed in longer.</span>
            </div>
            <input
              type="checkbox"
              checked={settings.rememberSessions}
              onChange={(event) => onUpdateSettings("rememberSessions", event.target.checked)}
            />
          </label>
        </div>

        <div className="mw-toggle-group">
          {["midnight", "marine", "sand"].map((theme) => (
            <button
              key={theme}
              type="button"
              className={classNames("mw-toggle", settings.theme === theme && "is-active")}
              onClick={() => onUpdateSettings("theme", theme)}
            >
              {titleize(theme)}
            </button>
          ))}
        </div>
      </article>
    </div>
  );
}

function PublicProfilePage({ username, portfolio, watchlists }) {
  const publicProfile = {
    displayName:
      username === "janedoe" ? portfolio.displayName : titleize(username.replace(/-/g, " ")),
    bio:
      username === "janedoe"
        ? portfolio.bio
        : "Public-facing portfolio preview for a member tracking conviction watchlists.",
    website: portfolio.website,
    visibility: username === "janedoe" ? portfolio.visibility : "public",
  };

  const featuredLists =
    username === "janedoe"
      ? watchlists.filter((watchlist) => portfolio.featuredWatchlistIds.includes(watchlist.id))
      : watchlists.slice(0, 2);

  return (
    <section className="mw-public-profile">
      <article className="mw-profile-hero">
        <div className="mw-avatar mw-avatar--large">{initials(publicProfile.displayName)}</div>
        <div>
          <p className="mw-eyebrow">Public profile</p>
          <h1>{publicProfile.displayName}</h1>
          <p>{publicProfile.bio}</p>
          <a href={publicProfile.website} className="mw-inline-link">
            {publicProfile.website}
          </a>
        </div>
      </article>

      {publicProfile.visibility === "private" ? (
        <article className="mw-panel">
          <h2>This profile is private.</h2>
          <p>Switch visibility to public from the portfolio screen to share featured watchlists.</p>
        </article>
      ) : (
        <div className="mw-showcase-grid">
          {featuredLists.map((watchlist) => (
            <article key={watchlist.id} className="mw-showcase-card">
              <div className="mw-tag-row">
                <span className="mw-tag">Public</span>
                <span className="mw-tag">{watchlist.items.length} items</span>
              </div>
              <h3>{watchlist.name}</h3>
              <p>{watchlist.description}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function NotFoundPage({ navigate }) {
  return (
    <section className="mw-panel mw-not-found">
      <p className="mw-eyebrow">Not found</p>
      <h1>The route does not exist in this MVP shell.</h1>
      <p>Use the homepage to move back into the public flow or sign in flow.</p>
      <AppLink to="/" navigate={navigate} className="mw-button mw-button--primary">
        Return Home
      </AppLink>
    </section>
  );
}

export default function MvpApp() {
  const { pathname, navigate } = useRouter();
  const route = matchRoute(pathname);

  const [session, setSession] = useState(defaultSession);
  const [watchlists, setWatchlists] = useState(initialWatchlists);
  const [selectedWatchlistId, setSelectedWatchlistId] = useState(initialWatchlists[0].id);
  const [portfolio, setPortfolio] = useState(initialPortfolio);
  const [settings, setSettings] = useState(initialSettings);
  const [sessions, setSessions] = useState(initialSessions);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
  const [watchlistSyncError, setWatchlistSyncError] = useState("");
  const [authHydrated, setAuthHydrated] = useState(false);

  const applyAuthPayload = (payload) => {
    const user = payload?.user || {};
    const nextWatchlists = Array.isArray(payload?.watchlists)
      ? payload.watchlists
      : [];

    setSession({
      isAuthenticated: true,
      name: user.name || defaultSession.name,
      email: user.email || defaultSession.email,
      username:
        user.username ||
        slugifyUsername(user.name || user.email?.split("@")[0] || defaultSession.username),
      plan: user.plan || defaultSession.plan,
    });
    setWatchlists(nextWatchlists);
    setSelectedWatchlistId(nextWatchlists[0]?.id || "");
    setPortfolio((current) => {
      const currentFeatured = current.featuredWatchlistIds.filter((id) =>
        nextWatchlists.some((watchlist) => watchlist.id === id)
      );
      const nextFeatured = currentFeatured.length
        ? currentFeatured
        : nextWatchlists.slice(0, 2).map((watchlist) => watchlist.id);
      return {
        ...current,
        displayName: user.name || current.displayName,
        featuredWatchlistIds: nextFeatured.slice(0, 3),
      };
    });
    setSessions([
      {
        id: `session-${Date.now()}`,
        deviceName: "Current Device",
        location: "Authenticated session",
        lastSeenAt: new Date().toISOString(),
      },
    ]);
  };

  useEffect(() => {
    let cancelled = false;
    const bootstrapSession = async () => {
      try {
        const payload = await apiRequest("/api/auth/session");
        if (cancelled) return;
        if (payload?.authenticated) {
          applyAuthPayload(payload);
        } else {
          setSession(defaultSession);
        }
      } catch (_error) {
        if (cancelled) return;
        setSession(defaultSession);
      } finally {
        if (!cancelled) setAuthHydrated(true);
      }
    };
    bootstrapSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const nextPath = legacyMemberRouteMap[pathname];
    if (!nextPath) return;
    navigate(nextPath, { replace: true });
  }, [navigate, pathname]);

  useEffect(() => {
    if (!authHydrated) return;
    if (protectedPaths.has(route.name) && !session.isAuthenticated) {
      navigate("/login", { replace: true });
      return;
    }
    if (
      session.isAuthenticated &&
      (route.name === "/login" || route.name === "/signup")
    ) {
      navigate(APP_WATCHLISTS_PATH, { replace: true });
    }
  }, [authHydrated, navigate, route.name, session.isAuthenticated]);

  useEffect(() => {
    if (!watchlists.some((watchlist) => watchlist.id === selectedWatchlistId)) {
      setSelectedWatchlistId(watchlists[0]?.id || "");
    }
  }, [selectedWatchlistId, watchlists]);

  useEffect(() => {
    setPortfolio((current) => ({
      ...current,
      featuredWatchlistIds: current.featuredWatchlistIds
        .filter((id) => watchlists.some((watchlist) => watchlist.id === id))
        .slice(0, 3),
    }));
  }, [watchlists]);

  const replaceWatchlistInState = (nextWatchlist) => {
    if (!nextWatchlist?.id) return;
    setWatchlists((current) =>
      current.map((watchlist) =>
        watchlist.id === nextWatchlist.id ? nextWatchlist : watchlist
      )
    );
  };

  const updateWatchlist = (watchlistId, updater) => {
    setWatchlists((current) =>
      current.map((watchlist) =>
        watchlist.id === watchlistId
          ? {
              ...watchlist,
              ...updater(watchlist),
              updatedAt: new Date().toISOString(),
            }
          : watchlist
      )
    );
  };

  const handleAuth = async (formState, mode) => {
    const isSignup = mode === "signup";
    if (isSignup && !formState.acceptTerms) {
      setAuthError("Please accept the terms to create an account.");
      return;
    }
    if (isSignup && formState.password !== formState.confirmPassword) {
      setAuthError("Passwords do not match.");
      return;
    }

    setAuthBusy(true);
    setAuthError("");
    try {
      const payload = await apiRequest(
        isSignup ? "/api/auth/signup" : "/api/auth/login",
        {
          method: "POST",
          body: {
            name: formState.name?.trim(),
            email: formState.email?.trim(),
            password: formState.password,
            remember: formState.remember,
          },
        }
      );
      applyAuthPayload(payload);
      setWatchlistSyncError("");
      navigate(APP_WATCHLISTS_PATH);
    } catch (error) {
      setAuthError(error.message || "Authentication failed.");
    } finally {
      setAuthBusy(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (_error) {
      // Keep local logout behavior even if network request fails.
    }
    setSession(defaultSession);
    setWatchlists(initialWatchlists);
    setSelectedWatchlistId(initialWatchlists[0]?.id || "");
    setPortfolio(initialPortfolio);
    setSettings(initialSettings);
    setSessions(initialSessions);
    setAuthError("");
    setWatchlistSyncError("");
    navigate("/");
  };

  const handleCreateWatchlist = async () => {
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest("/api/watchlists", {
          method: "POST",
          body: {
            name: `Watchlist ${watchlists.length + 1}`,
            description: "New list ready for custom symbols and notes.",
            notes: "Use this space for catalysts, theses, and risk notes.",
          },
        });
        if (payload?.watchlist) {
          setWatchlists((current) => [...current, payload.watchlist]);
          setSelectedWatchlistId(payload.watchlist.id);
          setWatchlistSyncError("");
        }
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not create watchlist.");
      }
      return;
    }

    const nextId = createId("watchlist");
    const nextWatchlist = {
      id: nextId,
      name: `Watchlist ${watchlists.length + 1}`,
      description: "New list ready for custom symbols and notes.",
      notes: "Use this space for catalysts, theses, and risk notes.",
      updatedAt: new Date().toISOString(),
      items: [],
    };
    setWatchlists((current) => [nextWatchlist, ...current]);
    setSelectedWatchlistId(nextId);
  };

  const handleRenameWatchlist = async (watchlistId, nextName) => {
    const trimmed = nextName.trim();
    if (!trimmed) return;
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(`/api/watchlists/${encodeURIComponent(watchlistId)}`, {
          method: "PATCH",
          body: { name: trimmed },
        });
        replaceWatchlistInState(payload.watchlist);
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not rename watchlist.");
      }
      return;
    }
    updateWatchlist(watchlistId, () => ({ name: trimmed }));
  };

  const handleDeleteWatchlist = async (watchlistId) => {
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(`/api/watchlists/${encodeURIComponent(watchlistId)}`, {
          method: "DELETE",
        });
        if (Array.isArray(payload.watchlists)) {
          setWatchlists(payload.watchlists);
          setSelectedWatchlistId(payload.watchlists[0]?.id || "");
        } else {
          setWatchlists((current) =>
            current.filter((watchlist) => watchlist.id !== watchlistId)
          );
        }
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not delete watchlist.");
      }
      return;
    }

    setWatchlists((current) => {
      if (current.length === 1) {
        return [
          {
            ...current[0],
            id: createId("watchlist"),
            name: "Fresh Watchlist",
            notes: "Start with the symbols or assets you want everywhere.",
            items: [],
            updatedAt: new Date().toISOString(),
          },
        ];
      }
      return current.filter((watchlist) => watchlist.id !== watchlistId);
    });
  };

  const handleAddItem = async (watchlistId, rawValue) => {
    const symbol = normalizeSymbol(rawValue);
    if (!symbol) return;
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(
          `/api/watchlists/${encodeURIComponent(watchlistId)}/items`,
          {
            method: "POST",
            body: {
              itemKey: symbol,
              itemType: guessItemType(symbol),
              title: formatItemTitle(symbol),
              notes: "New entry.",
            },
          }
        );
        replaceWatchlistInState(payload.watchlist);
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not add item.");
      }
      return;
    }

    updateWatchlist(watchlistId, (watchlist) => {
      if (watchlist.items.some((item) => item.itemKey === symbol)) {
        return {};
      }
      return {
        items: [
          ...watchlist.items,
          {
            id: createId("item"),
            itemKey: symbol,
            itemType: guessItemType(symbol),
            title: formatItemTitle(symbol),
            notes: "New entry.",
            position: watchlist.items.length + 1,
          },
        ],
      };
    });
  };

  const handleRemoveItem = async (watchlistId, itemId) => {
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(
          `/api/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(itemId)}`,
          { method: "DELETE" }
        );
        replaceWatchlistInState(payload.watchlist);
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not remove item.");
      }
      return;
    }

    updateWatchlist(watchlistId, (watchlist) => ({
      items: watchlist.items
        .filter((item) => item.id !== itemId)
        .map((item, index) => ({ ...item, position: index + 1 })),
    }));
  };

  const handleUpdateItemNotes = async (watchlistId, itemId, nextNotes) => {
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(
          `/api/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(itemId)}`,
          { method: "PATCH", body: { notes: nextNotes } }
        );
        replaceWatchlistInState(payload.watchlist);
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not save item notes.");
      }
      return;
    }

    updateWatchlist(watchlistId, (watchlist) => ({
      items: watchlist.items.map((item) =>
        item.id === itemId ? { ...item, notes: nextNotes } : item
      ),
    }));
  };

  const handleUpdateWatchlistNotes = async (watchlistId, nextNotes) => {
    if (session.isAuthenticated) {
      try {
        const payload = await apiRequest(`/api/watchlists/${encodeURIComponent(watchlistId)}`, {
          method: "PATCH",
          body: { notes: nextNotes },
        });
        replaceWatchlistInState(payload.watchlist);
        setWatchlistSyncError("");
      } catch (error) {
        setWatchlistSyncError(error.message || "Could not save watchlist notes.");
      }
      return;
    }

    updateWatchlist(watchlistId, () => ({ notes: nextNotes }));
  };

  const handleUpdateSettings = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const handleLogOutOtherSessions = () => {
    setSessions((current) => current.slice(0, 1));
  };

  const isPublicRoute =
    route.name === "/" ||
    route.name === PUBLIC_SCORECARD_PATH ||
    route.name === "/login" ||
    route.name === "/signup" ||
    route.name === "/u/:username" ||
    route.name === "404";

  const content = useMemo(() => {
    switch (route.name) {
      case "/":
        return <HomePage navigate={navigate} />;
      case "/login":
        return (
          <AuthPage
            mode="login"
            navigate={navigate}
            onSubmit={handleAuth}
            isSubmitting={authBusy}
            errorMessage={authError}
          />
        );
      case "/signup":
        return (
          <AuthPage
            mode="signup"
            navigate={navigate}
            onSubmit={handleAuth}
            isSubmitting={authBusy}
            errorMessage={authError}
          />
        );
      case APP_DASHBOARD_PATH:
        return (
          <DashboardPage
            session={session}
            watchlists={watchlists}
            portfolio={portfolio}
            navigate={navigate}
          />
        );
      case APP_WATCHLISTS_PATH:
        return (
          <WatchlistsPage
            watchlists={watchlists}
            selectedWatchlistId={selectedWatchlistId}
            setSelectedWatchlistId={setSelectedWatchlistId}
            onCreateWatchlist={handleCreateWatchlist}
            onRenameWatchlist={handleRenameWatchlist}
            onDeleteWatchlist={handleDeleteWatchlist}
            onAddItem={handleAddItem}
            onRemoveItem={handleRemoveItem}
            onUpdateWatchlistNotes={handleUpdateWatchlistNotes}
            onUpdateItemNotes={handleUpdateItemNotes}
            syncMessage={watchlistSyncError}
          />
        );
      case APP_PORTFOLIO_PATH:
        return <PortfolioModePage />;
      case PUBLIC_SCORECARD_PATH:
        return <ScorecardPage previewMode />;
      case APP_SCORECARD_PATH:
        return <ScorecardPage />;
      case APP_SETTINGS_PATH:
        return (
          <SettingsPage
            session={session}
            settings={settings}
            sessions={sessions}
            onUpdateSettings={handleUpdateSettings}
            onLogOutOtherSessions={handleLogOutOtherSessions}
          />
        );
      case "/u/:username":
        return (
          <PublicProfilePage
            username={route.params.username}
            portfolio={portfolio}
            watchlists={watchlists}
          />
        );
      default:
        return <NotFoundPage navigate={navigate} />;
    }
  }, [
    authBusy,
    authError,
    handleAuth,
    navigate,
    portfolio,
    route.name,
    route.params.username,
    selectedWatchlistId,
    session,
    sessions,
    settings,
    watchlistSyncError,
    watchlists,
  ]);

  return (
    <div className="mw-app">
      <div className="mw-background-layer" aria-hidden="true" />
      {isPublicRoute ? (
        <div className="mw-public-shell">
          <PublicHeader navigate={navigate} session={session} currentPath={pathname} />
          <main className="mw-public-main">{content}</main>
          <PublicFooter />
        </div>
      ) : (
        <MemberShell
          session={session}
          navigate={navigate}
          currentPath={pathname}
          watchlists={watchlists}
          onLogout={handleLogout}
        >
          {content}
        </MemberShell>
      )}
    </div>
  );
}
