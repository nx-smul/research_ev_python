import { useEffect, useState } from 'react';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export function useLiveMap() {
  const [liveData, setLiveData] = useState(null);
  const [liveLoading, setLiveLoading] = useState(true);
  const [liveError, setLiveError] = useState('');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const refresh = () => setRefreshTrigger(v => v + 1);

  useEffect(() => {
    const controller = new AbortController();
    setLiveLoading(true);
    fetch(`${API_URL}/api/live-map${refreshTrigger ? '?refresh=true' : ''}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then(async response => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || `API returned ${response.status}`);
        setLiveData(payload);
        setLiveError('');
      })
      .catch(err => {
        if (err.name !== 'AbortError') setLiveError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLiveLoading(false);
      });
    return () => controller.abort();
  }, [refreshTrigger]);

  return { liveData, liveLoading, liveError, refresh };
}
