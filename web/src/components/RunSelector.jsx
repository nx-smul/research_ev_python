import { useCallback, useEffect, useState } from 'react';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export function RunSelector({ onSelectRun, currentRunId }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchRuns = useCallback(() => {
    setLoading(true);
    fetch(`${API_URL}/api/runs`)
      .then(response => {
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return response.json();
      })
      .then(data => {
        setRuns(data?.runs || []);
        setError('');
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleSelect = run => {
    if (onSelectRun) {
      onSelectRun(run.run_id);
    }
  };

  const refresh = () => {
    fetchRuns();
  };

  return (
    <details className="run-selector-card">
      <summary>Run history ({runs.length})</summary>
      <p className="research-note">Switch between completed runs to compare results.</p>
      {loading ? (
        <div className="empty-state">Loading runs...</div>
      ) : error ? (
        <div className="error-state">
          <p>Could not load run history.</p>
          <button type="button" className="button button-small" onClick={refresh}>Retry</button>
        </div>
      ) : !runs.length ? (
        <div className="empty-state">No previous runs found.</div>
      ) : (
        <div className="run-list">
          {runs.map(run => (
            <button
              key={run.run_id}
              type="button"
              className={`run-item${currentRunId === run.run_id ? ' is-current' : ''}`}
              aria-current={currentRunId === run.run_id ? 'true' : undefined}
              onClick={() => handleSelect(run)}
            >
              <div className="run-info">
                <span className="run-id">{run.run_id?.substring(0, 10)}</span>
                <span className="run-date">{new Date(run.created_at).toLocaleDateString()}</span>
                <span className="run-mode">{run.data_mode}</span>
              </div>
              <div className="run-stats">
                {run.candidate_count && <span>{run.candidate_count} candidates</span>}
                {run.pareto_solutions_count && <span>{run.pareto_solutions_count} Pareto</span>}
              </div>
            </button>
          ))}
        </div>
      )}
    </details>
  );
}

export default RunSelector;
