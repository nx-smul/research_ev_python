import { useState } from 'react';

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—';
}

function formatSigned(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number > 0 ? '+' : ''}${number.toFixed(1)}` : '—';
}

function formatCurrency(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 0 })} BDT` : '—';
}

export function formatPlaceName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function ResearchDownload({ children, ...props }) {
  return <button type="button" className="research-download" {...props}>{children}</button>;
}

function downloadResearchCSV(rows, filename) {
  if (!rows.length) return;
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const csv = [columns, ...rows.map(row => columns.map(key => row[key] ?? ''))]
    .map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(','))
    .join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default function ResearchInsights({ research, onFocusCandidate }) {
  const uncertaintySummary = research.uncertainty_summary || {};
  const uncertainSites = research.uncertainty_site_screen || [];
  const equityRows = research.equity_accessibility || [];
  const queueRows = research.queueing_screen || [];
  const gridRows = research.grid_upgrade_screen || [];
  const investmentRows = research.investment_scenarios || [];
  const profileRows = research.time_of_day_load_profile || [];
  const carbonRows = research.carbon_analysis || [];
  const utilizationRows = research.utilization_analysis || [];
  const robustnessPath = research.portfolio_robustness;
  const unmetDemand = research.unmet_demand_analysis || [];
  const travelBurden = research.travel_burden_analysis || [];
  const ahpSensitivity = research.ahp_weight_sensitivity || [];

  if (!uncertainSites.length && !equityRows.length && !queueRows.length && !carbonRows.length) {
    return (
      <section className="research-insights" aria-label="Research insights">
        <div className="section-title"><div><span className="eyebrow">RUN ANALYTICS</span><h3>Research insights</h3></div><span className="run-pill">OPTIONAL</span></div>
        <div className="empty-state">No research extensions found for this run. Rerun the pipeline to generate them.</div>
      </section>
    );
  }

  return (
    <section className="research-insights" aria-label="Research insights">
      <div className="section-title"><div><span className="eyebrow">RUN ANALYTICS</span><h3>Research insights</h3></div><span className="run-pill">{uncertaintySummary.samples ? `${uncertaintySummary.samples} scenarios` : 'OPTIONAL'}</span></div>

      <details className="research-card" open>
        <summary>Robustness & site stability</summary>
        <p className="research-note">Heuristic Monte Carlo screen; not repeated optimization.</p>
        {uncertaintySummary.samples > 0 && <div className="uncertainty-range">
          <span>Reachable demand</span><strong>{formatPercent(uncertaintySummary.reachable_demand_pct_mean)} mean</strong>
          <small>{formatPercent(uncertaintySummary.reachable_demand_pct_p05)}–{formatPercent(uncertaintySummary.reachable_demand_pct_p95)} p05–p95</small>
        </div>}
        <div className="research-rank-list">{uncertainSites.slice(0, 5).map((site, index) => <button type="button" key={site.candidate_id} className="research-rank" onClick={() => onFocusCandidate(site.candidate_id)} title={`Show ${formatPlaceName(site.site_name || site.candidate_id)} on map`}>
          <span>{index + 1}. {formatPlaceName(site.site_name || site.candidate_id)}</span><b>{Number(site.selection_frequency_pct || 0).toFixed(0)}%</b><i><span style={{ width: `${Math.max(0, Math.min(100, Number(site.selection_frequency_pct) || 0))}%` }} /></i>
        </button>)}</div>
        <ResearchDownload onClick={() => downloadResearchCSV(uncertainSites, 'uncertainty-site-stability.csv')} disabled={!uncertainSites.length}>Download stability CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>Carbon & emissions analysis</summary>
        <p className="research-note">Assumption-based carbon screen; fleet composition and emissions factors are estimated.</p>
        {carbonRows.length > 0 && <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Station</th><th>Annual kWh</th><th>Avoided CO₂</th><th>Grid CO₂</th><th>Net benefit</th></tr></thead><tbody>{carbonRows.map(row => <tr key={row.candidate_id}><td>{formatPlaceName(row.site_name || row.candidate_id)}</td><td>{Number(row.modeled_annual_kwh_served || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td><td>{Number(row.avoided_ice_emissions_tons_co2 || 0).toFixed(1)} tons</td><td>{Number(row.added_grid_emissions_tons_co2 || 0).toFixed(1)} tons</td><td>{Number(row.net_avoided_emissions_tons_co2 || 0).toFixed(2)} tons</td></tr>)}</tbody></table></div>}
        <ResearchDownload onClick={() => downloadResearchCSV(carbonRows, 'carbon-analysis.csv')} disabled={!carbonRows.length}>Download carbon CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>Charger utilization</summary>
        <p className="research-note">Utilization estimates under assumed service window; not observed data.</p>
        {utilizationRows.length > 0 && <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Station</th><th>Chargers</th><th>Power</th><th>Daily Energy</th><th>Capacity factor</th></tr></thead><tbody>{utilizationRows.map(row => <tr key={row.candidate_id}><td>{formatPlaceName(row.site_name || row.candidate_id)}</td><td>{Number(row.total_chargers || 0)}</td><td>{Number(row.total_power_kw || 0).toFixed(1)} kW</td><td>{Number(row.daily_energy_kwh || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh</td><td>{formatPercent(row.capacity_factor_pct)}</td></tr>)}</tbody></table></div>}
        <ResearchDownload onClick={() => downloadResearchCSV(utilizationRows, 'utilization-analysis.csv')} disabled={!utilizationRows.length}>Download utilization CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>Area access comparison</summary>
        <p className="research-note">Spatial access proxy only—not a socioeconomic equity measure.</p>
        <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Area</th><th>Access</th><th>Gap</th></tr></thead><tbody>{equityRows.map(row => <tr key={`${row.group_field}-${row.group}`}><td>{formatPlaceName(row.group)}</td><td>{formatPercent(row.modeled_access_pct)}</td><td>{formatSigned(row.gap_vs_citywide_pp)} pp</td></tr>)}</tbody></table></div>
        <ResearchDownload onClick={() => downloadResearchCSV(equityRows, 'area-access-comparison.csv')} disabled={!equityRows.length}>Download area CSV</ResearchDownload>
      </details>

      <LoadProfilePanel profileRows={profileRows} />

      <details className="research-card">
        <summary>Unmet demand & travel burden</summary>
        <p className="research-note">Modeled access gaps; not empirical measurements.</p>
        {unmetDemand.length > 0 && <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Demand ID</th><th>Zone</th><th>Unmet kWh</th><th>Distance to station</th></tr></thead><tbody>{unmetDemand.slice(0, 15).map(row => <tr key={row.demand_id}><td>{row.demand_id}</td><td>{formatPlaceName(row.zone_name)}</td><td>{Number(row.demand_kwh_day || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td><td>{Number(row.distance_to_nearest_station_m || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} m</td></tr>)}</tbody></table></div>}
        <p className="research-note">Showing top 15 unserved demand points.</p>
        <ResearchDownload onClick={() => downloadResearchCSV(unmetDemand, 'unmet-demand-analysis.csv')} disabled={!unmetDemand.length}>Download unmet CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>Station operations & grid screen</summary>
        <p className="research-note">Queue and interconnection values are assumption-based screening estimates.</p>
        <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Station</th><th>Wait</th><th>Upgrade screen</th></tr></thead><tbody>{queueRows.map(row => {
          const grid = gridRows.find(item => item.candidate_id === row.candidate_id);
          return <tr key={row.candidate_id}><td>{formatPlaceName(row.site_name || row.candidate_id)}</td><td>{row.estimated_peak_wait_minutes == null ? 'Unstable' : `${Number(row.estimated_peak_wait_minutes).toFixed(1)} min`}</td><td>{grid ? formatCurrency(grid.total_upgrade_cost_screen_bdt) : '—'}</td></tr>;
        })}</tbody></table></div>
        <ResearchDownload onClick={() => downloadResearchCSV(queueRows, 'station-queue-screen.csv')} disabled={!queueRows.length}>Queue CSV</ResearchDownload>
        <ResearchDownload onClick={() => downloadResearchCSV(gridRows, 'grid-upgrade-screen.csv')} disabled={!gridRows.length}>Grid CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>AHP weight sensitivity</summary>
        <p className="research-note">Test how site rankings change under different weight scenarios.</p>
        {ahpSensitivity.length > 0 && <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Station</th><th>Base rank</th><th>Traffic-focused</th><th>Cost-focused</th><th>Stability</th></tr></thead><tbody>{ahpSensitivity.slice(0, 10).map(row => <tr key={row.candidate_id}><td>{formatPlaceName(row.site_name || row.candidate_id)}</td><td>{row.base_rank}</td><td>{row.traffic_focused_rank}</td><td>{row.cost_focused_rank}</td><td>{row.stability_category}</td></tr>)}</tbody></table></div>}
        <p className="research-note">Showing top 10 base-ranked sites.</p>
        <ResearchDownload onClick={() => downloadResearchCSV(ahpSensitivity, 'ahp-weight-sensitivity.csv')} disabled={!ahpSensitivity.length}>Download AHP CSV</ResearchDownload>
      </details>

      <details className="research-card">
        <summary>Investment & field validation</summary>
        <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Budget</th><th>Model</th><th>Annual surplus</th></tr></thead><tbody>{investmentRows.slice(0, 8).map((row, index) => <tr key={`${row.budget_scenario}-${row.operating_model}-${index}`}><td>{row.budget_scenario?.replaceAll('_', ' ')}</td><td>{row.operating_model || row.status}</td><td>{row.annual_net_operating_surplus_bdt == null ? '—' : formatCurrency(row.annual_net_operating_surplus_bdt)}</td></tr>)}</tbody></table></div>
        <p className="research-note">Tariff, operating cost and emissions inputs are scenarios, not forecasts.</p>
        <ResearchDownload onClick={() => downloadResearchCSV(investmentRows, 'investment-scenarios.csv')} disabled={!investmentRows.length}>Investment CSV</ResearchDownload>
        <ResearchDownload onClick={() => downloadResearchCSV(research.field_validation_template || [], 'field-validation-template.csv')} disabled={!research.field_validation_template?.length}>Field visit template</ResearchDownload>
      </details>
    </section>
  );
}

function LoadProfilePanel({ profileRows }) {
  const [profileDay, setProfileDay] = useState('weekday');
  const [profileSeason, setProfileSeason] = useState('dry');
  const filtered = profileRows.filter(row => row.day_type === profileDay && row.season === profileSeason);
  const uniqueDays = [...new Set(profileRows.map(row => row.day_type))];
  const uniqueSeasons = [...new Set(profileRows.map(row => row.season))];

  return (
    <details className="research-card">
      <summary>Hourly load profile</summary>
      <div className="profile-selectors">
        <label>Day <select aria-label="Profile day" value={profileDay} onChange={event => setProfileDay(event.target.value)}>{uniqueDays.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Season <select aria-label="Profile season" value={profileSeason} onChange={event => setProfileSeason(event.target.value)}>{uniqueSeasons.map(value => <option key={value}>{value}</option>)}</select></label>
      </div>
      {filtered.length > 0 ? <div className="hourly-chart" role="img" aria-label={`${profileDay} ${profileSeason} modeled load profile, 24 hours`}>
        {filtered.sort((a, b) => Number(a.hour) - Number(b.hour)).map(row => <span key={row.hour} title={`${String(row.hour).padStart(2, '0')}:00 · ${Number(row.average_load_kw).toLocaleString(undefined, { maximumFractionDigits: 0 })} kW`} style={{ height: `${Math.max(4, Number(row.hourly_share_pct) / Math.max(...filtered.map(item => Number(item.hourly_share_pct))) * 100)}%` }} />)}
      </div> : <div className="empty-state">No hourly profile in this run.</div>}
      <ResearchDownload onClick={() => downloadResearchCSV(profileRows, 'modeled-hourly-load.csv')} disabled={!profileRows.length}>Download profile CSV</ResearchDownload>
    </details>
  );
}
