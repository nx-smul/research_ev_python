import { formatPlaceName } from './ResearchInsights';

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—';
}

function formatSHA(hash) {
  return hash ? `${hash.substring(0, 8)}...` : '—';
}

function getClassBadge(classValue) {
  const badges = {
    observed: { color: '#10b981', label: 'Observed' },
    official_source: { color: '#3b82f6', label: 'Official Source' },
    derived_from_observed: { color: '#8b5cf6', label: 'Derived' },
    community_mapped: { color: '#f59e0b', label: 'Community Mapped' },
    assumed: { color: '#f97316', label: 'Assumed' },
    synthetic_demo: { color: '#6b7280', label: 'Synthetic Demo' },
    configuration: { color: '#06b6d4', label: 'Configuration' },
  };
  return badges[classValue] || { color: '#6b7280', label: classValue || 'Unknown' };
}

function getClaimLevelLabel(dataMode) {
  if (dataMode === 'demo') {
    return { level: 1, label: 'Level 1: Software Demonstration', color: '#6b7280' };
  }
  return { level: 3, label: 'Level 3: Scenario Result', color: '#f59e0b' };
}

export default function EvidencePanel({ manifest, runMetadata }) {
  if (!manifest) {
    return (
      <section className="evidence-panel" aria-label="Data status">
        <div className="section-title"><div><span className="eyebrow">EVIDENCE STATUS</span><h3>Data status</h3></div></div>
        <div className="empty-state">No run manifest found.</div>
      </section>
    );
  }

  const dataClass = manifest.data_mode === 'demo' ? 'synthetic_demo' : 'provenance_documented_unverified';
  const claimInfo = getClaimLevelLabel(manifest.data_mode);
  const evidenceStatus = manifest.evidence_summary?.status || 'unknown';

  const inputRows = runMetadata?.evidence?.inputs || manifest.inputs || [];
  const inputCount = inputRows.length;
  const observedCount = inputRows.filter(r => ['observed', 'official_source', 'derived_from_observed'].includes(r.data_class)).length;
  const syntheticCount = inputRows.filter(r => r.data_class === 'synthetic_demo').length;

  return (
    <section className="evidence-panel" aria-label="Data status">
      <div className="section-title">
        <div>
          <span className="eyebrow">EVIDENCE STATUS</span>
          <h3>Data status</h3>
        </div>
        <span className="run-pill" style={{ backgroundColor: claimInfo.color, color: '#fff' }}>
          Claim Level {claimInfo.level}
        </span>
      </div>

      <div className="data-status-card">
        <div className="data-status-row">
          <span className="label">Data mode:</span>
          <span className="value">{manifest.data_mode === 'demo' ? 'SYNTHETIC DEMO' : 'PROVENANCE-DOCUMENTED'}</span>
        </div>
        <div className="data-status-row">
          <span className="label">Evidence status:</span>
          <span className="value">{evidenceStatus.replace(/_/g, ' ').toUpperCase()}</span>
        </div>
        <div className="data-status-row">
          <span className="label">Claim level:</span>
          <span className="value" style={{ color: claimInfo.color }}>{claimInfo.label}</span>
        </div>
        {manifest.created_at && (
          <div className="data-status-row">
            <span className="label">Run created:</span>
            <span className="value">{new Date(manifest.created_at).toLocaleDateString()}</span>
          </div>
        )}
        <div className="data-status-row">
          <span className="label">Run ID:</span>
          <span className="value" style={{ fontFamily: 'monospace' }}>{manifest.run_id?.substring(0, 8)}...</span>
        </div>
      </div>
      <p className="refresh-note" style={{ fontSize: '0.8rem', color: 'var(--text-muted, #64748b)', margin: '4px 0 8px' }}>
        Automatically refreshes every minute while this tab is open.
      </p>

      {manifest.evidence_summary?.limitations && (
        <div className="limitations-panel">
          <strong>Limitations</strong>
          <ul>
            {manifest.evidence_summary.limitations.map((lim, i) => (
              <li key={i}>{lim}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="input-inventory">
        <summary>Run inputs & provenance ({inputCount})</summary>
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Path</th>
                <th>Class</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {inputRows.map((row) => {
                const badge = getClassBadge(row.data_class);
                return (
                  <tr key={row.path}>
                    <td>{row.label || 'Unnamed'}</td>
                    <td>{row.path?.split('/').slice(-2).join('/') || '—'}</td>
                    <td>
                      <span className="badge" style={{ backgroundColor: badge.color, color: '#fff' }}>
                        {badge.label}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.85em' }}>
                      {formatSHA(row.sha256)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>

      <div className="claim-warning">
        <strong>Interpretation</strong>
        <p>
          {manifest.data_mode === 'demo'
            ? 'This run uses synthetic demonstration data; results are modeled estimates, not observed demand, utilization, or an investment forecast.'
            : 'Results are conditional on inputs and assumptions. Provenance declarations do not independently authenticate source claims.'}
        </p>
      </div>
    </section>
  );
}
