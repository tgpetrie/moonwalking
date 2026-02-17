import React, { useEffect } from 'react';
import AlertsTab from './AlertsTab';
import '../styles/sentiment-popup-advanced.css';

export default function AlertsPanelGlobal({ isOpen, onClose }) {
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
              <p className="subtitle">Market-wide stream. Coin popup alerts remain coin-scoped.</p>
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

        <main className="tab-content">
          <section className="tab-panel active" role="tabpanel">
            <AlertsTab compact={false} />
          </section>
        </main>
      </div>
    </div>
  );
}
