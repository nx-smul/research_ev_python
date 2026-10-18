function formatNumeric(value, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : '—';
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—';
}

function formatCurrency(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 0 })} BDT` : '—';
}

function formatMegaValue(value, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number / 1000000).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : '—';
}

export default function MetricsDashboard({ solution, research, candidates }) {
  const coverage = solution?.demand_coverage_pct;
  const cost = solution?.total_cost_million_bdt;
  const gridLoad = solution?.total_grid_power_kw;
  const stationCount = solution?.open_station_count;
  const candidateCount = candidates?.length || 0;

  const carbonSummary = research?.carbon_summary;
  const utilizationSummary = research?.utilization_summary;
  const robustnessSummary = research?.robustness_summary;

  return (
    <details className="research-card metrics-dashboard" open>
      <summary>Summary metrics</summary>
      <p className="research-note">At-a-glance indicators. Values depend on selected solution.</p>

      <div className="metrics-grid dashboard-grid">
        {/* Core Metrics */}
        <div className="metric-card">
          <span>Candidate sites</span>
          <strong>{candidateCount}</strong>
        </div>
        <div className="metric-card">
          <span>Selected stations</span>
          <strong>{stationCount}</strong>
        </div>
        <div className="metric-card" title="Share of input demand assigned to selected stations">
          <span>Modeled coverage</span>
          <strong>{formatPercent(coverage)}</strong>
          <small>Of input demand</small>
        </div>

        {/* Carbon & Environment */}
        {carbonSummary && (
          <div className="metric-card">
            <span>Net avoided CO₂</span>
            <strong>{formatNumeric(carbonSummary.net_avoided_tons, ' tons')}</strong>
            <small>Annual impact</small>
          </div>
        )}

        {/* Utilization */}
        {utilizationSummary && (
          <div className="metric-card">
            <span>System capacity factor</span>
            <strong>{formatPercent(utilizationSummary.capacity_factor_pct)}</strong>
            <small>Based on 24h</small>
          </div>
        )}

        {/* Portfolio Stability */}
        {robustnessSummary && (
          <div className="metric-card">
            <span>Portfolio stability</span>
            <strong>{formatPercent(robustnessSummary.mean_stability)}</strong>
            <small>Mean Jaccard similarity</small>
          </div>
        )}

        {/* Cost */}
        <div className="metric-card">
          <span>Modeled cost</span>
          <strong>{cost == null ? '—' : `${Number(cost).toFixed(1)} M BDT`}</strong>
          <small>Life-cycle estimate</small>
        </div>

        {/* Grid */}
        <div className="metric-card">
          <span>Peak grid load</span>
          <strong>{gridLoad == null ? '—' : `${(Number(gridLoad) / 1000).toFixed(1)} MW`}</strong>
          <small>Simulated max</small>
        </div>
      </div>

      {research?.assumptions && (
        <p className="research-note">
          <strong>Note:</strong> Metrics are based on model assumptions. See "Research insights" for detailed breakdowns.
        </p>
      )}
    </details>
  );
}
