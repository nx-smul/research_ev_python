export default function ParetoSelector({ solutions, roles, solutionIndex, onSelect, onDownloadCSV }) {
  if (!solutions?.length) return <div className="empty-state">No Pareto solutions available.</div>;

  return (
    <>
      <div className="section-title"><div><span className="eyebrow">PARETO TRADE-OFF</span><h3>Choose a solution</h3></div><button className="text-button" onClick={onDownloadCSV}>CSV ↓</button></div>
      <div className="solution-list">{solutions.map((row, index) => <button key={row.solution_id || index} className={`solution-card ${solutionIndex === index ? 'is-active' : ''}`} onClick={() => onSelect(index)} aria-pressed={solutionIndex === index}>
        <span className="solution-id">{row.solution_id || `S${index + 1}`}</span><span className="solution-role">{roles.roles[index]?.join(' · ') || 'Pareto alternative'}</span><span className="solution-stats">{row.open_station_count ?? '—'} stations <b>{Number(row.demand_coverage_pct || 0).toFixed(1)}% coverage</b></span>
      </button>)}</div>
    </>
  );
}
