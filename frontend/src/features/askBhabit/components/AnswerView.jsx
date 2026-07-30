// The structured answer. Fixed section order:
//   1 Direct read · 2 What changed · 3 Your position · 4 Thesis check
//   5 Evidence · 6 Missing & uncertain · 7 Confidence · 8 Sources
//
// Design rules encoded here:
//   • Missing data is rendered with tone borders + status pills, never neutral.
//   • Confidence shows a qualitative badge + reasons, never a fake precise score.
//   • Sources use a <details> for progressive disclosure.
import PropTypes from "prop-types";
import { toneClass } from "./toneClass.js";

function Badge({ tone, children }) {
  return <span className={`abx-badge ${toneClass(tone)}`}>{children}</span>;
}
Badge.propTypes = { tone: PropTypes.string, children: PropTypes.node };

function Section({ index, title, children }) {
  return (
    <section className="abx-card">
      <p className="abx-card-title">
        {index}. {title}
      </p>
      {children}
    </section>
  );
}
Section.propTypes = { index: PropTypes.number, title: PropTypes.string, children: PropTypes.node };

export default function AnswerView({ view, onCitationOpen }) {
  const { directRead, whatChanged, position, thesisCheck, evidence, missing, confidence, sources, assetIdentity } = view;
  const pos = position.display;

  return (
    <div className="abx-answer">
      {/* 1 — Direct read */}
      <div className={`abx-direct ${toneClass(directRead.tone)}`}>
        {assetIdentity ? <AssetIdentity identity={assetIdentity} /> : null}
        <p className="abx-direct-headline">{directRead.headline}</p>
        {directRead.detail ? <p className="abx-direct-detail">{directRead.detail}</p> : null}
      </div>

      {/* 2 — What changed */}
      <Section index={2} title="What changed">
        <div style={{ marginBottom: whatChanged.items.length ? 10 : 0 }}>
          <Badge tone={whatChanged.tone}>{whatChanged.label}</Badge>
          {whatChanged.sinceLabel ? (
            <span className="abx-source-meta" style={{ marginLeft: 8 }}>since {whatChanged.sinceLabel}</span>
          ) : null}
        </div>
        {whatChanged.hasPrior ? (
          <div className="abx-list">
            {whatChanged.items.map((item, i) => (
              <div key={i} className={`abx-item ${toneClass(item.tone)}`}>
                <div className="abx-item-label">{item.label}</div>
                {item.detail ? <div className="abx-item-detail">{item.detail}</div> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="abx-muted-note">{whatChanged.blurb} No prior snapshot to compare against yet.</p>
        )}
      </Section>

      {/* 3 — Your position */}
      <Section index={3} title="Your position">
        <div className="abx-posgrid">
          <Metric label="Entry" value={pos.entryPrice} />
          <Metric label="Market" value={pos.marketPrice} />
          <Metric label="Cost basis" value={pos.costBasis} />
          <Metric label="Unrealized P&L" value={pos.unrealizedPnl} tone={position.pnlTone} />
          <Metric label="Return" value={pos.unrealizedPnlPct} tone={position.pnlTone} />
          <Metric label="Allocation" value={pos.allocationPct} />
        </div>
      </Section>

      {/* 4 — Thesis check */}
      <Section index={4} title="Thesis check">
        {thesisCheck ? (
          <>
            <Badge tone={thesisCheck.tone}>{thesisCheck.label}</Badge>
            {thesisCheck.reasons.length ? (
              <ul className="abx-reasons">
                {thesisCheck.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : (
          <p className="abx-muted-note">No thesis on file — add one to have future answers track it.</p>
        )}
      </Section>

      {/* 5 — Evidence */}
      <Section index={5} title="Evidence">
        {evidence.length ? (
          <div className="abx-list">
            {evidence.map((e, i) => (
              <div key={i} className={`abx-item ${toneClass(e.tone)}`}>
                <div className="abx-item-label">{e.claim}</div>
                {e.detail ? <div className="abx-item-detail">{e.detail}</div> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="abx-muted-note">No supporting evidence could be gathered.</p>
        )}
      </Section>

      {/* 6 — Missing & uncertain (never neutral) */}
      <Section index={6} title="Missing & uncertain data">
        {missing.length ? (
          <div className="abx-list">
            {missing.map((m, i) => (
              <div key={i} className={`abx-missing-item ${toneClass(m.tone)}`}>
                <span className="abx-missing-status">{m.label}</span>
                <div className="abx-missing-body">
                  <div className="abx-missing-metric">{m.metric}</div>
                  <div className="abx-missing-detail">{m.detail || m.blurb}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="abx-muted-note">No material data gaps detected.</p>
        )}
      </Section>

      {/* 7 — Confidence (qualitative, with reasons) */}
      <Section index={7} title="Confidence">
        <Badge tone={confidence.tone}>{confidence.label}</Badge>
        {confidence.reasons.length ? (
          <ul className="abx-reasons">
            {confidence.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : null}
      </Section>

      {/* 8 — Sources (progressive disclosure) */}
      <Section index={8} title="Sources">
        {sources.length ? (
          <details>
            <summary className="abx-source-summary">{sources.length} sources</summary>
            <div style={{ marginTop: 8 }}>
              {sources.map((s, i) => (
                <div key={i} className="abx-source">
                  <span className="abx-source-provider">{s.provider}</span>
                  <span className="abx-source-meta">
                    {s.retrievedLabel}
                    {" · "}
                    <span className={`abx-freshness ${toneClass(s.freshness === "fresh" ? "positive" : s.freshness === "error" ? "danger" : "warning")}`}>
                      {s.freshness}
                    </span>
                  </span>
                  <span className="abx-source-claim">
                    {s.claim}
                    {s.url ? (
                      <>
                        {" — "}
                        <a
                          className="abx-source-link"
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={() => onCitationOpen?.(s)}
                        >
                          open
                        </a>
                      </>
                    ) : null}
                  </span>
                </div>
              ))}
            </div>
          </details>
        ) : (
          <p className="abx-muted-note">No sources to cite.</p>
        )}
      </Section>
    </div>
  );
}

function AssetIdentity({ identity }) {
  return (
    <div className="abx-asset-identity">
      <span>{identity.name}</span>
      <span>{identity.symbol}</span>
      {identity.chain ? <span>{identity.chain}</span> : null}
      {identity.shortIdentifier ? (
        <details className="abx-identity-details">
          <summary aria-label={`Full identifier ${identity.fullIdentifier}`}>
            <code>{identity.shortIdentifier}</code>
          </summary>
          <code className="abx-full-identifier">{identity.fullIdentifier}</code>
        </details>
      ) : null}
    </div>
  );
}

AssetIdentity.propTypes = {
  identity: PropTypes.shape({
    name: PropTypes.string,
    symbol: PropTypes.string,
    chain: PropTypes.string,
    shortIdentifier: PropTypes.string,
    fullIdentifier: PropTypes.string,
  }),
};

function Metric({ label, value, tone }) {
  return (
    <div className="abx-metric">
      <span className="abx-metric-label">{label}</span>
      <span className={`abx-metric-value ${tone ? toneClass(tone) : ""}`}>{value}</span>
    </div>
  );
}
Metric.propTypes = { label: PropTypes.string, value: PropTypes.node, tone: PropTypes.string };

AnswerView.propTypes = {
  view: PropTypes.object.isRequired,
  onCitationOpen: PropTypes.func,
};
