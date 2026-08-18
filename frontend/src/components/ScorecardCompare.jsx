import ScorecardPage from "./ScorecardPage.jsx";
import ScorecardRedesignPage from "./ScorecardRedesignPage.jsx";
import "../styles/scorecard-redesign.css";

/**
 * Small header control that swaps between the original scorecard, the redesign,
 * and the side-by-side view. It lives outside both pages so neither page has to
 * know the other exists — the baseline stays untouched for comparison.
 */
export function ScorecardVariantSwitch({ variant, links, navigate }) {
  return (
    <div className="scr-switch">
      <span className="scr-switch__label">Scorecard version</span>
      <nav className="scr-switch__links" aria-label="Scorecard version">
        {links.map((link) => (
          <a
            key={link.variant}
            href={link.to}
            className={`scr-switch__link${link.variant === variant ? " is-active" : ""}`}
            aria-current={link.variant === variant ? "page" : undefined}
            onClick={(event) => {
              if (
                !navigate ||
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
              // A `?variant=` URL keeps the same pathname, so a client-side
              // navigation to that pathname would be a no-op and leave the
              // stale query in place. Reload in that one case.
              const samePath = window.location.pathname === link.to;
              if (samePath && window.location.search) {
                window.location.assign(link.to);
                return;
              }
              navigate(link.to);
            }}
          >
            {link.label}
          </a>
        ))}
      </nav>
    </div>
  );
}

/** Renders both versions in one view so the change is easy to judge. */
export function ScorecardCompareView({ previewMode = false }) {
  return (
    <div className="scr-compare">
      <p className="scr-compare__intro">
        Both versions read the same live data. The original is on the left, the redesign on the
        right. On a narrow screen they stack, original first.
      </p>

      {/* Collapsed by default: the point of this route is to look at the two
          pages, not to read about them. */}
      <details className="scr-compare__changes">
        <summary className="scr-compare__changes-toggle">What changed in the redesign</summary>
        <ul className="scr-compare__changes-list">
          <li>
            The coin is the page heading. On the original it is a pill above the title and a
            form near the bottom.
          </li>
          <li>
            Demo, preview, and live data each get their own label, and anything that is not
            measured from real outcomes says so in a banner.
          </li>
          <li>
            Signal history, board history, coin history, and internal diagnostics are four
            numbered zones, each opening with what it measures and what to do with it.
          </li>
          <li>
            Categories that sound like opposite advice are stated as separate buckets of past
            calls, so the page cannot be read as a live buy-and-sell contradiction.
          </li>
          <li>
            Grouped rollups and scoring parameters are collapsed into the diagnostics zone
            instead of sitting inline between the cards.
          </li>
          <li>
            When nothing has finished grading, the page shows collection progress rather than an
            empty chart.
          </li>
        </ul>
      </details>
      <div className="scr-compare__grid">
        <section className="scr-compare__pane">
          <header className="scr-compare__pane-head">
            <span className="scr-compare__pane-title">Original</span>
            <span className="scr-compare__pane-note">Current production page</span>
          </header>
          <ScorecardPage previewMode={previewMode} />
        </section>
        <section className="scr-compare__pane">
          <header className="scr-compare__pane-head">
            <span className="scr-compare__pane-title">Redesign</span>
            <span className="scr-compare__pane-note">Proposed replacement</span>
          </header>
          <ScorecardRedesignPage previewMode={previewMode} />
        </section>
      </div>
    </div>
  );
}

export default ScorecardCompareView;
