import { useCallback, useEffect, useMemo, useState } from 'react';
import MapView from './MapView.jsx';
import { filterCandidates, paretoRoles } from './mapLogic.js';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const ZONES = ['ALL', 'Gulshan / Banani / Baridhara', 'Motijheel Commercial Zone (CBD)', 'Mirpur (1, 10, 11, DOHS)', 'Uttara North Gateway', 'Mohakhali & Tejgaon Industrial', 'Dhanmondi & Mohammadpur', 'Old Dhaka (Lalbagh/Sutrapur/Sadarghat)', 'Purbachal 300ft Corridor'];
const THEME_KEY = 'dhaka-evcs-theme';
const LAYER_PRESETS = {
  planning: { candidates: true, demand: true, roads: false, landuse: false, substations: false, 'osm-chargers': false, 'osm-fuel': false },
  live: { candidates: false, demand: false, roads: true, landuse: false, substations: false, 'osm-chargers': true, 'osm-fuel': true },
  all: { candidates: true, demand: true, roads: true, landuse: true, substations: true, 'osm-chargers': true, 'osm-fuel': true },
};

export default function App() {
  const [data, setData] = useState(null);
  const [liveData, setLiveData] = useState(null);
  const [liveLoading, setLiveLoading] = useState(true);
  const [liveError, setLiveError] = useState('');
  const [liveRefresh, setLiveRefresh] = useState(0);
  const [dashboardRefresh, setDashboardRefresh] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [controlsOpen, setControlsOpen] = useState(() => !window.matchMedia?.('(max-width: 650px)').matches);
  const [zone, setZone] = useState('ALL');
  const [query, setQuery] = useState('');
  const [minAhp, setMinAhp] = useState(0);
  const [solutionIndex, setSolutionIndex] = useState(0);
  const [profileDay, setProfileDay] = useState('weekday');
  const [profileSeason, setProfileSeason] = useState('dry');
  const [selected, setSelected] = useState(null);
  const [mapStatus, setMapStatus] = useState('');
  const [mapInstance, setMapInstance] = useState(null);
  const [theme, setTheme] = useState(() => {
    const saved = window.localStorage.getItem(THEME_KEY);
    return ['auto', 'light', 'dark'].includes(saved) ? saved : 'auto';
  });
  const [resolvedTheme, setResolvedTheme] = useState('light');
  const [visibleLayers, setVisibleLayers] = useState({ candidates: true, demand: true, roads: false, landuse: false, substations: false, 'osm-chargers': true, 'osm-fuel': true });

  const setStatus = useCallback(value => setMapStatus(value), []);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const applyTheme = () => {
      const resolved = theme === 'auto' ? (media?.matches ? 'dark' : 'light') : theme;
      document.documentElement.dataset.theme = resolved;
      document.querySelector('meta[name="theme-color"]')?.setAttribute(
        'content',
        resolved === 'dark' ? '#0d111b' : '#f4f6fa',
      );
      setResolvedTheme(resolved);
    };
    applyTheme();
    window.localStorage.setItem(THEME_KEY, theme);
    if (theme !== 'auto' || !media) return undefined;
    media.addEventListener?.('change', applyTheme);
    return () => media.removeEventListener?.('change', applyTheme);
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`${API_URL}/api/dashboard`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(`API returned ${response.status}`); return response.json(); })
      .then(payload => { setData(payload); setError(''); })
      .catch(err => { if (err.name !== 'AbortError') setError(`${err.message}. Check the API URL and CORS configuration.`); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [dashboardRefresh]);

  useEffect(() => {
    const controller = new AbortController();
    setLiveLoading(true);
    fetch(`${API_URL}/api/live-map${liveRefresh ? '?refresh=true' : ''}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then(async response => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || `API returned ${response.status}`);
        setLiveData(payload);
        setLiveError('');
      })
      .catch(err => { if (err.name !== 'AbortError') setLiveError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLiveLoading(false); });
    return () => controller.abort();
  }, [liveRefresh]);

  const roles = useMemo(() => paretoRoles(data?.pareto || []), [data]);
  const liveCounts = useMemo(() => {
    const features = liveData?.features || [];
    const hasFacilityType = (feature, type) => Array.isArray(feature.properties?.facility_types)
      ? feature.properties.facility_types.includes(type)
      : feature.properties?.amenity === (type === 'ev_charger' ? 'charging_station' : 'fuel');
    return {
      chargers: features.filter(feature => hasFacilityType(feature, 'ev_charger')).length,
      fuel: features.filter(feature => hasFacilityType(feature, 'fuel_station')).length,
    };
  }, [liveData]);
  const activeSolution = data?.pareto?.[solutionIndex] || null;
  const research = data?.research || {};
  const uncertainSites = research.uncertainty_site_screen || [];
  const equityRows = research.equity_accessibility || [];
  const queueRows = research.queueing_screen || [];
  const gridRows = research.grid_upgrade_screen || [];
  const investmentRows = research.investment_scenarios || [];
  const profileRows = (research.time_of_day_load_profile || [])
    .filter(row => row.day_type === profileDay && row.season === profileSeason);
  const selectedIds = useMemo(() => new Set((activeSolution?.selected_station_ids || '').split(';').filter(Boolean)), [activeSolution]);
  const rankMap = useMemo(() => Object.fromEntries((data?.ranked || []).map(row => [row.candidate_id, row])), [data]);
  const candidates = useMemo(() => filterCandidates(data?.candidates?.features || [], rankMap, zone, minAhp, query), [data, rankMap, zone, minAhp, query]);
  const mapCandidates = useMemo(() => candidates.map(feature => {
    const rank = rankMap[feature.properties?.candidate_id] || {};
    return {
      ...feature,
      properties: {
        ...feature.properties,
        topsis_score: rank.topsis_score,
        topsis_rank: rank.topsis_rank,
      },
    };
  }), [candidates, rankMap]);
  const toggleLayer = key => setVisibleLayers(previous => ({ ...previous, [key]: !previous[key] }));
  const activeLayerPreset = Object.entries(LAYER_PRESETS)
    .find(([, preset]) => Object.entries(preset).every(([key, value]) => visibleLayers[key] === value))?.[0];
  const applyLayerPreset = preset => setVisibleLayers(LAYER_PRESETS[preset]);

  const jumpToSite = useCallback(properties => {
    setSelected(properties);
    setControlsOpen(false);
    const longitude = Number(properties.lon ?? properties.longitude ?? properties.geometry?.coordinates?.[0]);
    const latitude = Number(properties.lat ?? properties.latitude ?? properties.geometry?.coordinates?.[1]);
    if (Number.isFinite(longitude) && Number.isFinite(latitude)) mapInstance?.flyTo({ center: [longitude, latitude], zoom: 14, essential: true });
  }, [mapInstance]);

  const downloadGeoJSON = () => {
    const fc = { type: 'FeatureCollection', features: (data?.candidates?.features || []).filter(feature => selectedIds.has(feature.properties?.candidate_id)) };
    downloadFile(JSON.stringify(fc, null, 2), `evcs-${activeSolution?.solution_id || 'selected'}.geojson`, 'application/geo+json');
  };
  const downloadCSV = () => {
    const rows = data?.pareto || [];
    if (!rows.length) return;
    const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
    const csv = [columns, ...rows.map(row => columns.map(key => row[key] ?? ''))].map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\r\n');
    downloadFile(csv, 'pareto-solutions.csv', 'text/csv');
  };
  const downloadResearchCSV = (rows, filename) => {
    if (!rows.length) return;
    const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
    const csv = [columns, ...rows.map(row => columns.map(key => row[key] ?? ''))]
      .map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(','))
      .join('\r\n');
    downloadFile(csv, filename, 'text/csv');
  };
  const focusCandidate = candidateId => {
    const feature = (data?.candidates?.features || []).find(
      item => String(item.properties?.candidate_id) === String(candidateId),
    );
    if (feature) jumpToSite({ ...feature.properties, geometry: feature.geometry });
  };
  const uncertaintySummary = research.uncertainty_summary || {};

  return <div className="app-shell">
    <header className="topbar">
      <div className="header-brand">
        <button className={`menu-button ${controlsOpen ? 'is-open' : ''}`} type="button" onClick={() => setControlsOpen(open => !open)} aria-expanded={controlsOpen} aria-controls="controls-panel" aria-label={controlsOpen ? 'Close menu' : 'Open menu'} title={controlsOpen ? 'Close menu' : 'Open menu'}>
          <span /><span /><span />
        </button>
        <div className="brand"><div className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 18.5h16M6.5 18V9.5l5.5-4 5.5 4V18M9.5 18v-5h5v5" /><circle cx="18.5" cy="6" r="2.2" /></svg></div><div><h1>Dhaka EVCS Atlas</h1><p>Charging infrastructure · grid planning</p></div></div>
      </div>
      <div className="top-actions">
        <label className="search"><span>⌕</span><input aria-label="Search candidate and zone" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search site or zone" /></label>
        <label className="theme-control"><span aria-hidden="true">◐</span><span className="visually-hidden">Appearance</span><select aria-label="Appearance" value={theme} onChange={event => setTheme(event.target.value)}><option value="auto">Auto</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
      </div>
    </header>

    <main className={`workspace ${controlsOpen ? 'controls-open' : 'controls-closed'}`}>
      <section id="controls-panel" className="control-panel" aria-label="Map and optimization controls" aria-hidden={!controlsOpen} inert={!controlsOpen}>
        <div className="panel-heading"><div><span className="eyebrow">MAP MENU · SCENARIO EXPLORER</span><h2>Plan & compare</h2></div><span className={`run-pill ${data?.run?.data_mode === 'demo' ? 'is-demo' : ''}`}>{data?.run?.data_mode || 'RUN'}</span></div>
        <div className="menu-intro"><span className="menu-intro-icon" aria-hidden="true">⌖</span><div><strong>Dhaka planning workspace</strong><span>Explore candidate locations, demand and live amenities.</span></div></div>
        {error && <div role="alert" className="error-card"><strong>API unavailable</strong><p>{error}</p><button className="button button-small" onClick={() => setDashboardRefresh(value => value + 1)}>Retry</button></div>}
        {loading && <div className="empty-state">Loading run artifacts…</div>}
        <div className="field"><label htmlFor="zone-filter">District area</label><select id="zone-filter" value={zone} onChange={event => setZone(event.target.value)}>{ZONES.map(item => <option key={item} value={item}>{item === 'ALL' ? 'All Dhaka' : item}</option>)}</select></div>
        <section className="layer-section" aria-label="Map layers">
          <div className="section-title layer-heading"><div><span className="eyebrow">MAP DISPLAY</span><h3>Layers</h3></div><span className="layer-count">{Object.values(visibleLayers).filter(Boolean).length} on</span></div>
          <div className="layer-presets" role="group" aria-label="Layer presets">
            <button type="button" className={activeLayerPreset === 'planning' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'planning'} onClick={() => applyLayerPreset('planning')}>Planning</button>
            <button type="button" className={activeLayerPreset === 'live' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'live'} onClick={() => applyLayerPreset('live')}>Live assets</button>
            <button type="button" className={activeLayerPreset === 'all' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'all'} onClick={() => applyLayerPreset('all')}>All layers</button>
          </div>
          <fieldset className="layer-controls"><legend className="visually-hidden">Map layers</legend>{[['candidates', 'Candidate sites'], ['demand', 'Demand areas'], ['roads', 'Road network'], ['landuse', 'Land use'], ['substations', 'Substations'], ['osm-chargers', 'OSM EV chargers'], ['osm-fuel', 'OSM fuel stations']].map(([key, label]) => <label key={key}><input type="checkbox" checked={visibleLayers[key]} onChange={() => toggleLayer(key)} />{label}</label>)}</fieldset>
        </section>
        <div className={`live-data-note ${liveError ? 'has-error' : ''}`} role={liveError ? 'alert' : 'status'}>
          <div className="live-data-heading"><span className="live-data-icon" aria-hidden="true">↗</span><div><strong>{liveLoading ? 'Loading live OSM assets…' : liveError ? 'Live map data unavailable' : liveData?.is_stale ? 'Showing cached OSM assets' : 'OpenStreetMap assets'}</strong><span>{liveError ? liveError : liveData?.is_stale ? `Refresh failed: ${liveData.refresh_error}` : liveData?.osm_data_timestamp ? `OSM edits through ${new Date(liveData.osm_data_timestamp).toLocaleString()}` : liveData?.retrieved_at ? `Fetched ${new Date(liveData.retrieved_at).toLocaleString()} · OSM edit time unavailable` : 'Public amenities · not modeled demand'}</span></div></div>
          {!liveError && <div className="live-asset-counts"><span><i className="legend-dot osm-charge" />{liveLoading ? '—' : `${liveCounts.chargers} ${liveCounts.chargers === 1 ? 'EV charger' : 'EV chargers'}`}</span><span><i className="legend-dot osm-fuel" />{liveLoading ? '—' : `${liveCounts.fuel} ${liveCounts.fuel === 1 ? 'fuel station' : 'fuel stations'}`}</span><button type="button" className="live-refresh" aria-label="Refresh live OSM data" title="Refresh live OSM data" onClick={() => setLiveRefresh(value => value + 1)}>↻</button></div>}
          {liveError && <button className="text-button" onClick={() => setLiveRefresh(value => value + 1)}>Retry live data</button>}
        </div>
        <div className="field"><label htmlFor="ahp-filter">Minimum suitability <output>{Number(minAhp).toFixed(2)}</output></label><input id="ahp-filter" type="range" min="0" max="0.95" step="0.05" value={minAhp} onChange={event => setMinAhp(Number(event.target.value))} /></div>
        <div className="metrics-grid">
          <Metric label="Candidate sites" value={candidates.length} />
          <Metric label="Chosen stations" value={activeSolution?.open_station_count ?? '—'} />
          <Metric label="Coverage" value={activeSolution?.demand_coverage_pct == null ? '—' : `${Number(activeSolution.demand_coverage_pct).toFixed(1)}%`} />
          <Metric label="Peak grid load" value={activeSolution?.total_grid_power_kw == null ? '—' : `${(Number(activeSolution.total_grid_power_kw) / 1000).toFixed(1)} MW`} />
          <Metric label="Model cost" value={activeSolution?.total_cost_million_bdt == null ? '—' : `${Number(activeSolution.total_cost_million_bdt).toFixed(1)} M BDT`} />
          <Metric label="Input provenance" value={data?.run?.data_mode === 'demo' ? 'Synthetic demo' : data?.run?.run_id ? 'Run documented' : 'Unknown'} />
        </div>
        <div className="divider" />
        <div className="section-title"><div><span className="eyebrow">PARETO TRADE-OFF</span><h3>Choose a solution</h3></div><button className="text-button" onClick={downloadCSV}>CSV ↓</button></div>
        {!data?.pareto?.length ? <div className="empty-state">No Pareto solutions available.</div> : <div className="solution-list">{data.pareto.map((row, index) => <button key={row.solution_id || index} className={`solution-card ${solutionIndex === index ? 'is-active' : ''}`} onClick={() => setSolutionIndex(index)} aria-pressed={solutionIndex === index}>
          <span className="solution-id">{row.solution_id || `S${index + 1}`}</span><span className="solution-role">{roles.roles[index]?.join(' · ') || 'Pareto alternative'}</span><span className="solution-stats">{row.open_station_count ?? '—'} stations <b>{Number(row.demand_coverage_pct || 0).toFixed(1)}% coverage</b></span>
        </button>)}</div>}
        <section className="research-insights" aria-label="Research insights">
          <div className="section-title"><div><span className="eyebrow">RUN ANALYTICS</span><h3>Research insights</h3></div><span className="run-pill">{uncertaintySummary.samples ? `${uncertaintySummary.samples} scenarios` : 'OPTIONAL'}</span></div>
          {!uncertainSites.length && !equityRows.length && !queueRows.length
            ? <div className="empty-state">No research extensions found for this run. Rerun the pipeline to generate them.</div>
            : <>
              <details className="research-card" open>
                <summary>Robustness & site stability</summary>
                <p className="research-note">Heuristic Monte Carlo screen; not repeated optimization.</p>
                {uncertaintySummary.samples > 0 && <div className="uncertainty-range">
                  <span>Reachable demand</span><strong>{formatPercent(uncertaintySummary.reachable_demand_pct_mean)} mean</strong>
                  <small>{formatPercent(uncertaintySummary.reachable_demand_pct_p05)}–{formatPercent(uncertaintySummary.reachable_demand_pct_p95)} p05–p95</small>
                </div>}
                <div className="research-rank-list">{uncertainSites.slice(0, 5).map((site, index) => <button type="button" key={site.candidate_id} className="research-rank" onClick={() => focusCandidate(site.candidate_id)} title={`Show ${formatPlaceName(site.site_name || site.candidate_id)} on map`}>
                  <span>{index + 1}. {formatPlaceName(site.site_name || site.candidate_id)}</span><b>{Number(site.selection_frequency_pct || 0).toFixed(0)}%</b><i><span style={{ width: `${Math.max(0, Math.min(100, Number(site.selection_frequency_pct) || 0))}%` }} /></i>
                </button>)}</div>
                <ResearchDownload onClick={() => downloadResearchCSV(uncertainSites, 'uncertainty-site-stability.csv')} disabled={!uncertainSites.length}>Download stability CSV</ResearchDownload>
              </details>
              <details className="research-card">
                <summary>Area access comparison</summary>
                <p className="research-note">Spatial access proxy only—not a socioeconomic equity measure.</p>
                <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Area</th><th>Access</th><th>Gap</th></tr></thead><tbody>{equityRows.map(row => <tr key={`${row.group_field}-${row.group}`}><td>{formatPlaceName(row.group)}</td><td>{formatPercent(row.modeled_access_pct)}</td><td>{formatSigned(row.gap_vs_citywide_pp)} pp</td></tr>)}</tbody></table></div>
                <ResearchDownload onClick={() => downloadResearchCSV(equityRows, 'area-access-comparison.csv')} disabled={!equityRows.length}>Download area CSV</ResearchDownload>
              </details>
              <details className="research-card">
                <summary>Hourly load profile</summary>
                <div className="profile-selectors">
                  <label>Day <select aria-label="Profile day" value={profileDay} onChange={event => setProfileDay(event.target.value)}>{[...new Set((research.time_of_day_load_profile || []).map(row => row.day_type))].map(value => <option key={value}>{value}</option>)}</select></label>
                  <label>Season <select aria-label="Profile season" value={profileSeason} onChange={event => setProfileSeason(event.target.value)}>{[...new Set((research.time_of_day_load_profile || []).map(row => row.season))].map(value => <option key={value}>{value}</option>)}</select></label>
                </div>
                {profileRows.length > 0 ? <div className="hourly-chart" role="img" aria-label={`${profileDay} ${profileSeason} modeled load profile, 24 hours`}>
                  {profileRows.sort((a, b) => Number(a.hour) - Number(b.hour)).map(row => <span key={row.hour} title={`${String(row.hour).padStart(2, '0')}:00 · ${Number(row.average_load_kw).toLocaleString(undefined, { maximumFractionDigits: 0 })} kW`} style={{ height: `${Math.max(4, Number(row.hourly_share_pct) / Math.max(...profileRows.map(item => Number(item.hourly_share_pct))) * 100)}%` }} />)}
                </div> : <div className="empty-state">No hourly profile in this run.</div>}
                <ResearchDownload onClick={() => downloadResearchCSV(research.time_of_day_load_profile || [], 'modeled-hourly-load.csv')} disabled={!research.time_of_day_load_profile?.length}>Download profile CSV</ResearchDownload>
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
                <summary>Investment & field validation</summary>
                <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Budget</th><th>Model</th><th>Annual surplus</th></tr></thead><tbody>{investmentRows.slice(0, 8).map((row, index) => <tr key={`${row.budget_scenario}-${row.operating_model}-${index}`}><td>{row.budget_scenario?.replaceAll('_', ' ')}</td><td>{row.operating_model || row.status}</td><td>{row.annual_net_operating_surplus_bdt == null ? '—' : formatCurrency(row.annual_net_operating_surplus_bdt)}</td></tr>)}</tbody></table></div>
                <p className="research-note">Tariff, operating cost and emissions inputs are scenarios, not forecasts.</p>
                <ResearchDownload onClick={() => downloadResearchCSV(investmentRows, 'investment-scenarios.csv')} disabled={!investmentRows.length}>Investment CSV</ResearchDownload>
                <ResearchDownload onClick={() => downloadResearchCSV(research.field_validation_template || [], 'field-validation-template.csv')} disabled={!research.field_validation_template?.length}>Field visit template</ResearchDownload>
              </details>
            </>}
        </section>
        <div className="panel-footer"><button className="button button-primary" onClick={downloadGeoJSON} disabled={!selectedIds.size}>Export selected GeoJSON</button><span>{data?.candidates?.features?.length || 0} sites loaded</span></div>
      </section>
      <section className="map-panel" aria-label="Dhaka charging station map">
        <div className="map-toolbar"><span className="map-label"><span className="live-dot" /> DHAKA, BANGLADESH <span className="map-live-tag">OPENFREEMAP</span></span><button className="button button-small fit-sites-button" onClick={() => mapInstance?.fitDataBounds()}><span aria-hidden="true">⌖</span><span>Fit sites</span></button><button className="button button-small fit-sites-button" onClick={() => mapInstance?.fitFacilityBounds()} disabled={!liveData?.features?.length}><span aria-hidden="true">⚡</span><span>Fit live assets</span></button></div>
        <MapView data={{ ...data, live: { geojson: { type: 'FeatureCollection', features: liveData?.features || [] } }, candidates: { type: 'FeatureCollection', features: mapCandidates } }} selectedIds={selectedIds} visibleLayers={visibleLayers} basemap={resolvedTheme} onSelect={jumpToSite} status={mapStatus || (error ? 'Research map data unavailable. Start FastAPI and check VITE_API_URL.' : '')} setStatus={setStatus} onReady={setMapInstance} />
        {selected && <aside className="site-card"><button className="close-button" aria-label="Close site information" onClick={() => setSelected(null)}>×</button><span className="eyebrow">CANDIDATE SITE</span><h3>{formatPlaceName(selected.site_name || selected.candidate_id)}</h3><p>{formatPlaceName(selected.zone_name || 'Dhaka')}</p><span className="site-id">{selected.candidate_id}</span></aside>}
        <div className="map-legend"><span><i className="legend-dot" style={{ backgroundColor: '#7455f7' }} />Selected site</span><span><i className="legend-dot" style={{ backgroundColor: '#2563eb' }} />Candidate</span><span><i className="legend-dot" style={{ backgroundColor: '#089776' }} />EV charger</span><span><i className="legend-dot" style={{ backgroundColor: '#d98612' }} />Fuel station</span></div>
      </section>
    </main>

    <footer className="app-footer"><span>Dhaka EVCS Research · {data?.run?.run_id ? `Run ${String(data.run.run_id).slice(0, 10)}` : 'Current results'}</span><span>Live facility data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · basemap © <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a>, OpenMapTiles &amp; OSM</span></footer>
  </div>;
}

function Metric({ label, value }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}

function ResearchDownload({ children, ...props }) {
  return <button type="button" className="research-download" {...props}>{children}</button>;
}

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

function formatPlaceName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function downloadFile(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}
