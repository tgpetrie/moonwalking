import React from 'react';
import { learnComplete, learnProgress, LearnProgress } from '../../api/sentiment';

export default function LearningTracker(): JSX.Element {
  const [progress, setProgress] = React.useState<LearnProgress | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      const res = await learnProgress();
      setProgress(res.progress);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Unable to load progress');
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const handleComplete = async () => {
    setLoading(true);
    try {
      const res = await learnComplete();
      setProgress(res.progress);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Unable to update progress');
    } finally {
      setLoading(false);
    }
  };

  const completed = progress?.completed ?? 0;
  const streak = progress?.streak ?? 0;

  return (
    <div className="p-4 rounded-2xl shadow bg-white">
      <div className="font-semibold mb-1">Learning</div>
      {error && (
        <div className="text-xs text-red-600 mb-1" role="alert">
          {error}
        </div>
      )}
      <div className="text-sm text-gray-700">Completed: {completed} • Streak: {streak}</div>
      <button
        className="mt-2 px-3 py-2 rounded-xl bg-emerald-600 text-white disabled:opacity-50"
        onClick={handleComplete}
        disabled={loading}
      >
        Mark lesson done
      </button>
    </div>
  );
}
