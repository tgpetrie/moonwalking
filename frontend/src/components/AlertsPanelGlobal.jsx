import React, { useCallback, useEffect, useState } from 'react';
import AlertsTab from './AlertsTab';
import ForYouTab from './alerts/ForYouTab.jsx';
import ActiveRulesTab from './alerts/ActiveRulesTab.jsx';
import AlertHistoryTab from './alerts/AlertHistoryTab.jsx';
import useAlertRules from './alerts/useAlertRules.js';
import { listRecommendations } from './alerts/alertRulesApi.js';
import '../styles/sentiment-popup-advanced.css';
import '../styles/alerts-center.css';

// "For You" is the personalized stream; suggestions live inside it rather
// than in a separate Recommended tab (a suggestion is an event to act on,
// not a destination to visit). The legacy market-wide feed stays intact
// under Market Feed.
const TABS = [
  { key: 'foryou', label: 'For You' },
  { key: 'active', label: 'Active' },
  { key: 'history', label: 'History' },
  { key: 'market', label: 'Market Feed' },
];

const SUBTITLES = {
  foryou: 'Signals and suggestions for coins you hold, watch, or track.',
  active: 'Alerts you have set up. Pause or remove them any time.',
  history: 'Alerts that have triggered, with what happened.',
  market: 'Market-wide stream. Coin popup alerts remain coin-scoped.',
};

export default function AlertsPanelGlobal({ isOpen, onClose, onOpenCoinSentiment = null }) {
  // Market Feed is the familiar default; we lead with For You only when the
  // user is signed in and actually has pending suggestions to look at.
  const [activeTab, setActiveTab] = useState('market');
  const [probed, setProbed] = useState(false);
  // Symbol handed from a For You signal to the builder: "rules are an action
  // attached to intelligence", not only a standalone destination.
  const [prefillSymbol, setPrefillSymbol] = useState(null);

  const {
    rules, recommendations, events,
    loading, errors, authRequired,
    loadRules, loadRecommendations, loadHistory,
    createRule, acceptRecommendation, dismissRecommendation,
    setRuleStatus, removeRule,
  } = useAlertRules();

  useEffect(() => {
    const onEsc = (evt) => {
      if (evt.key === 'Escape' && isOpen) onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', onEsc);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', onEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  // One cheap probe decides the landing tab. Signed-out or empty simply keeps
  // the Market Feed, so nothing is hidden from anyone.
  useEffect(() => {
    if (!isOpen || probed) return;
    let cancelled = false;
    listRecommendations({ refresh: true })
      .then((recs) => {
        if (!cancelled && Array.isArray(recs) && recs.length > 0) {
          setActiveTab('foryou');
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setProbed(true); });
    return () => { cancelled = true; };
  }, [isOpen, probed]);

  const handleLoadRules = useCallback((o) => loadRules(o), [loadRules]);
  const handleLoadHistory = useCallback((o) => loadHistory(o), [loadHistory]);
  // For You is the summary surface: it draws on all three slices.
  const handleLoadForYou = useCallback((o) => {
    loadRecommendations(o);
    loadHistory(o);
    loadRules(o);
  }, [loadRecommendations, loadHistory, loadRules]);

  // Alert-intent contract (v1): intelligence hands over only a symbol — never
  // builder internals. If richer prefill is ever needed (trigger type,
  // threshold), extend this contract here rather than letting stream items
  // reach into the builder's implementation.
  const handleSetAlertFor = useCallback((symbol) => {
    setPrefillSymbol(String(symbol || '').toUpperCase() || null);
    setActiveTab('active');
  }, []);

  const handlePrefillConsumed = useCallback(() => setPrefillSymbol(null), []);

  if (!isOpen) return null;

  return (
    <div
      className={`sentiment-overlay ${isOpen ? 'active' : ''}`}
      onClick={(event) => {
        if (event.target.classList.contains('sentiment-overlay')) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="alertsGlobalTitle"
    >
      <div className="sentiment-popup">
        <header className="popup-header">
          <div className="header-left">
            <div className="header-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path d="M15 17H9" />
                <path d="M18 17V11a6 6 0 10-12 0v6" />
                <path d="M5 17h14" />
                <path d="M10 21a2 2 0 004 0" />
              </svg>
            </div>
            <div className="header-text">
              <h1 id="alertsGlobalTitle">Alerts Center</h1>
              <p className="subtitle">{SUBTITLES[activeTab]}</p>
            </div>
          </div>

          <div className="header-right">
            <button className="close-btn" onClick={onClose} aria-label="Close alerts panel">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <nav className="tab-nav" role="tablist" aria-label="Alerts sections">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <main className="tab-content">
          {activeTab === 'foryou' && (
            <section className="tab-panel active" role="tabpanel">
              <ForYouTab
                events={events}
                recommendations={recommendations}
                rules={rules}
                loading={loading}
                errors={errors}
                authRequired={authRequired}
                onLoad={handleLoadForYou}
                onAccept={acceptRecommendation}
                onDismiss={dismissRecommendation}
                onOpenCoinSentiment={onOpenCoinSentiment}
                onSetAlertFor={handleSetAlertFor}
              />
            </section>
          )}

          {activeTab === 'active' && (
            <section className="tab-panel active" role="tabpanel">
              <ActiveRulesTab
                rules={rules}
                loading={loading.rules}
                error={errors.rules}
                authRequired={authRequired}
                onLoad={handleLoadRules}
                onCreate={createRule}
                onSetStatus={setRuleStatus}
                onRemove={removeRule}
                prefillSymbol={prefillSymbol}
                onPrefillConsumed={handlePrefillConsumed}
              />
            </section>
          )}

          {activeTab === 'history' && (
            <section className="tab-panel active" role="tabpanel">
              <AlertHistoryTab
                events={events}
                loading={loading.events}
                error={errors.events}
                authRequired={authRequired}
                onLoad={handleLoadHistory}
              />
            </section>
          )}

          {/* The legacy market-wide feed, unchanged and with all its filters. */}
          {activeTab === 'market' && (
            <section className="tab-panel active" role="tabpanel">
              <AlertsTab compact={false} onOpenCoinSentiment={onOpenCoinSentiment} />
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
