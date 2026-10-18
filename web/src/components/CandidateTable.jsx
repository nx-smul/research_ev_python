import { useMemo, useState } from 'react';

function formatPlaceName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function ResearchDownload({ children, ...props }) {
  return <button type="button" className="research-download" {...props}>{children}</button>;
}

export default function CandidateTable({
  candidates,
  rankMap,
  selected,
  comparisonIds,
  onToggleComparison,
  onJumpToSite,
  onFocusCandidate,
  onDownloadCSV,
  initialComparisonIds,
  activeFilters,
}) {
  const [candidateSort, setCandidateSort] = useState({ key: 'ahp_suitability_score', direction: 'desc' });

  const sortedRows = useMemo(() => [...candidates].sort((left, right) => {
    const a = left.properties?.[candidateSort.key];
    const b = right.properties?.[candidateSort.key];
    const comparison = ['candidate_id', 'zone_name'].includes(candidateSort.key)
      ? String(a || '').localeCompare(String(b || ''))
      : (Number(a) || 0) - (Number(b) || 0);
    return candidateSort.direction === 'asc' ? comparison : -comparison;
  }), [candidates, candidateSort]);

  const toggleSort = key => setCandidateSort(current => ({
    key,
    direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
  }));

  const sortLabel = key => candidateSort.key === key
    ? `Sorted ${candidateSort.direction === 'asc' ? 'ascending' : 'descending'}`
    : 'Sort';

  const comparisonFeatures = comparisonIds
    .map(id => candidates.find(f => f.properties?.candidate_id === id))
    .filter(Boolean);

  return (
    <details className="research-card candidate-table-card" open={initialComparisonIds.length > 0}>
      <summary>Candidate data table ({sortedRows.length})</summary>
      <p className="research-note">Suitability is a model score (0–1). Export includes run and available source provenance.</p>
      <div className="research-table-wrap candidate-table-wrap">
        <table className="research-table candidate-table">
          <caption className="visually-hidden">Filtered candidate sites; sortable by identifier, area, and suitability score</caption>
          <thead><tr>
            <th><span className="visually-hidden">Compare</span></th>
            <th aria-sort={candidateSort.key === 'candidate_id' ? candidateSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button type="button" onClick={() => toggleSort('candidate_id')} aria-label={`Sort by candidate ID, ${sortLabel('candidate_id')}`}>Candidate</button></th>
            <th aria-sort={candidateSort.key === 'zone_name' ? candidateSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button type="button" onClick={() => toggleSort('zone_name')} aria-label={`Sort by area, ${sortLabel('zone_name')}`}>Area</button></th>
            <th aria-sort={candidateSort.key === 'ahp_suitability_score' ? candidateSort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button type="button" onClick={() => toggleSort('ahp_suitability_score')} aria-label={`Sort by suitability score, ${sortLabel('ahp_suitability_score')}`}>Suitability (0–1)</button></th>
          </tr></thead>
          <tbody>{sortedRows.map(feature => {
            const properties = feature.properties || {};
            const candidateId = properties.candidate_id;
            const score = properties.ahp_suitability_score;
            return <tr key={candidateId} className={selected?.candidate_id === candidateId ? 'is-map-selected' : ''} aria-selected={selected?.candidate_id === candidateId}>
              <td><input type="checkbox" aria-label={`Compare ${properties.site_name || candidateId}`} checked={comparisonIds.includes(candidateId)} disabled={comparisonIds.length >= 3 && !comparisonIds.includes(candidateId)} onChange={() => onToggleComparison(candidateId)} /></td>
              <td><button type="button" className="candidate-link" onClick={() => onJumpToSite({ ...properties, ...rankMap[candidateId], geometry: feature.geometry })} aria-label={`Show ${properties.site_name || candidateId} on map`}>{properties.site_name || candidateId}</button></td>
              <td>{formatPlaceName(properties.zone_name || '—')}</td>
              <td>{Number.isFinite(Number(score)) ? Number(score).toFixed(2) : '—'}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      {!sortedRows.length && <div className="empty-state">No candidate sites match the selected filters.</div>}
      <p className="research-note">Select up to 3 sites to compare; current filter: {activeFilters}</p>
      <ResearchDownload onClick={onDownloadCSV} disabled={!sortedRows.length}>Download candidate CSV with provenance</ResearchDownload>
      {comparisonFeatures.length > 0 && <section className="comparison-panel" aria-label="Candidate comparison">
        <div className="section-title"><h3>Compare candidates ({comparisonFeatures.length}/3)</h3><button type="button" className="text-button" onClick={() => onToggleComparison('__clear__')}>Clear</button></div>
        <div className="research-table-wrap comparison-table-wrap"><table className="research-table"><caption className="visually-hidden">Comparison of selected candidate sites</caption><thead><tr><th>Candidate</th><th>Area</th><th>AHP score</th><th>TOPSIS score</th><th>Rank</th><th>Grid headroom</th><th>Distance to substation</th><th>Coverage</th><th>Map</th></tr></thead><tbody>
          {comparisonFeatures.map(feature => {
            const props = feature.properties || {};
            const rank = rankMap[props.candidate_id] || {};
            return <tr key={props.candidate_id}><td>{formatPlaceName(props.site_name || props.candidate_id)}</td><td>{formatPlaceName(props.zone_name || '—')}</td><td>{formatNumeric(props.ahp_suitability_score)}</td><td>{formatNumeric(rank.topsis_score)}</td><td>{rank.topsis_rank ?? '—'}</td><td>{formatNumeric(props.substation_headroom_mva, ' MVA')}</td><td>{formatNumeric(props.distance_to_substation_m, ' m')}</td><td>Solution-level only</td><td><button type="button" className="candidate-link" onClick={() => onFocusCandidate(props.candidate_id)}>Zoom</button></td></tr>;
          })}
        </tbody></table></div>
      </section>}
    </details>
  );
}

function formatNumeric(value, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : '—';
}
