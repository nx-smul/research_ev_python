function formatNumeric(value, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : '—';
}

export default function FilterPanel({
  zone,
  setZone,
  minAhp,
  setMinAhp,
  maxAhp,
  setMaxAhp,
  query,
  setQuery,
  candidates,
}) {
  const zoneCounts = {};
  const scores = [];

  (candidates || []).forEach(f => {
    const z = f.properties?.zone_name || 'Unknown';
    zoneCounts[z] = (zoneCounts[z] || 0) + 1;

    const score = f.properties?.ahp_suitability_score;
    if (Number.isFinite(Number(score))) {
      scores.push(Number(score));
    }
  });

  const minScore = scores.length > 0 ? Math.min(...scores) : 0;
  const maxScore = scores.length > 0 ? Math.max(...scores) : 1;

  const clearAll = () => {
    setZone('ALL');
    setMinAhp(0);
    setMaxAhp(1);
    setQuery('');
  };

  return (
    <details className="research-card filter-panel">
      <summary>Filter controls</summary>
      <p className="research-note">Narrow candidate results by area and score range.</p>

      <div className="filter-section">
        <label className="filter-label">
          <span>Zone/Area</span>
          <select value={zone} onChange={e => setZone(e.target.value)}>
            <option value="ALL">All Dhaka ({candidates?.length || 0})</option>
            {Object.entries(zoneCounts)
              .sort((a, b) => b[1] - a[1])
              .map(([name, count]) => (
                <option key={name} value={name}>{name} ({count})</option>
              ))}
          </select>
        </label>
      </div>

      <div className="filter-section">
        <label className="filter-label">
          <span>Minimum suitability</span>
          <span>{formatNumeric(minAhp, '/1')}</span>
          <input
            type="range"
            min="0"
            max={maxAhp}
            step="0.05"
            value={minAhp}
            onChange={e => setMinAhp(Number(e.target.value))}
          />
        </label>
      </div>

      <div className="filter-section">
        <label className="filter-label">
          <span>Maximum suitability</span>
          <span>{formatNumeric(maxAhp, '/1')}</span>
          <input
            type="range"
            min={minAhp}
            max="1"
            step="0.05"
            value={maxAhp}
            onChange={e => setMaxAhp(Number(e.target.value))}
          />
        </label>
      </div>

      <div className="filter-section">
        <label className="filter-label">
          <span>Search</span>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Site name, ID, or zone"
            className="filter-input"
          />
        </label>
      </div>

      <div className="filter-actions">
        <button type="button" className="text-button" onClick={clearAll}>
          Clear all filters
        </button>
      </div>
    </details>
  );
}
