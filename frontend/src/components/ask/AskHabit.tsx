import React from 'react';
import { postAsk, recentAsks, AskRecentResponse } from '../../api/sentiment';

const MIN_TTL_SECONDS = 20;

export default function AskHabit(): JSX.Element {
  const [question, setQuestion] = React.useState('');
  const [payload, setPayload] = React.useState<AskRecentResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const refresh = React.useCallback(async () => {
    try {
      const res = await recentAsks();
      setPayload(res);
      setError(null);
      return res;
    } catch (err: any) {
      setError(err.message || 'Unable to load recent asks');
      return null;
    }
  }, []);

  React.useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const loop = async () => {
      const res = await refresh();
      if (!alive) return;
      const ttlSeconds = res?.swr?.ttl_seconds ?? res?.swr?.ttl ?? 30;
      timer = setTimeout(loop, Math.max(MIN_TTL_SECONDS, ttlSeconds) * 1000);
    };

    loop();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    setSubmitting(true);
    try {
      await postAsk(trimmed);
      setQuestion('');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Unable to log question');
    } finally {
      setSubmitting(false);
    }
  };

  const items = payload?.items || [];

  return (
    <div className="p-4 rounded-2xl shadow bg-white">
      <div className="font-semibold mb-2">What do you want to know next?</div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          className="flex-1 border rounded-xl px-3 py-2"
          placeholder="Ask a falsifiable question…"
          disabled={submitting}
        />
        <button
          type="submit"
          className="px-3 py-2 rounded-xl bg-black text-white disabled:opacity-50"
          disabled={submitting}
        >
          Log
        </button>
      </form>
      {error && (
        <div className="mt-2 text-xs text-red-600" role="alert">
          {error}
        </div>
      )}
      <div className="mt-3 text-xs text-gray-500">Recent asks</div>
      <ul className="mt-1 space-y-1">
        {items.slice(0, 5).map((entry, index) => (
          <li key={`${entry.ts}-${index}`} className="text-sm text-gray-700">
            • {entry.q}
          </li>
        ))}
        {!items.length && <li className="text-sm text-gray-400">No questions logged yet.</li>}
      </ul>
    </div>
  );
}
