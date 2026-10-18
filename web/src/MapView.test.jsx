import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const mapMocks = vi.hoisted(() => ({ instance: null, options: null, controls: [], popups: [], setWorkerUrl: vi.fn() }));

vi.mock('maplibre-gl', () => {
  class MockMap {
    constructor(options) {
      mapMocks.options = options;
      this.sources = new Map();
      this.layers = new Map();
      for (const layer of options.style.layers || []) {
        this.layers.set(layer.id, { ...layer, layout: { ...layer.layout } });
      }
      this.listeners = new Map();
      this.canvas = { style: {}, width: 800, height: 600, toDataURL: vi.fn(() => 'data:image/png;base64,dGVzdA==') };
      this.center = options.center;
      this.zoom = options.zoom;
      mapMocks.instance = this;
    }

    addControl(control, position = 'bottom-right') { mapMocks.controls.push({ control, position }); }
    isStyleLoaded() { return true; }
    getSource(id) { return this.sources.get(id); }
    getLayer(id) { return this.layers.get(id); }
    addSource(id, source) { this.sources.set(id, { ...source, setData(data) { this.data = data; } }); }
    addLayer(layer) { this.layers.set(layer.id, { ...layer, layout: {} }); }
    moveLayer(id) {
      this.movedLayer = id;
      this.layerOrder = [...this.layers.keys()].filter(layerId => layerId !== id);
      this.layerOrder.push(id);
    }
    setLayoutProperty(id, key, value) { this.layers.get(id).layout[key] = value; }
    setStyle(style) {
      this.style = style;
      this.setStyleCalls = [...(this.setStyleCalls || []), style];
      this.sources.clear();
      this.layers.clear();
      for (const callback of this.listeners.get('style.load') || []) callback();
    }
    getCanvas() { return this.canvas; }
    getCenter() { return { toArray: () => this.center }; }
    getZoom() { return this.zoom; }
    jumpTo({ center, zoom }) { this.center = center; this.zoom = zoom; }
    flyTo() {}
    fitBounds(bounds, options) { this.fit = { bounds, options }; }
    remove() {}

    on(event, ...args) {
      const layerEvent = args.length === 2 ? `${event}:${args[0]}` : event;
      const callback = args.at(-1);
      this.listeners.set(layerEvent, [...(this.listeners.get(layerEvent) || []), callback]);
    }

    off() {}

  }

  class MockBounds {
    constructor() { this.coordinates = []; }
    extend(coordinates) { this.coordinates.push(coordinates); }
    isEmpty() { return this.coordinates.length === 0; }
  }

  class MockPopup {
    constructor(options) {
      this.options = options;
      mapMocks.popups.push(this);
    }

    setLngLat(coordinates) { this.coordinates = coordinates; return this; }
    setDOMContent(content) { this.content = content; return this; }
    addTo(map) { this.map = map; return this; }
    remove() { this.removed = true; }
  }

  return {
    Map: MockMap,
    setWorkerUrl: mapMocks.setWorkerUrl,
    NavigationControl: class {},
    ScaleControl: class {},
    Popup: MockPopup,
    LngLatBounds: MockBounds,
  };
});

import MapView from './MapView.jsx';
import { MAP_COLORS, SUBSTATION_HEADROOM_COLOR_EXPRESSION } from './mapStyles.js';

afterEach(() => {
  cleanup();
  mapMocks.instance = null;
  mapMocks.options = null;
  mapMocks.controls = [];
  mapMocks.popups = [];
  mapMocks.setWorkerUrl.mockClear();
});

describe('MapView', () => {
  it('uses distinct colors for every map feature category', () => {
    expect(new Set(Object.values(MAP_COLORS)).size).toBe(Object.values(MAP_COLORS).length);
  });

  it('configures MapLibre to use the bundled worker asset', () => {
    render(<MapView
      data={{ candidates: { features: [] } }}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true }}
      onSelect={vi.fn()}
      setStatus={vi.fn()}
    />);

    expect(mapMocks.setWorkerUrl).toHaveBeenCalledWith(expect.stringMatching(/maplibre-gl-worker/));
    expect(mapMocks.options.attributionControl).toBe(false);
    expect(mapMocks.controls.map(control => control.position)).toEqual(['top-right', 'bottom-left']);
  });

  it('renders the candidate overlay and fits the view to available sites', () => {
    const data = {
      candidates: {
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.41, 23.81] },
          properties: { candidate_id: 'candidate-1' },
        }],
      },
      demand: {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.42, 23.82] },
          properties: { demand_id: 'demand-1' },
        }],
      },
      live: { geojson: { type: 'FeatureCollection', features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.4, 23.78] },
          properties: { amenity: 'charging_station', is_ev_charger: true, is_fuel_station: false },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.41, 23.77] },
          properties: { amenity: 'fuel', is_ev_charger: false, is_fuel_station: true },
        },
      ] } },
    };
    const props = {
      data,
      selectedIds: new Set(),
      visibleLayers: {
        candidates: true,
        demand: true,
        roads: false,
        landuse: false,
        substations: false,
        'osm-chargers': true,
        'osm-fuel': true,
      },
      onSelect: vi.fn(),
      setStatus: vi.fn(),
      onReady: vi.fn(),
    };
    const view = render(<MapView {...props} />);
    const map = mapMocks.instance;
    expect(map.getLayer('candidate-sites')).toBeTruthy();
    expect(map.getLayer('candidate-sites').paint['circle-color']).toEqual([
      'case', ['get', 'is_selected'], MAP_COLORS.selected, MAP_COLORS.candidate,
    ]);
    expect(map.getLayer('overlay-osm-facilities-layer')).toBeTruthy();
    expect(map.getLayer('overlay-osm-fuel-layer')).toBeTruthy();
    expect(map.getLayer('overlay-osm-facilities-layer').filter).toEqual([
      '==', ['get', 'is_ev_charger'], true,
    ]);
    expect(map.getLayer('overlay-osm-fuel-layer').filter).toEqual([
      '==', ['get', 'is_fuel_station'], true,
    ]);
    expect(map.getLayer('overlay-substations-layer').paint['circle-color']).toEqual(SUBSTATION_HEADROOM_COLOR_EXPRESSION);
    expect(map.getLayer('overlay-osm-facilities-layer').layout.visibility).toBe('visible');
    expect(map.getLayer('overlay-osm-fuel-layer').layout.visibility).toBe('visible');
    expect(map.getSource('overlay-osm-facilities').data.features).toHaveLength(2);
    expect(map.getSource('overlay-osm-facilities').data.features.map(feature => [
      feature.properties.is_ev_charger, feature.properties.is_fuel_station,
    ])).toEqual([[true, false], [false, true]]);
    expect(map.getSource('candidate-sites').data.features[0].properties.candidate_id).toBe('candidate-1');
    expect(map.getLayer('overlay-demand-layer').layout.visibility).toBe('visible');
    expect(map.getSource('overlay-demand').data).toBe(data.demand);
    expect(map.movedLayer).toBe('candidate-sites');
    expect(map.listeners.get('click:candidate-sites')).toHaveLength(1);
    expect(map.fit.options).toMatchObject({ maxZoom: 12, duration: 0 });
    expect(map.fit.bounds.coordinates).toEqual([[90.41, 23.81]]);
    const ready = props.onReady.mock.calls[0][0];
    ready.fitFacilityBounds();
    expect(map.fit.bounds.coordinates).toEqual([[90.4, 23.78], [90.41, 23.77]]);
    expect(map.fit.options.duration).toBe(500);
    expect(view.container).toBeInTheDocument();
  });

  it('shows readable feature names and types for every map data layer on hover', () => {
    const data = {
      candidates: {
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.41, 23.81] },
          properties: {
            candidate_id: 'CS-01',
            site_name: 'Airport_Hub_Site_1',
            zone_name: 'Uttara',
            ahp_suitability_score: 0.647,
            topsis_score: 0.8338,
            topsis_rank: 1,
            distance_to_substation_m: 9412.9,
            substation_headroom_mva: 11,
            land_cost_bdt_sqm: 110000,
          },
        }],
      },
      demand: {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [90.42, 23.82] },
          properties: {
            demand_id: 'DEMAND-001',
            anchor_zone: 'Airport_Hub',
            zone_type: 'Transport_Hub',
            zone_name: 'Uttara',
            daily_demand_kwh: 3742,
          },
        }],
      },
    };
    render(<MapView
      data={data}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true, demand: true }}
      onSelect={vi.fn()}
      setStatus={vi.fn()}
    />);
    const map = mapMocks.instance;
    const coordinates = { lng: 90.41, lat: 23.81 };
    const candidateHover = map.listeners.get('mouseenter:candidate-sites')
      .find(callback => callback.length > 0);
    candidateHover({ lngLat: coordinates, features: [{ properties: data.candidates.features[0].properties }] });

    expect(mapMocks.popups.at(-1).content.textContent).toContain('Airport Hub Site 1');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Candidate charging site');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Uttara');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Reference: CS-01');
    expect(mapMocks.popups.at(-1).content.textContent).not.toContain('Airport_Hub');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('AHP suitability: 64.7%');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('TOPSIS score: 83.4%');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('TOPSIS rank: 1');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Grid headroom: 11 MVA');

    const selectedHover = map.listeners.get('mouseenter:candidate-sites')
      .find(callback => callback.length > 0);
    selectedHover({
      lngLat: coordinates,
      features: [{
        properties: { ...data.candidates.features[0].properties, is_selected: true },
      }],
    });
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Selected charging site');

    selectedHover({
      lngLat: coordinates,
      features: [{
        properties: { ...data.candidates.features[0].properties, is_selected: false },
      }],
    });
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Candidate charging site');

    const demandHover = map.listeners.get('mouseenter:overlay-demand-layer')[0];
    demandHover({ lngLat: coordinates, features: [{ properties: data.demand.features[0].properties }] });
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Airport Hub');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Transport Hub');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Modeled demand: 3,742 kWh/day');

    const hoverCases = [
      {
        layer: 'overlay-osm-facilities-layer',
        properties: { name: 'Charge_Point_1', amenity: 'charging_station', facility_types: ['ev_charger'], max_power: '50', socket: 'CCS;Type 2' },
        expected: ['Charge Point 1', 'EV charging station', 'Power: 50 kW', 'Connectors: CCS, Type 2'],
      },
      {
        layer: 'overlay-osm-fuel-layer',
        properties: { name: 'Fuel_And_Charge', amenity: 'fuel', facility_types: ['ev_charger', 'fuel_station'] },
        expected: ['Fuel And Charge', 'EV charger & fuel station'],
      },
      {
        layer: 'overlay-substations-layer',
        properties: { name: 'Uttara_SS_01', sub_id: 'DPDC-SS-03', utility: 'DPDC', headroom_mva: 11, headroom_pct: 22, rated_mva: 50, base_load_mva: 39 },
        expected: ['Uttara SS 01', 'DPDC substation', 'Spare capacity: 11 MVA', 'Rated capacity: 50 MVA'],
      },
      {
        layer: 'overlay-roads-layer',
        properties: { corridor_name: 'Airport_Road', highway: 'primary', length_m: 2793.7, maxspeed: 60, pcu_per_hr: 3800, congestion_factor: 1.12 },
        expected: ['Airport Road', 'Primary', 'Road length: 2.8 km', 'Traffic flow: 3,800 PCU/h'],
      },
      {
        layer: 'overlay-landuse-layer',
        properties: { zone_name: 'Old_Dhaka', zone_type: 'Heritage', is_exclusion_zone: true, land_price_bdt_sqm: 250000, is_flood_hazard: 1 },
        expected: ['Old Dhaka', 'Restricted land-use area', 'Land price: 250,000 BDT/m²', 'Flood hazard: Yes'],
      },
    ];
    for (const { layer, properties, expected } of hoverCases) {
      const hover = map.listeners.get(`mouseenter:${layer}`)
        .find(callback => callback.length > 0);
      hover({ lngLat: coordinates, features: [{ properties }] });
      const tooltip = mapMocks.popups.at(-1).content.textContent;
      for (const label of expected) expect(tooltip).toContain(label);
    }
  });

  it('uses the themed popup for clicked OpenStreetMap facilities', () => {
    const data = {
      candidates: { features: [] },
      live: {
        geojson: {
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [90.4, 23.8] },
            properties: { name: 'Dhaka Charge Point', amenity: 'charging_station', osm_url: 'https://www.openstreetmap.org/node/1' },
          }],
        },
      },
    };
    render(<MapView
      data={data}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true, 'osm-chargers': true, 'osm-fuel': true }}
      onSelect={vi.fn()}
      setStatus={vi.fn()}
    />);
    mapMocks.instance.listeners.get('click:overlay-osm-facilities-layer')[0]({
      lngLat: { lng: 90.4, lat: 23.8 },
      features: [{ properties: data.live.geojson.features[0].properties }],
    });

    expect(mapMocks.popups.at(-1).options.className).toBe('map-feature-popup');
    expect(mapMocks.popups.at(-1).content.className).toBe('map-feature-content');
    expect(mapMocks.popups.at(-1).content.textContent).toContain('Dhaka Charge Point');
  });

  it('starts with the no-key OpenFreeMap Positron style', () => {
    render(<MapView
      data={{ candidates: { features: [] } }}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true }}
      onSelect={vi.fn()}
      setStatus={vi.fn()}
    />);

    expect(mapMocks.options.style).toBe('https://tiles.openfreemap.org/styles/positron');
  });

  it('exposes shareable viewport state and exports the rendered map canvas', () => {
    const onReady = vi.fn();
    const onViewportChange = vi.fn();
    render(<MapView
      data={{ candidates: { features: [] } }}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true }}
      initialViewport={{ center: [90.5, 23.9], zoom: 12 }}
      onSelect={vi.fn()}
      onViewportChange={onViewportChange}
      onReady={onReady}
      setStatus={vi.fn()}
    />);

    const mapApi = onReady.mock.calls[0][0];
    expect(mapMocks.options.center).toEqual([90.5, 23.9]);
    expect(mapMocks.options.zoom).toBe(12);
    expect(mapMocks.options.preserveDrawingBuffer).toBe(true);
    expect(mapApi.getViewState()).toEqual({ center: [90.5, 23.9], zoom: 12 });
    expect(mapApi.exportImage()).toMatch(/^data:image\/png/);
    mapMocks.instance.center = [90.6, 24];
    mapMocks.instance.listeners.get('moveend')[0]();
    expect(onViewportChange).toHaveBeenCalledWith({ center: [90.6, 24], zoom: 12 });
  });

  it('switches to the no-key OpenFreeMap dark style with the app appearance', () => {
    const onSelect = vi.fn();
    const props = {
      data: { candidates: { features: [{
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [90.4, 23.8] },
        properties: { candidate_id: 'CS-17', site_name: 'Test charging site' },
      }] } },
      selectedIds: new Set(),
      visibleLayers: { candidates: true },
      onSelect,
      setStatus: vi.fn(),
    };
    const view = render(<MapView {...props} />);
    view.rerender(<MapView {...props} basemap="dark" />);

    expect(mapMocks.instance.setStyleCalls).toEqual(['https://tiles.openfreemap.org/styles/dark']);
    expect(mapMocks.instance.getLayer('candidate-sites')).toBeTruthy();
    expect(mapMocks.instance.getLayer('overlay-demand-layer')).toBeTruthy();
    expect(mapMocks.instance.listeners.get('click:candidate-sites')).toHaveLength(1);
    expect(mapMocks.instance.getSource('candidate-sites').data.features[0].properties.candidate_id).toBe('CS-17');
    mapMocks.instance.listeners.get('click:candidate-sites')[0]({
      features: [{ properties: { candidate_id: 'CS-17' }, geometry: props.data.candidates.features[0].geometry }],
    });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ candidate_id: 'CS-17' }));
  });

  it('reports tile and data-layer failures with useful, distinct diagnostics', () => {
    const setStatus = vi.fn();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    render(<MapView
      data={{ candidates: { features: [] } }}
      selectedIds={new Set()}
      visibleLayers={{ candidates: true }}
      onSelect={vi.fn()}
      setStatus={setStatus}
    />);
    const onError = mapMocks.instance.listeners.get('error')[0];

    onError({ sourceId: 'openmaptiles', error: new Error('Failed to fetch tile') });
    expect(setStatus).toHaveBeenLastCalledWith(expect.stringContaining('OpenFreeMap'));
    expect(setStatus).toHaveBeenLastCalledWith(expect.stringContaining('Failed to fetch tile'));

    onError({ sourceId: 'overlay-demand', error: new Error('Invalid GeoJSON') });
    expect(setStatus).toHaveBeenLastCalledWith(expect.stringContaining('Map data layer "overlay-demand"'));
    expect(setStatus).toHaveBeenLastCalledWith(expect.stringContaining('Invalid GeoJSON'));

    const statusCount = setStatus.mock.calls.length;
    onError({ sourceId: 'ne2_shaded', error: new Error('Request aborted') });
    expect(setStatus).toHaveBeenCalledTimes(statusCount);
    warn.mockRestore();
  });
});
