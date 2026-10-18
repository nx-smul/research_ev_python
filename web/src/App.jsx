import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { filterCandidates, paretoRoles } from './mapLogic.js';
import { useDashboardData } from './hooks/useDashboardData.js';
import { useLiveMap } from './hooks/useLiveMap.js';
import { useTheme } from './hooks/useTheme.js';
import { useWorkspace } from './hooks/useWorkspace.js';
import { useURLState, readInitialView, ZONES, DEFAULT_VISIBLE_LAYERS } from './hooks/useURLState.js';
import CandidateTable from './components/CandidateTable.jsx';
import ParetoSelector from './components/ParetoSelector.jsx';
import ResearchInsights from './components/ResearchInsights.jsx';
import EvidencePanel from './components/EvidencePanel.jsx';
import LiveDataPanel from './components/LiveDataPanel.jsx';
import RunSelector from './components/RunSelector.jsx';
import MetricsDashboard from './components/MetricsDashboard.jsx';
import FilterPanel from './components/FilterPanel.jsx';

const MapView = lazy(() => import('./MapView.jsx'));

const LAYER_PRESETS = {
  planning: { candidates: true, demand: true, roads: false, landuse: false, substations: false, 'osm-chargers': false, 'osm-fuel': false },
  live: { candidates: false, demand: false, roads: true, landuse: false, substations: false, 'osm-chargers': true, 'osm-fuel': true },
  all: { candidates: true, demand: true, roads: true, landuse: true, substations: true, 'osm-chargers': true, 'osm-fuel': true },
};

const MAP_LEGEND_ITEMS = [
  { layer: 'candidates', label: 'Candidate', marker: 'candidate' },
  { layer: 'candidates', label: 'Selected', marker: 'selected' },
  { layer: 'demand', label: 'Demand', marker: 'demand' },
  { layer: 'roads', label: 'Roads', marker: 'road' },
  { layer: 'landuse', label: 'Land use', marker: 'landuse' },
  { layer: 'landuse', label: 'Exclusion', marker: 'landuse-excluded' },
  { layer: 'substations', label: 'Substation <15%', marker: 'substation-low' },
  { layer: 'substations', label: 'Substation 15–30%', marker: 'substation-medium' },
  { layer: 'substations', label: 'Substation ≥30%', marker: 'substation-high' },
  { layer: 'osm-chargers', label: 'EV charger', marker: 'osm-charge' },
  { layer: 'osm-fuel', label: 'Fuel station', marker: 'osm-fuel' },
];

const TOUR_STEPS = [
  { title: 'Explore map layers', body: 'Turn candidate, demand, road, land-use, substation, and live OpenStreetMap layers on or off. The legend follows your layer choices.' },
  { title: 'Filter candidate sites', body: 'Search sites or areas, set a suitability range, and use the sortable candidate table to inspect matching locations.' },
  { title: 'Compare candidates', body: 'Select up to three candidates in the table. Their modeled attributes appear side by side; coverage is reported at the solution level only.' },
  { title: 'Interpret results carefully', body: 'Review the run assumptions, input provenance, data freshness, and research notes before treating model results as planning evidence.' },
];

export default function App() {
  const [initialView] = useState(readInitialView);
  const { data, loading, error, isRefreshing: isRefreshingDashboard, retrievedAt: dashboardRetrievedAt, refresh: refreshDashboard, selectRun } = useDashboardData();
  const { liveData, liveLoading, liveError, refresh: refreshLive } = useLiveMap();
  const { theme, setTheme, resolvedTheme } = useTheme(initialView.theme);
  const workspace = useWorkspace();

  const [legendOpen, setLegendOpen] = useState(true);
  const [legendRevealWidth, setLegendRevealWidth] = useState(0);
  const [mapReadyToLoad, setMapReadyToLoad] = useState(false);
  const [tourStep, setTourStep] = useState(null);
  const [mapViewport, setMapViewport] = useState(initialView.viewport);
  const [controlsOpen, setControlsOpen] = useState(() => !window.matchMedia?.('(max-width: 650px)').matches);
  const [zone, setZone] = useState(initialView.zone);
  const [query, setQuery] = useState(initialView.query);
  const [minAhp, setMinAhp] = useState(initialView.minAhp);
  const [maxAhp, setMaxAhp] = useState(Math.max(initialView.minAhp, initialView.maxAhp));
  const [solutionIndex, setSolutionIndex] = useState(initialView.solutionIndex);
  const [selected, setSelected] = useState(null);
  const [comparisonIds, setComparisonIds] = useState(initialView.comparisonIds);
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const [assumptionsPosition, setAssumptionsPosition] = useState({ top: 0, left: 0 });
  const [coordinateCopyStatus, setCoordinateCopyStatus] = useState('');
  const [mapStatus, setMapStatus] = useState('');
  const [mapInstance, setMapInstance] = useState(null);
  const [visibleLayers, setVisibleLayers] = useState(initialView.visibleLayers);
  const [shareNotice, setShareNotice] = useState('');

  const assumptionsTriggerRef = useRef(null);
  const assumptionsPopoverRef = useRef(null);
  const legendItemsRef = useRef(null);
  const legendRef = useRef(null);

  const visibleLegendItems = MAP_LEGEND_ITEMS.filter(item => visibleLayers[item.layer]);
  const visibleLegendKey = visibleLegendItems.map(item => item.marker).join(',');

  useLayoutEffect(() => {
    const updateLegendWidth = () => {
      if (!legendOpen) {
        setLegendRevealWidth(0);
        return;
      }
      const panelWidth = legendRef.current?.parentElement?.clientWidth || window.innerWidth;
      const chipSpace = window.innerWidth <= 650 ? 38 : 52;
      const availableWidth = Math.max(0, panelWidth - chipSpace);
      setLegendRevealWidth(Math.min(legendItemsRef.current?.scrollWidth || 0, availableWidth));
    };
    updateLegendWidth();
    window.addEventListener('resize', updateLegendWidth);
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(updateLegendWidth);
    if (legendRef.current?.parentElement) observer?.observe(legendRef.current.parentElement);
    return () => {
      window.removeEventListener('resize', updateLegendWidth);
      observer?.disconnect();
    };
  }, [legendOpen, visibleLegendKey]);

  const setStatus = useCallback(value => setMapStatus(value), []);

  useEffect(() => {
    const url = createViewUrl({
      zone, query, minAhp, maxAhp, visibleLayers, theme, comparisonIds, solutionIndex,
      selectedId: selected?.candidate_id || '',
    }, mapViewport || mapInstance?.getViewState?.());
    window.history.replaceState({}, '', url);
  }, [mapInstance, mapViewport, zone, query, minAhp, maxAhp, visibleLayers, theme, comparisonIds, solutionIndex, selected?.candidate_id]);

  useEffect(() => {
    let timeoutId;
    let idleId;
    if ('requestIdleCallback' in window) idleId = window.requestIdleCallback(() => setMapReadyToLoad(true), { timeout: 1200 });
    else timeoutId = window.setTimeout(() => setMapReadyToLoad(true), 150);
    return () => {
      if (idleId !== undefined) window.cancelIdleCallback?.(idleId);
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, []);

  useEffect(() => {
    if (!assumptionsOpen) return undefined;
    const updatePosition = () => {
      const bounds = assumptionsTriggerRef.current?.getBoundingClientRect();
      if (!bounds) return;
      const width = Math.min(360, window.innerWidth - 24);
      const popoverHeight = assumptionsPopoverRef.current?.offsetHeight || 320;
      setAssumptionsPosition({
        top: Math.max(12, Math.min(bounds.bottom + 8, window.innerHeight - Math.min(popoverHeight, window.innerHeight - 24) - 12)),
        left: Math.max(12, Math.min(bounds.right - width, window.innerWidth - width - 12)),
      });
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [assumptionsOpen]);

  useEffect(() => {
    if (tourStep === null) return undefined;
    const dialog = document.querySelector('.tour-dialog');
    dialog?.querySelector('button:not(:disabled)')?.focus();
    const handleTourKey = event => {
      if (event.key === 'Escape') setTourStep(null);
      if (event.key === 'Tab' && dialog) {
        const focusable = [...dialog.querySelectorAll('button:not(:disabled)')];
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handleTourKey);
    return () => document.removeEventListener('keydown', handleTourKey);
  }, [tourStep]);

  useEffect(() => {
    const closeOnOutsideClick = event => {
      if (assumptionsOpen && !assumptionsTriggerRef.current?.contains(event.target) && !assumptionsPopoverRef.current?.contains(event.target)) {
        setAssumptionsOpen(false);
      }
    };
    const closeOnEscape = event => {
      if (event.key === 'Escape' && assumptionsOpen) {
        setAssumptionsOpen(false);
        assumptionsTriggerRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [assumptionsOpen]);

  const roles = useMemo(() => paretoRoles(data?.pareto || []), [data]);
  const activeSolution = data?.pareto?.[solutionIndex] || null;
  const research = data?.research || {};
  const selectedIds = useMemo(() => new Set((activeSolution?.selected_station_ids || '').split(';').filter(Boolean)), [activeSolution]);
  const rankMap = useMemo(() => Object.fromEntries((data?.ranked || []).map(row => [row.candidate_id, row])), [data]);
  const candidates = useMemo(() => filterCandidates(data?.candidates?.features || [], rankMap, zone, minAhp, query, maxAhp), [data, rankMap, zone, minAhp, query, maxAhp]);
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
    setCoordinateCopyStatus('');
    setControlsOpen(false);
    const longitude = Number(properties.lon ?? properties.longitude ?? properties.geometry?.coordinates?.[0]);
    const latitude = Number(properties.lat ?? properties.latitude ?? properties.geometry?.coordinates?.[1]);
    if (Number.isFinite(longitude) && Number.isFinite(latitude)) mapInstance?.flyTo({ center: [longitude, latitude], zoom: 14, essential: true });
  }, [mapInstance]);

  const focusCandidate = candidateId => {
    const feature = (data?.candidates?.features || []).find(
      item => String(item.properties?.candidate_id) === String(candidateId),
    );
    if (feature) jumpToSite({ ...feature.properties, geometry: feature.geometry });
  };

  const toggleComparison = candidateId => {
    if (candidateId === '__clear__') {
      setComparisonIds([]);
      return;
    }
    setComparisonIds(current => current.includes(candidateId)
      ? current.filter(id => id !== candidateId)
      : current.length < 3 ? [...current, candidateId] : current);
  };

  const activeFilters = [
    `area=${zone === 'ALL' ? 'All Dhaka' : zone}`,
    `suitability=${Number(minAhp).toFixed(2)}–${Number(maxAhp).toFixed(2)}`,
    query.trim() && `search=${query.trim()}`,
  ].filter(Boolean).join('; ');

  useEffect(() => {
    if (selected || !initialView.selectedId || !data?.candidates?.features) return;
    const feature = data.candidates.features.find(item => String(item.properties?.candidate_id) === initialView.selectedId);
    if (feature) jumpToSite({ ...feature.properties, geometry: feature.geometry });
  }, [data, initialView.selectedId, jumpToSite, selected]);

  const getWorkspaceState = () => ({
    zone, query, minAhp, maxAhp, visibleLayers, theme, comparisonIds,
    solutionIndex,
    viewport: mapViewport || mapInstance?.getViewState?.() || initialView.viewport,
  });

  const applyWorkspaceState = state => {
    setZone(ZONES.includes(state.zone) ? state.zone : 'ALL');
    setQuery(state.query || '');
    setMinAhp(Math.max(0, Math.min(1, Number(state.minAhp) || 0)));
    setMaxAhp(Math.max(Number(state.minAhp) || 0, Math.min(1, Number(state.maxAhp) || 1)));
    setVisibleLayers({ ...DEFAULT_VISIBLE_LAYERS, ...state.visibleLayers });
    if (['auto', 'light', 'dark'].includes(state.theme)) setTheme(state.theme);
    setComparisonIds(Array.isArray(state.comparisonIds) ? state.comparisonIds.slice(0, 3) : []);
    setSolutionIndex(Math.max(0, Number(state.solutionIndex) || 0));
    if (state.viewport) mapInstance?.setViewState?.(state.viewport);
  };

  const shareCurrentView = async () => {
    const url = createViewUrl({
      zone, query, minAhp, maxAhp, visibleLayers, theme, comparisonIds, solutionIndex,
      selectedId: selected?.candidate_id || '',
    }, mapViewport || mapInstance?.getViewState?.());
    try {
      await navigator.clipboard.writeText(url.toString());
      setShareNotice('Shareable map link copied.');
    } catch (shareError) {
      setShareNotice(`Link could not be copied: ${shareError.message}`);
    }
  };

  const downloadMapSnapshot = () => {
    try {
      const image = mapInstance?.exportImage?.();
      if (!image) throw new Error('The map is not ready to export.');
      const sourceCanvas = document.createElement('canvas');
      const mapCanvas = mapInstance.getCanvas?.();
      if (!mapCanvas) throw new Error('The map canvas is unavailable.');
      sourceCanvas.width = mapCanvas.width;
      sourceCanvas.height = mapCanvas.height + 56;
      const context = sourceCanvas.getContext('2d');
      if (!context) throw new Error('This browser cannot prepare a map snapshot.');
      const snapshot = new Image();
      snapshot.onload = () => {
        try {
          context.drawImage(snapshot, 0, 0);
          context.fillStyle = 'rgba(8, 18, 30, 0.92)';
          context.fillRect(0, mapCanvas.height, sourceCanvas.width, 54);
          context.fillStyle = '#ffffff';
          context.font = '14px system-ui, sans-serif';
          context.fillText(`Dhaka EVCS Atlas · ${data?.run?.run_id || 'Research results'} · ${new Date().toLocaleDateString()}`, 14, mapCanvas.height + 17);
          context.font = '10px system-ui, sans-serif';
          context.fillStyle = '#d4dce5';
          const legend = visibleLegendItems.map(item => item.label).join('  ·  ') || 'No visible layers';
          context.fillText(`Legend: ${legend}`.slice(0, 220), 14, mapCanvas.height + 33);
          const scale = document.querySelector('.maplibregl-ctrl-scale')?.textContent || '';
          context.fillText(`${scale ? `Scale ${scale}  ·  ` : ''}Basemap © OpenFreeMap, OpenMapTiles & OpenStreetMap contributors`, 14, mapCanvas.height + 47);
          downloadFile(sourceCanvas.toDataURL('image/png'), 'dhaka-evcs-map.png', 'image/png');
          setShareNotice('Map snapshot downloaded.');
        } catch (snapshotError) {
          setShareNotice(`Map snapshot unavailable: ${snapshotError.message}`);
        }
      };
      snapshot.onerror = () => setShareNotice('Map snapshot could not be prepared.');
      snapshot.src = image;
      setShareNotice('Preparing map snapshot…');
    } catch (snapshotError) {
      setShareNotice(`Map snapshot unavailable: ${snapshotError.message}`);
    }
  };

  const downloadGeoJSON = () => {
    const evidence = data?.evidence || {};
    const source = evidence.inputs?.find(input => /candidate/i.test(`${input.label || ''} ${input.path || ''}`)) || {};
    const fc = {
      type: 'FeatureCollection',
      metadata: {
        run_id: data?.run?.run_id || null,
        data_mode: data?.run?.data_mode || 'unknown',
        data_class: source.data_class || (data?.run?.data_mode === 'demo' ? 'synthetic_demo' : 'unclassified'),
        source_url: source.source_url || null,
        source_retrieved_at: source.retrieved_at || null,
        manifest_path: 'results/run_manifest.json',
      },
      features: (data?.candidates?.features || []).filter(feature => selectedIds.has(feature.properties?.candidate_id)),
    };
    downloadFile(JSON.stringify(fc, null, 2), `evcs-${activeSolution?.solution_id || 'selected'}.geojson`, 'application/geo+json');
  };

  const downloadCSV = () => {
    const rows = data?.pareto || [];
    if (!rows.length) return;
    downloadFile(toCSV(rows), 'pareto-solutions.csv', 'text/csv');
  };

  const downloadCandidateCSV = () => {
    const evidence = data?.evidence || {};
    const source = evidence.inputs?.find(input => /candidate/i.test(`${input.label || ''} ${input.path || ''}`)) || {};
    const candidateRows = candidates;
    const rows = candidateRows.map(feature => ({
      ...feature.properties,
      longitude: feature.geometry?.coordinates?.[0],
      latitude: feature.geometry?.coordinates?.[1],
      run_id: data?.run?.run_id || '',
      data_class: source.data_class || (data?.run?.data_mode === 'demo' ? 'synthetic_demo' : 'unclassified'),
      source_url: source.source_url || '',
      source_retrieved_at: source.retrieved_at || '',
      source_units: source.units || '',
      applied_filter_area: zone === 'ALL' ? 'All Dhaka' : zone,
      applied_filter_min_suitability: minAhp,
      applied_filter_max_suitability: maxAhp,
      applied_filter_search: query,
    }));
    if (rows.length) downloadFile(toCSV(rows), 'candidate-sites-with-provenance.csv', 'text/csv');
  };

  const selectedCoordinates = selected?.geometry?.coordinates;
  const selectedLongitude = Number(selected?.lon ?? selected?.longitude ?? selectedCoordinates?.[0]);
  const selectedLatitude = Number(selected?.lat ?? selected?.latitude ?? selectedCoordinates?.[1]);
  const hasSelectedCoordinates = Number.isFinite(selectedLongitude) && Number.isFinite(selectedLatitude);
  const selectedRank = selected?.topsis_rank ?? rankMap[selected?.candidate_id]?.topsis_rank;
  const selectedScore = Number(selected?.ahp_suitability_score);

  const copySelectedCoordinates = async () => {
    if (!hasSelectedCoordinates || !navigator.clipboard?.writeText) {
      setCoordinateCopyStatus('Coordinates could not be copied in this browser.');
      return;
    }
    try {
      await navigator.clipboard.writeText(`${selectedLongitude.toFixed(6)}, ${selectedLatitude.toFixed(6)}`);
      setCoordinateCopyStatus('Coordinates copied (longitude, latitude).');
    } catch {
      setCoordinateCopyStatus('Coordinates could not be copied in this browser.');
    }
  };

  return <div className="app-shell">
    <header className="topbar">
      <div className="header-brand">
        <button className={`menu-button ${controlsOpen ? 'is-open' : ''}`} type="button" onClick={() => setControlsOpen(open => !open)} aria-expanded={controlsOpen} aria-controls="controls-panel" aria-label={controlsOpen ? 'Close menu' : 'Open menu'} title={controlsOpen ? 'Close menu' : 'Open menu'}>
          <span /><span /><span />
        </button>
        <div className="brand"><div className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 18.5h16M6.5 18V9.5l5.5-4 5.5 4V18M9.5 18v-5h5v5" /><circle cx="18.5" cy="6" r="2.2" /></svg></div><div><h1>Dhaka EVCS Atlas</h1><p>Charging infrastructure · grid planning</p></div></div>
      </div>
      <div className="top-actions">
        <label className="search"><span>⌕</span><input aria-label="Search candidate and zone" list="site-search-options" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search site or zone" /></label>
        <datalist id="site-search-options">{[
          ...new Set([
            ...(data?.candidates?.features || []).flatMap(feature => [feature.properties?.site_name, feature.properties?.candidate_id, feature.properties?.zone_name]),
            ...ZONES.filter(item => item !== 'ALL'),
          ].filter(Boolean)),
        ].map(option => <option key={option} value={option} />)}</datalist>
        <button type="button" className="assumptions-trigger" ref={assumptionsTriggerRef} aria-label="Model assumptions for this run" aria-expanded={assumptionsOpen} aria-controls="model-assumptions-popover" onClick={() => setAssumptionsOpen(open => !open)}>
          <svg aria-hidden="true" viewBox="0 0 20 20"><path d="M3 5h14M5 10h10m-7 5h4" /></svg><span>Model assumptions</span>
        </button>
        <div className="theme-controls" role="group" aria-label="Appearance">
          <button type="button" className="theme-toggle" aria-label="Use automatic theme" title="Use automatic theme" aria-pressed={theme === 'auto'} onClick={() => setTheme('auto')}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" /></svg>
          </button>
          <button type="button" className="theme-toggle" aria-label="Use light theme" title="Use light theme" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></svg>
          </button>
          <button type="button" className="theme-toggle" aria-label="Use dark theme" title="Use dark theme" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M20.2 15.1A8.5 8.5 0 0 1 8.9 3.8 8.5 8.5 0 1 0 20.2 15.1Z" /></svg>
          </button>
        </div>
      </div>
    </header>
    {assumptionsOpen && createPortal(
      <section
        id="model-assumptions-popover"
        className="model-assumptions-popover"
        ref={assumptionsPopoverRef}
        aria-label="Model assumptions for this run"
        style={{ top: assumptionsPosition.top, left: assumptionsPosition.left }}
      >
        <div className="assumptions-popover-heading">
          <strong>Model assumptions for this run</strong>
          <button type="button" aria-label="Close model assumptions" onClick={() => setAssumptionsOpen(false)}>×</button>
        </div>
        {data?.run?.configuration ? <dl>
          <div><dt>Service radius</dt><dd>{formatNumeric(data.run.configuration.optimization?.service_radius_rmax_m, ' m')}</dd></div>
          <div><dt>Budget cap</dt><dd>{formatCurrency(data.run.configuration.optimization?.budget_cap_bdt)}</dd></div>
          <div><dt>Project lifetime</dt><dd>{data.run.configuration.economic?.project_lifetime_years ?? '—'} years</dd></div>
          <div><dt>Discount rate</dt><dd>{formatNumeric(Number(data.run.configuration.economic?.discount_rate) * 100, '%')}</dd></div>
          <div><dt>Population / generations</dt><dd>{data.run.configuration.optimization?.nsga2?.population_size ?? '—'} / {data.run.configuration.optimization?.nsga2?.generations ?? '—'}</dd></div>
          <div><dt>Charger types / power</dt><dd>{Object.values(data.run.configuration.chargers || {}).map(charger => charger.power_kw).filter(value => value != null).join(', ') || '—'} kW</dd></div>
        </dl> : <div className="empty-state">Configuration details were not included with this run.</div>}
      </section>,
      document.body,
    )}

    <main className={`workspace ${controlsOpen ? 'controls-open' : 'controls-closed'}`}>
      <section id="controls-panel" className="control-panel" aria-label="Map and optimization controls" aria-hidden={!controlsOpen} inert={!controlsOpen}>
        <div className="panel-heading"><div><span className="eyebrow">MAP MENU · SCENARIO EXPLORER</span><h2>Plan & compare</h2></div><span className={`run-pill ${data?.run?.data_mode === 'demo' ? 'is-demo' : ''}`}>{data?.run?.data_mode || 'RUN'}</span></div>
        <div className="menu-intro"><span className="menu-intro-icon" aria-hidden="true">⌖</span><div><strong>Dhaka planning workspace</strong><span>Explore candidate locations, demand and live amenities.</span></div><button type="button" className="button button-small" onClick={() => setTourStep(0)}>Take a tour</button></div>
        {error && <div role="alert" className="error-card"><strong>API unavailable</strong><p>{error}</p><button className="button button-small" onClick={refreshDashboard}>Retry</button></div>}
        {loading && <div className="empty-state">Loading run artifacts…</div>}
        <section className="workspace-saves" aria-label="Saved workspaces">
          <label htmlFor="workspace-name">Save this view</label>
          <div className="workspace-save-row"><input id="workspace-name" aria-label="Workspace name" value={workspace.workspaceName} onChange={event => workspace.setWorkspaceName(event.target.value)} placeholder="Workspace name" /><button type="button" className="button button-small" onClick={() => workspace.save(getWorkspaceState)}>Save</button></div>
          <div className="workspace-save-row">
            <select aria-label="Saved workspaces" value={workspace.selectedWorkspace} onChange={event => workspace.setSelectedWorkspace(event.target.value)}>
              <option value="">Saved workspaces ({workspace.savedWorkspaces.length})</option>
              {workspace.savedWorkspaces.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
            </select>
            <button type="button" className="button button-small" onClick={() => workspace.load(workspace.selectedWorkspace, applyWorkspaceState)} disabled={!workspace.selectedWorkspace}>Load</button>
            <button type="button" className="button button-small button-quiet" onClick={workspace.remove} disabled={!workspace.selectedWorkspace} aria-label="Delete saved workspace">×</button>
          </div>
          {workspace.workspaceNotice && <span className="workspace-notice" role="status">{workspace.workspaceNotice}</span>}
        </section>
        <EvidencePanel manifest={data?.run} runMetadata={data} />
        <RunSelector currentRunId={data?.run?.run_id} onSelectRun={selectRun} />
        <div className="field"><label htmlFor="zone-filter">District area</label><select id="zone-filter" value={zone} onChange={event => setZone(event.target.value)}>{ZONES.map(item => <option key={item} value={item}>{item === 'ALL' ? 'All Dhaka' : item}</option>)}</select></div>
        <section className="layer-section" aria-label="Map layers">
          <div className="section-title layer-heading"><div><span className="eyebrow">MAP DISPLAY</span><h3>Layers</h3></div><span className="layer-count">{Object.values(visibleLayers).filter(Boolean).length} on</span></div>
          <div className="layer-presets" role="group" aria-label="Layer presets">
            <button type="button" className={activeLayerPreset === 'planning' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'planning'} onClick={() => applyLayerPreset('planning')}>Planning</button>
            <button type="button" className={activeLayerPreset === 'live' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'live'} onClick={() => applyLayerPreset('live')}>Live assets</button>
            <button type="button" className={activeLayerPreset === 'all' ? 'is-active' : ''} aria-pressed={activeLayerPreset === 'all'} onClick={() => applyLayerPreset('all')}>All layers</button>
          </div>
          <fieldset className="layer-controls"><legend className="visually-hidden">Map layers</legend>{[['candidates', 'Candidate sites'], ['demand', 'Demand areas'], ['roads', 'Road network'], ['landuse', 'Land use'], ['substations', 'Substations'], ['osm-chargers', 'OSM EV chargers'], ['osm-fuel', 'OSM fuel stations']].map(([key, label]) => <label key={key}><input type="checkbox" checked={visibleLayers[key]} onChange={() => toggleLayer(key)} />{label}</label>)}</fieldset>
          <details className="layer-explanations">
            <summary>Layer meaning & evidence</summary>
            <dl>
              <div><dt>Candidate sites</dt><dd>Derived/model-scored planning locations; not confirmed available parcels.</dd></div>
              <div><dt>Demand areas</dt><dd>Input demand values used by the model; modeled estimates, not observed charger sessions.</dd></div>
              <div><dt>Road network</dt><dd>Mapped road geometry. Traffic and speed proxies may be assumed.</dd></div>
              <div><dt>Land use & exclusions</dt><dd>Mapped planning constraints; confirm currency and legal status with the authority.</dd></div>
              <div><dt>Substations</dt><dd>Input utility attributes; not a utility-validated interconnection study.</dd></div>
              <div><dt>Live OSM amenities</dt><dd>Community-mapped facilities, separate from and not used in the optimization.</dd></div>
            </dl>
            {data?.evidence?.inputs?.length > 0 && <ul className="layer-source-list">{data.evidence.inputs.filter(input => /candidate|demand|road|land.?use|substation/i.test(`${input.label || ''} ${input.path || ''}`)).map((input, index) => <li key={`${input.path || input.label}-${index}`}><strong>{input.label || input.path}</strong><span>{input.data_class || 'unclassified'}{input.source_url ? <> · <a href={input.source_url} target="_blank" rel="noreferrer">source</a></> : ''}</span></li>)}</ul>}
          </details>
        </section>
        <LiveDataPanel liveData={liveData} liveLoading={liveLoading} liveError={liveError} onRefresh={refreshLive} />
        <div className="field"><label htmlFor="ahp-filter">Minimum suitability <output>{Number(minAhp).toFixed(2)}</output></label><input id="ahp-filter" type="range" min="0" max={maxAhp} step="0.05" value={minAhp} onChange={event => setMinAhp(Number(event.target.value))} /></div>
        <div className="field"><label htmlFor="ahp-max-filter">Maximum suitability <output>{Number(maxAhp).toFixed(2)}</output></label><input id="ahp-max-filter" type="range" min={minAhp} max="1" step="0.05" value={maxAhp} onChange={event => setMaxAhp(Number(event.target.value))} /></div>
        <div className="metrics-grid">
          <MetricsDashboard solution={activeSolution} research={research} candidates={candidates} />
        </div>
        <CandidateTable
          candidates={candidates}
          rankMap={rankMap}
          selected={selected}
          comparisonIds={comparisonIds}
          onToggleComparison={toggleComparison}
          onJumpToSite={jumpToSite}
          onFocusCandidate={focusCandidate}
          onDownloadCSV={downloadCandidateCSV}
          initialComparisonIds={initialView.comparisonIds}
          activeFilters={activeFilters}
        />
        <div className="divider" />
        <ParetoSelector solutions={data?.pareto} roles={roles} solutionIndex={solutionIndex} onSelect={setSolutionIndex} onDownloadCSV={downloadCSV} />
        <ResearchInsights research={research} onFocusCandidate={focusCandidate} />
        <div className="panel-footer"><button className="button button-primary" onClick={downloadGeoJSON} disabled={!selectedIds.size}>Export selected GeoJSON</button><span>{data?.candidates?.features?.length || 0} sites loaded</span></div>
      </section>
      <section className="map-panel" aria-label="Dhaka charging station map">
        <div className="map-toolbar"><span className="map-label"><span className="live-dot" /> DHAKA, BANGLADESH <span className="map-live-tag">OPENFREEMAP</span></span><button type="button" className="button button-small fit-sites-button" aria-label="Fit candidate sites" title="Fit candidate sites" onClick={() => mapInstance?.fitDataBounds()}><span aria-hidden="true">⌖</span><span>Fit sites</span></button><button type="button" className="button button-small fit-sites-button" aria-label="Fit live assets" title="Fit live assets" onClick={() => mapInstance?.fitFacilityBounds()} disabled={!liveData?.features?.length}><span aria-hidden="true">⚡</span><span>Fit live assets</span></button><button type="button" className="button button-small map-action-button" onClick={shareCurrentView} aria-label="Copy shareable map link">Share</button><button type="button" className="button button-small map-action-button" onClick={downloadMapSnapshot} aria-label="Download map snapshot">Snapshot</button></div>
        <p id="map-keyboard-help" className="visually-hidden">Keyboard map controls: arrow keys pan; plus and minus zoom. Candidate data is also available in the sortable candidate table.</p>
        <Suspense fallback={<div className="map-loading" role="status">Loading interactive map…</div>}>
          {mapReadyToLoad
            ? <MapView data={{ ...data, live: { geojson: { type: 'FeatureCollection', features: liveData?.features || [] } }, candidates: { type: 'FeatureCollection', features: mapCandidates } }} selectedIds={selectedIds} selectedCandidateId={selected?.candidate_id} visibleLayers={visibleLayers} basemap={resolvedTheme} initialViewport={initialView.viewport} onSelect={jumpToSite} onViewportChange={setMapViewport} status={mapStatus || (error ? 'Research map data unavailable. Start FastAPI and check VITE_API_URL.' : '')} setStatus={setStatus} onReady={setMapInstance} />
            : <div className="map-loading" role="status">Preparing interactive map…</div>}
        </Suspense>
        <button
          ref={legendRef}
          type="button"
          className={`map-legend${legendOpen ? ' is-open' : ''}`}
          aria-label={legendOpen ? 'Collapse map legend' : 'Expand map legend'}
          aria-expanded={legendOpen}
          aria-controls="map-legend-items"
          onClick={() => setLegendOpen(open => !open)}
        >
          {!legendOpen && <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /><path d="M12 5v14" /></svg>}
          <span id="map-legend-items" className="map-legend-reveal" aria-hidden={!legendOpen} style={{ width: `${legendOpen ? legendRevealWidth : 0}px` }}>
            <span ref={legendItemsRef} className="map-legend-items">
            {visibleLegendItems.length
              ? visibleLegendItems.map(item => <span key={`${item.layer}-${item.marker}`}><i className={`legend-dot ${item.marker}`} />{item.label}</span>)
              : <span>No map layers enabled</span>}
            </span>
          </span>
        </button>
        {shareNotice && <div className="map-action-status" role="status">{shareNotice}</div>}
        {selected && <aside className="site-card" aria-label="Selected candidate details">
          <button className="close-button" aria-label="Close site information" onClick={() => setSelected(null)}>×</button>
          <span className="eyebrow">CANDIDATE DETAILS</span>
          <h3>{formatPlaceName(selected.site_name || selected.candidate_id)}</h3>
          <p>{formatPlaceName(selected.zone_name || 'Dhaka')} · {selected.candidate_id}</p>
          <dl className="site-details">
            <div><dt>Suitability</dt><dd>{Number.isFinite(selectedScore) ? selectedScore.toFixed(2) : '—'}</dd></div>
            <div><dt>TOPSIS rank</dt><dd>{selectedRank ?? '—'}</dd></div>
            <div><dt>Coordinates</dt><dd>{hasSelectedCoordinates ? `${selectedLongitude.toFixed(5)}, ${selectedLatitude.toFixed(5)}` : '—'}</dd></div>
          </dl>
          <div className="site-card-actions">
            <button type="button" className="button button-small" onClick={copySelectedCoordinates} disabled={!hasSelectedCoordinates}>Copy coordinates</button>
          </div>
          {coordinateCopyStatus && <span className="site-copy-status" role="status">{coordinateCopyStatus}</span>}
        </aside>}
      </section>
    </main>

    {tourStep !== null && <div className="scrim" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setTourStep(null); }}>
      <section className="settings-dialog tour-dialog" role="dialog" aria-modal="true" aria-labelledby="tour-title">
        <div className="dialog-heading"><div><span className="eyebrow">ATLAS WALKTHROUGH · {tourStep + 1}/{TOUR_STEPS.length}</span><h2 id="tour-title">{TOUR_STEPS[tourStep].title}</h2></div><button type="button" className="close-button" aria-label="Close walkthrough" onClick={() => setTourStep(null)}>×</button></div>
        <p>{TOUR_STEPS[tourStep].body}</p>
        <div className="dialog-actions">
          <button type="button" className="button" onClick={() => setTourStep(step => Math.max(0, step - 1))} disabled={tourStep === 0}>Back</button>
          {tourStep < TOUR_STEPS.length - 1
            ? <button type="button" className="button button-primary" onClick={() => setTourStep(step => step + 1)}>Next</button>
            : <button type="button" className="button button-primary" onClick={() => setTourStep(null)}>Finish</button>}
        </div>
      </section>
    </div>}

    <footer className="app-footer"><span>Dhaka EVCS Research · {data?.run?.run_id ? `Run ${String(data.run.run_id).slice(0, 10)}` : 'Current results'}</span><span>Live facility data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · basemap © <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a>, OpenMapTiles &amp; OSM</span></footer>
  </div>;
}

function createViewUrl(state, viewport) {
  const url = new URL(window.location.href);
  url.searchParams.set('area', state.zone);
  if (state.query.trim()) url.searchParams.set('q', state.query.trim());
  else url.searchParams.delete('q');
  url.searchParams.set('min', String(state.minAhp));
  url.searchParams.set('max', String(state.maxAhp));
  url.searchParams.set('layers', Object.entries(state.visibleLayers).filter(([, visible]) => visible).map(([key]) => key).join(','));
  url.searchParams.set('theme', state.theme);
  if (state.comparisonIds.length) url.searchParams.set('compare', state.comparisonIds.join(','));
  else url.searchParams.delete('compare');
  if (state.solutionIndex) url.searchParams.set('solution', String(state.solutionIndex));
  else url.searchParams.delete('solution');
  if (state.selectedId) url.searchParams.set('site', state.selectedId);
  else url.searchParams.delete('site');
  if (viewport?.center?.length === 2 && viewport.center.every(Number.isFinite) && Number.isFinite(viewport.zoom)) {
    url.searchParams.set('lon', viewport.center[0].toFixed(5));
    url.searchParams.set('lat', viewport.center[1].toFixed(5));
    url.searchParams.set('zoom', viewport.zoom.toFixed(2));
  }
  return url;
}


function toCSV(rows) {
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  return [columns, ...rows.map(row => columns.map(key => row[key] ?? ''))]
    .map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(','))
    .join('\r\n');
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—';
}

function formatCurrency(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 0 })} BDT` : '—';
}

function formatNumeric(value, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : '—';
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
