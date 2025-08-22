import React, { useState } from 'react';

export default function AuthPanel({ onAuth }) {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSignIn = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    // Placeholder: No authentication, just simulate success
    setTimeout(() => {
      setMessage('Local mode: No authentication. Watchlist is saved only in your browser.');
      if (onAuth) onAuth();
      setLoading(false);
    }, 500);
    setLoading(false);
  };

  return (
    <div className="max-w-md mx-auto p-6 bg-black/70 rounded-xl border border-purple-900 mt-8">
      <h2 className="text-xl font-bold mb-4 text-center text-blue">Sign In to Save Your Watchlist</h2>
      <form onSubmit={handleSignIn} className="flex flex-col gap-4">
        <input
          type="email"
          placeholder="Your email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          className="p-2 rounded border border-gray-700 bg-black text-white"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition"
        >
          {loading ? 'Sending...' : 'Send Magic Link'}
        </button>
      </form>
      {message && <div className="mt-4 text-center text-sm text-orange-400">{message}</div>}
    </div>
  );
}
