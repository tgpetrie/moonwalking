import React, { useState } from 'react';

export default function AskCodexPanel({ onClose }) {
  const [query, setQuery] = useState('Explain how 1‑minute gainers trend streak is computed.');
  const [reply, setReply] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(''); setReply('');
    try {
      const res = await fetch('/api/ask-codex', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.reply || 'Request failed');
      setReply(data.reply || 'No reply');
    } catch (e2) {
      setError(e2.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-xl bg-gray-950 border border-purple-800 rounded-xl shadow-lg flex flex-col max-h-full">
        <div className="flex items-center justify-between px-4 py-3 border-b border-purple-900/50">
          <h2 className="text-sm font-bold tracking-wide text-purple-200">ASK CODEX</h2>
          <button onClick={onClose} className="px-2 py-1 text-xs rounded bg-purple-700/40 hover:bg-purple-600 text-purple-100 border border-purple-600">Close</button>
        </div>
        <form onSubmit={submit} className="p-4 flex flex-col gap-3 overflow-auto">
          <textarea
            className="w-full h-28 text-xs bg-black/40 border border-purple-700 rounded p-2 font-mono text-purple-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Ask about the dashboard, data flow, trends..." />
          <div className="flex items-center gap-2">
            <button type="submit" disabled={loading || !query.trim()} className="px-4 py-1.5 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-xs font-semibold shadow">{loading ? 'Asking...' : 'Ask'}</button>
            <button type="button" onClick={() => { setReply(''); setQuery(''); }} className="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs border border-gray-600">Clear</button>
          </div>
          {error && <div className="text-xs text-red-400">{error}</div>}
          {reply && <div className="mt-2 p-3 rounded bg-black/40 border border-purple-800 text-xs whitespace-pre-wrap leading-relaxed text-purple-100 font-mono max-h-64 overflow-auto">{reply}</div>}
        </form>
      </div>
    </div>
  );
}
