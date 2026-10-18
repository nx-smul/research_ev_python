import { useCallback, useEffect, useState } from 'react';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export function useDashboardData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [retrievedAt, setRetrievedAt] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedRunId, setSelectedRunId] = useState(null);

  const refresh = useCallback(() => setRefreshTrigger(v => v + 1), []);
  const selectRun = useCallback(runId => setSelectedRunId(runId), []);

  useEffect(() => {
    const controller = new AbortController();
    if (!data) setLoading(true);
    setIsRefreshing(true);
    fetch(`${API_URL}${selectedRunId ? `/api/run/${encodeURIComponent(selectedRunId)}` : '/api/dashboard'}`, { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return response.json();
      })
      .then(payload => {
        if (!payload || typeof payload !== 'object') throw new Error('Dashboard returned an invalid data payload');
        setData(payload);
        setRetrievedAt(new Date());
        setError('');
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError(`${err.message}. Check the API URL and CORS configuration.`);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setIsRefreshing(false);
        }
      });
    return () => controller.abort();
  }, [refreshTrigger, selectedRunId]);

  // Auto-refresh every 60 seconds when tab is visible
  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') {
        setRefreshTrigger(value => value + 1);
      }
    };
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        setRefreshTrigger(value => value + 1);
      }
    }, 60_000);
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, []);

  return { data, loading, error, isRefreshing, retrievedAt, refresh, selectRun };
}
