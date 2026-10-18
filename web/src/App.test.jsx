import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App.jsx';

vi.mock('./MapView.jsx', () => ({
  default: ({ status, onSelect }) => <>
    <div data-testid="map">{status}</div>
    <button type="button" onClick={() => onSelect({
      site_name: 'Mohakhali_Terminal_Site_1',
      zone_name: 'Badda_Mohakhali',
      candidate_id: 'CS-17',
      ahp_suitability_score: 0.87,
      topsis_rank: 3,
      geometry: { type: 'Point', coordinates: [90.41, 23.81] },
    })}>Mock select candidate</button>
  </>,
}));

const payload = {
  run: {
    run_id: 'test-run', data_mode: 'demo', created_at: '2026-10-09T00:00:00Z',
    configuration: {
      optimization: { service_radius_rmax_m: 5000, budget_cap_bdt: 2500000000, nsga2: { population_size: 100, generations: 250 } },
      economic: { project_lifetime_years: 10, discount_rate: 0.08 },
      chargers: { ac: { power_kw: 22 }, dc: { power_kw: 60 } },
    },
  },
  evidence: {
    status: 'synthetic_demo',
    modeled_results_are_observations: false,
    live_osm_used_in_optimization: false,
    limitations: ['Simulation checks are not utility validation.'],
    input_counts: { total: 4, synthetic: 4, observed_or_derived: 0 },
    inputs: [{ label: 'Demand zones', path: 'data/processed/demand.geojson', data_class: 'synthetic_demo', validation: 'demo-generated' }],
  },
  candidates: { type: 'FeatureCollection', features: [
    { type: 'Feature', geometry: { type: 'Point', coordinates: [90.4, 23.8] }, properties: { candidate_id: 'c1', site_name: 'Test station', zone_name: 'Motijheel_Dilkusha', ahp_suitability_score: 0.9 } },
    { type: 'Feature', geometry: { type: 'Point', coordinates: [90.41, 23.8] }, properties: { candidate_id: 'c2', site_name: 'Second test station', zone_name: 'Motijheel_Dilkusha', ahp_suitability_score: 0.8 } },
  ] },
  demand: { type: 'FeatureCollection', features: [] },
  roads: { type: 'FeatureCollection', features: [{
    type: 'Feature',
    properties: { u: 'test-a', v: 'test-b', length_m: 1250 },
    geometry: { type: 'LineString', coordinates: [[90.4, 23.8], [90.41, 23.8]] },
  }] },
  landuse: { type: 'FeatureCollection', features: [] }, substations: [],
  pareto: [{ solution_id: 's1', total_cost_bdt: 100, total_cost_million_bdt: 0.0001, demand_coverage_pct: 70, open_station_count: 1, total_grid_power_kw: 1000, selected_station_ids: 'c1' }], ranked: [],
  research: {
    uncertainty_summary: { samples: 250, reachable_demand_pct_mean: 78.4, reachable_demand_pct_p05: 65, reachable_demand_pct_p95: 91 },
    uncertainty_site_screen: [{ candidate_id: 'c1', site_name: 'Stable_Site', selection_frequency_pct: 82 }],
    equity_accessibility: [{ group: 'North_Zone', group_field: 'zone_name', modeled_access_pct: 72.5, gap_vs_citywide_pp: -4.2 }],
    time_of_day_load_profile: [
      { day_type: 'weekday', season: 'dry', hour: 0, average_load_kw: 12, hourly_share_pct: 1.2 },
      { day_type: 'weekend', season: 'dry', hour: 0, average_load_kw: 10, hourly_share_pct: 1.0 },
    ],
    queueing_screen: [{ candidate_id: 'c1', site_name: 'Stable_Site', estimated_peak_wait_minutes: 3.5 }],
    grid_upgrade_screen: [{ candidate_id: 'c1', total_upgrade_cost_screen_bdt: 100000 }],
    investment_scenarios: [{ budget_scenario: 'budget_1x', operating_model: 'commercial', annual_net_operating_surplus_bdt: 250000 }],
    field_validation_template: [{ candidate_id: 'c1', record_status: 'not_visited' }],
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.removeItem('dhaka-evcs-theme');
  window.localStorage.removeItem('dhaka-evcs-workspaces');
  window.history.replaceState({}, '', '/');
  delete document.documentElement.dataset.theme;
});

describe('dashboard UI', () => {
  it('keeps search and map layer controls available', async () => {
    vi.stubGlobal('navigator', Object.assign(Object.create(navigator), {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);
    await waitFor(() => expect(screen.getByText('Choose a solution')).toBeInTheDocument());
    expect(screen.getByText('SYNTHETIC DEMO')).toBeInTheDocument();
    expect(screen.getByText(/not observed demand, utilization, or an investment forecast/)).toBeInTheDocument();
    expect(screen.getByText('Run inputs & provenance (1)')).toBeInTheDocument();
    expect(screen.getAllByText('Demand zones')).toHaveLength(2);
    expect(screen.getByTitle(/Share of input demand assigned/)).toBeInTheDocument();
    const candidateTable = screen.getByRole('table', { name: /Filtered candidate sites/ });
    const scoreSort = screen.getByRole('button', { name: /Sort by suitability score/ });
    fireEvent.click(scoreSort);
    expect(candidateTable.querySelector('tbody tr')).toHaveTextContent('Second test station');
    expect(candidateTable.querySelector('th[aria-sort="ascending"]')).toHaveTextContent('Suitability');
    fireEvent.click(screen.getByRole('button', { name: /Sort by candidate ID/ }));
    expect(candidateTable.querySelector('th[aria-sort="ascending"]')).toHaveTextContent('Candidate');
    const autoTheme = screen.getByRole('button', { name: 'Use automatic theme' });
    const lightTheme = screen.getByRole('button', { name: 'Use light theme' });
    const darkTheme = screen.getByRole('button', { name: 'Use dark theme' });
    expect(autoTheme).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.click(darkTheme);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));
    expect(darkTheme).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(lightTheme);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'));
    expect(lightTheme).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(autoTheme);
    expect(autoTheme).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('combobox', { name: 'Search candidate and zone' })).toBeInTheDocument();
    expect(document.querySelector('#site-search-options option[value="Test station"]')).toBeInTheDocument();
    expect(screen.getByText('1.0 MW')).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Map layers' })).toBeInTheDocument();
    const menuButton = screen.getByRole('button', { name: 'Close menu' });
    expect(menuButton).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(menuButton);
    expect(screen.getByRole('button', { name: 'Open menu' })).toHaveAttribute('aria-expanded', 'false');
    expect(document.querySelector('#controls-panel')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('button', { name: 'Dismiss menu overlay' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true');
    expect(document.querySelector('#controls-panel')).toHaveAttribute('aria-hidden', 'false');
    expect(screen.queryByRole('button', { name: 'Calculate road distance' })).not.toBeInTheDocument();
    const demandLayer = screen.getByRole('checkbox', { name: 'Demand areas' });
    expect(demandLayer).toBeChecked();
    expect(screen.getByText('Demand')).toBeInTheDocument();
    fireEvent.click(demandLayer);
    expect(demandLayer).not.toBeChecked();
    expect(screen.queryByText('Demand', { selector: '.map-legend-items > span' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Live assets' }));
    expect(screen.getByRole('button', { name: 'Live assets' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('checkbox', { name: 'Candidate sites' })).not.toBeChecked();
    expect(screen.queryByText('Candidate', { selector: '.map-legend-items > span' })).not.toBeInTheDocument();
    expect(screen.getByText('Roads', { selector: '.map-legend-items > span' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Planning' }));
    expect(screen.getByRole('checkbox', { name: 'Candidate sites' })).toBeChecked();
    expect(screen.getByText('Candidate', { selector: '.map-legend-items > span' })).toBeInTheDocument();
    expect(screen.getByText('Demand', { selector: '.map-legend-items > span' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'OSM EV chargers' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM fuel stations' })).not.toBeChecked();
    expect(screen.getByText('OPENFREEMAP')).toBeInTheDocument();
    const legend = screen.getByRole('button', { name: 'Collapse map legend' });
    expect(legend).toBeInTheDocument();
    expect(legend.querySelector('svg')).not.toBeInTheDocument();
    expect(within(legend).getByText('Selected')).toBeInTheDocument();
    fireEvent.click(legend);
    const collapsedLegend = screen.getByRole('button', { name: 'Expand map legend' });
    expect(collapsedLegend).toHaveAttribute('aria-expanded', 'false');
    expect(collapsedLegend.querySelectorAll('svg path')).toHaveLength(2);
    expect(document.querySelector('#map-legend-items')).toHaveAttribute('aria-hidden', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Expand map legend' }));
    expect(screen.getByRole('button', { name: 'Collapse map legend' }).querySelector('svg')).not.toBeInTheDocument();
    expect(document.querySelector('#map-legend-items')).toHaveAttribute('aria-hidden', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Mock select candidate' }));
    expect(screen.getByRole('heading', { name: 'Mohakhali Terminal Site 1' })).toBeInTheDocument();
    expect(screen.getByText('Badda Mohakhali · CS-17')).toBeInTheDocument();
    expect(screen.getByText('0.87')).toBeInTheDocument();
    expect(screen.getByText('3', { selector: 'dd' })).toBeInTheDocument();
    expect(screen.getByText('90.41000, 23.81000')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Copy coordinates' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Coordinates copied'));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('90.410000, 23.810000');
  });

  it('follows system color preference while appearance is set to auto', async () => {
    let systemChange;
    const media = {
      matches: true,
      addEventListener: vi.fn((event, callback) => { systemChange = callback; }),
      removeEventListener: vi.fn(),
    };
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));

    render(<App />);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));
    expect(window.localStorage.getItem('dhaka-evcs-theme')).toBe('auto');

    media.matches = false;
    systemChange({ matches: false });
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'));
  });

  it('supports candidate comparisons, score bounds, and assumption disclosures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);

    await screen.findByText('Choose a solution');
    expect(screen.getByText(/Run created/)).toBeInTheDocument();
    expect(screen.getByText('Automatically refreshes every minute while this tab is open.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Refresh results' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Layer meaning & evidence'));
    expect(screen.getByText(/modeled estimates, not observed charger sessions/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Candidate data table (2)'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Compare Test station' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Compare Second test station' }));
    expect(screen.getByRole('region', { name: 'Candidate comparison' })).toBeInTheDocument();
    expect(screen.getByText('Compare candidates (2/3)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(screen.queryByRole('region', { name: 'Candidate comparison' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('slider', { name: /Maximum suitability/ }), { target: { value: '0.85' } });
    expect(screen.getByText('Candidate data table (1)')).toBeInTheDocument();
    const assumptionsTrigger = screen.getByRole('button', { name: 'Model assumptions for this run' });
    fireEvent.click(assumptionsTrigger);
    expect(screen.getByRole('region', { name: 'Model assumptions for this run' })).toBeInTheDocument();
    expect(screen.getByText('5,000 m')).toBeInTheDocument();
    expect(screen.getByText('22, 60 kW')).toBeInTheDocument();
  });

  it('saves/restores local workspaces and guides users through the atlas', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);
    await screen.findByText('Choose a solution');

    fireEvent.change(screen.getByRole('textbox', { name: 'Workspace name' }), { target: { value: 'Planning scenario A' } });
    expect(screen.getByRole('textbox', { name: 'Workspace name' })).toHaveValue('Planning scenario A');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Saved “Planning scenario A”')).toHaveAttribute('role', 'status');
    expect(JSON.parse(window.localStorage.getItem('dhaka-evcs-workspaces'))[0].name).toBe('Planning scenario A');
    fireEvent.change(screen.getByRole('combobox', { name: 'District area' }), { target: { value: 'Motijheel Commercial Zone (CBD)' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Saved workspaces' }), { target: { value: 'Planning scenario A' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load' }));
    expect(screen.getByRole('combobox', { name: 'District area' })).toHaveValue('ALL');

    fireEvent.click(screen.getByRole('button', { name: 'Take a tour' }));
    expect(screen.getByRole('dialog', { name: /Explore map layers/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('dialog', { name: /Filter candidate sites/ })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('restores shareable filters and visible layers from the URL', async () => {
    window.history.replaceState({}, '', '/?area=Motijheel%20Commercial%20Zone%20(CBD)&q=c1&min=0.5&max=0.95&layers=candidates&theme=dark&compare=c1');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);
    await screen.findByText('Choose a solution');

    expect(screen.getByRole('combobox', { name: 'District area' })).toHaveValue('Motijheel Commercial Zone (CBD)');
    expect(screen.getByRole('combobox', { name: 'Search candidate and zone' })).toHaveValue('c1');
    expect(screen.getByRole('slider', { name: /Minimum suitability/ })).toHaveValue('0.5');
    expect(screen.getByRole('checkbox', { name: 'Candidate sites' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Demand areas' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM EV chargers' })).not.toBeChecked();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('checkbox', { name: 'Compare Test station' })).toBeChecked();
  });

  it('handles empty data and presents an API error accessibly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unavailable')));
    render(<App />);
    expect(await screen.findByText('API unavailable')).toBeInTheDocument();
    expect(await screen.findByText(/Research map data unavailable/)).toBeInTheDocument();
  });

  it('retries dashboard data without reloading the page', async () => {
    let dashboardRequests = 0;
    vi.stubGlobal('fetch', vi.fn(url => {
      if (String(url).endsWith('/api/dashboard')) {
        dashboardRequests += 1;
        if (dashboardRequests === 1) return Promise.reject(new Error('network unavailable'));
        return Promise.resolve({ ok: true, json: async () => payload });
      }
      return Promise.resolve({ ok: true, json: async () => ({ type: 'FeatureCollection', features: [] }) });
    }));
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(screen.getByText('Choose a solution')).toBeInTheDocument());
    expect(dashboardRequests).toBe(2);
  });

  it('switches dashboard data when a historical run is selected', async () => {
    const historicalPayload = {
      ...payload,
      run: { ...payload.run, run_id: 'run-old-123', created_at: '2026-10-08T00:00:00Z' },
      candidates: { ...payload.candidates, features: [payload.candidates.features[1]] },
    };
    vi.stubGlobal('fetch', vi.fn(url => {
      const target = String(url);
      if (target.endsWith('/api/runs')) {
        return Promise.resolve({ ok: true, json: async () => ({ runs: [{ run_id: 'run-old-123', created_at: '2026-10-08T00:00:00Z', data_mode: 'demo' }] }) });
      }
      if (target.endsWith('/api/run/run-old-123')) {
        return Promise.resolve({ ok: true, json: async () => historicalPayload });
      }
      return Promise.resolve({ ok: true, json: async () => payload });
    }));
    render(<App />);

    await screen.findByText('Choose a solution');
    fireEvent.click(screen.getByText('Run history (1)'));
    fireEvent.click(screen.getByRole('button', { name: /run-old-12/ }));

    await waitFor(() => expect(screen.getByText(/Run run-old-12/)).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/run/run-old-123'), expect.any(Object));
    expect(screen.getByText('Candidate data table (1)')).toBeInTheDocument();
  });

  it('loads live OpenStreetMap data separately from modeled dashboard results', async () => {
    const liveMap = {
      type: 'FeatureCollection',
      source: 'OpenStreetMap',
      retrieved_at: '2026-10-09T00:00:00Z',
      osm_data_timestamp: '2026-10-09T00:00:00Z',
      features: [
        { type: 'Feature', properties: { amenity: 'charging_station', facility_types: ['ev_charger'] } },
        { type: 'Feature', properties: { amenity: 'fuel', facility_types: ['fuel_station'] } },
        { type: 'Feature', properties: { amenity: 'fuel', facility_types: ['ev_charger', 'fuel_station'] } },
      ],
    };
    vi.stubGlobal('fetch', vi.fn(url => Promise.resolve({
      ok: true,
      json: async () => String(url).includes('/api/live-map') ? liveMap : payload,
    })));
    render(<App />);

    expect(await screen.findByText('2 EV chargers')).toBeInTheDocument();
    expect(screen.getByText('2 fuel stations')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'OSM EV chargers' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM fuel stations' })).toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: 'OSM EV chargers' }));
    expect(screen.getByRole('checkbox', { name: 'OSM EV chargers' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM fuel stations' })).toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: 'OSM EV chargers' }));
    expect(screen.getByText(/OSM edits through/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fit live assets' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Fit live assets' }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh live OSM data' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/live-map?refresh=true'),
      expect.objectContaining({ cache: 'no-store' }),
    ));
  });

  it('surfaces run research insights and links stable sites to the map', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);

    expect(await screen.findByText('Research insights')).toBeInTheDocument();
    const assumptionsTrigger = screen.getByRole('button', { name: 'Model assumptions for this run' });
    expect(assumptionsTrigger).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(assumptionsTrigger);
    expect(assumptionsTrigger).toHaveAttribute('aria-expanded', 'true');
    const assumptionsPopover = screen.getByRole('region', { name: 'Model assumptions for this run' });
    expect(assumptionsPopover.parentElement).toBe(document.body);
    expect(assumptionsPopover).toHaveTextContent('Service radius');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('region', { name: 'Model assumptions for this run' })).not.toBeInTheDocument();
    expect(assumptionsTrigger).toHaveAttribute('aria-expanded', 'false');
    expect(assumptionsTrigger).toHaveFocus();
    expect(screen.getByText('250 scenarios')).toBeInTheDocument();
    expect(screen.getByText('78.4% mean')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Stable Site/ }));
    expect(screen.getByRole('heading', { name: 'Test Station' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    fireEvent.click(screen.getByText('Area access comparison'));
    expect(screen.getByText('North Zone')).toBeInTheDocument();
    expect(screen.getByText('72.5%')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Hourly load profile'));
    expect(screen.getByRole('img', { name: /weekday dry modeled load profile/ })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox', { name: 'Profile day' }), { target: { value: 'weekend' } });
    expect(screen.getByRole('img', { name: /weekend dry modeled load profile/ })).toBeInTheDocument();
    fireEvent.click(screen.getByText('Station operations & grid screen'));
    expect(screen.getByText('3.5 min')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Investment & field validation'));
    expect(screen.getByText('commercial')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Field visit template' })).toBeEnabled();
  });
});
