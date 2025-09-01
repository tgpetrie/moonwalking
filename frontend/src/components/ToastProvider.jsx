import React, { createContext, useContext, useCallback, useState, useEffect } from 'react';

const ToastContext = createContext(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

export default function ToastProvider({ children, max = 3, duration = 2200 }) {
  const [toasts, setToasts] = useState([]);

  const show = useCallback((message, opts = {}) => {
    const id = Math.random().toString(36).slice(2);
    const toast = { id, message, type: opts.type || 'info' };
    setToasts((curr) => {
      const next = [...curr, toast];
      return next.slice(-max);
    });
    setTimeout(() => {
      setToasts((curr) => curr.filter((t) => t.id !== id));
    }, opts.duration || duration);
  }, [max, duration]);

  // Also listen for custom events so non-hook code can trigger a toast (optional)
  useEffect(() => {
    const handler = (e) => { if (e?.detail?.message) show(e.detail.message, e.detail); };
    window.addEventListener('bhabit:toast', handler);
    return () => window.removeEventListener('bhabit:toast', handler);
  }, [show]);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 10000, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map((t) => (
          <div key={t.id}
               style={{
                 background: t.type === 'error' ? 'rgba(239,68,68,0.9)' : 'rgba(37,99,235,0.9)',
                 color: '#fff',
                 padding: '8px 12px',
                 borderRadius: 8,
                 boxShadow: '0 6px 18px rgba(0,0,0,0.3)',
                 fontSize: 12,
                 maxWidth: 280,
               }}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

