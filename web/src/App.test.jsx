import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App.jsx';

vi.mock('./MapView.jsx', () => ({
  default: ({ status, onSelect }) => <>
    <div data-testid="map">{status}</div>
    <button type="button" onClick={() => onSelect({
      site_name: 'Mohakhali_Terminal_Site_1',
      zone_name: 'Badda_Mohakhali',
      candidate_id: 'CS-17',
    })}>Mock select candidate</button>
  </>,
}));

const payload = {
  run: { run_id: 'test-run', data_mode: 'demo' },
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
  delete document.documentElement.dataset.theme;
});

describe('dashboard UI', () => {
  it('keeps search and map layer controls available', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);
    await waitFor(() => expect(screen.getByText('Choose a solution')).toBeInTheDocument());
    expect(screen.getByRole('combobox', { name: 'Appearance' })).toHaveValue('auto');
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.change(screen.getByRole('combobox', { name: 'Appearance' }), { target: { value: 'dark' } });
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));
    fireEvent.change(screen.getByRole('combobox', { name: 'Appearance' }), { target: { value: 'light' } });
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'));
    expect(screen.getByRole('textbox', { name: 'Search candidate and zone' })).toBeInTheDocument();
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
    fireEvent.click(demandLayer);
    expect(demandLayer).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Live assets' }));
    expect(screen.getByRole('button', { name: 'Live assets' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('checkbox', { name: 'Candidate sites' })).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Planning' }));
    expect(screen.getByRole('checkbox', { name: 'Candidate sites' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM EV chargers' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'OSM fuel stations' })).not.toBeChecked();
    expect(screen.getByText('OPENFREEMAP')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mock select candidate' }));
    expect(screen.getByRole('heading', { name: 'Mohakhali Terminal Site 1' })).toBeInTheDocument();
    expect(screen.getByText('Badda Mohakhali')).toBeInTheDocument();
    expect(screen.getByText('CS-17')).toBeInTheDocument();
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
