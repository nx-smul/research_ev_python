import { useCallback, useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import mapLibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';

const EMPTY_COLLECTION = { type: 'FeatureCollection', features: [] };
const layerEventBindings = new WeakMap();
const OPENFREEMAP_STYLE_URLS = {
  light: 'https://tiles.openfreemap.org/styles/positron',
  dark: 'https://tiles.openfreemap.org/styles/dark',
};

function bindLayerEvents(instance, layerId, bind) {
  let boundLayers = layerEventBindings.get(instance);
  if (!boundLayers) {
    boundLayers = new Set();
    layerEventBindings.set(instance, boundLayers);
  }
  if (boundLayers.has(layerId)) return;
  bind();
  boundLayers.add(layerId);
}

function formatLocationName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\bsite\s+(\d+)\b/gi, 'Site $1')
    .replace(/\b(\d+)(st|nd|rd|th)\b/gi, '$1$2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function formatMetric(value, options = {}) {
  const number = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(number)) return null;
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: options.digits ?? 1,
  }).format(number);
  return `${formatted}${options.unit === '%' ? '%' : options.unit ? ` ${options.unit}` : ''}`;
}

function isFlagSet(value) {
  if (typeof value === 'string') return !['', '0', 'false', 'no'].includes(value.trim().toLowerCase());
  return Boolean(value);
}

function tooltipDetails(properties, kind) {
  const zone = formatLocationName(properties.zone_name || properties.anchor_zone);
  const location = properties.site_name || properties.anchor_zone || properties.zone_name || properties.name;
  let name;
  let type;

  if (kind === 'candidate') {
    name = formatLocationName(properties.site_name || properties.zone_name || properties.candidate_id || 'Candidate site');
    type = properties.is_selected ? 'Selected charging site' : 'Candidate charging site';
  } else if (kind === 'demand') {
    name = formatLocationName(properties.anchor_zone || properties.zone_name || 'Demand area');
    type = formatLocationName(properties.zone_type || 'Modeled demand zone');
  } else if (kind === 'substation') {
    name = formatLocationName(properties.name || properties.sub_id || 'Electrical substation');
    type = `${formatLocationName(properties.utility || 'Utility')} substation`;
  } else if (kind === 'facility') {
    const facilityTypes = Array.isArray(properties.facility_types)
      ? properties.facility_types
      : [properties.amenity === 'charging_station' ? 'ev_charger' : 'fuel_station'];
    type = facilityTypes.includes('ev_charger') && facilityTypes.includes('fuel_station')
      ? 'EV charger & fuel station'
      : facilityTypes.includes('ev_charger') ? 'EV charging station' : 'Fuel station';
    name = formatLocationName(properties.name || type);
  } else if (kind === 'landuse') {
    name = formatLocationName(properties.name || properties.zone_name || properties.zone_type || 'Land-use area');
    type = isFlagSet(properties.is_exclusion_zone) ? 'Restricted land-use area' : `${formatLocationName(properties.zone_type || 'Permitted')} land use`;
  } else {
    name = formatLocationName(properties.name || properties.corridor_name || 'Road corridor');
    type = formatLocationName(properties.highway || properties.road_type || 'Road');
  }

  let metrics = [];
  if (kind === 'candidate') {
    metrics = [
      ['AHP suitability', formatMetric(Number(properties.ahp_suitability_score) * 100, { unit: '%', digits: 1 })],
      ['TOPSIS score', formatMetric(Number(properties.topsis_score) * 100, { unit: '%', digits: 1 })],
      ['TOPSIS rank', formatMetric(properties.topsis_rank, { digits: 0 })],
      ['Substation distance', formatMetric(properties.distance_to_substation_m, { unit: 'm' })],
      ['Grid headroom', formatMetric(properties.substation_headroom_mva, { unit: 'MVA' })],
      ['Modeled land cost', formatMetric(properties.land_cost_bdt_sqm, { unit: 'BDT/m²', digits: 0 })],
    ];
  } else if (kind === 'demand') {
    metrics = [['Modeled demand', formatMetric(properties.daily_demand_kwh, { unit: 'kWh/day', digits: 0 })]];
  } else if (kind === 'substation') {
    metrics = [
      ['Spare capacity', formatMetric(properties.headroom_mva, { unit: 'MVA' })],
      ['Headroom share', formatMetric(properties.headroom_pct, { unit: '%' })],
      ['Rated capacity', formatMetric(properties.rated_mva, { unit: 'MVA' })],
      ['Base load', formatMetric(properties.base_load_mva, { unit: 'MVA' })],
    ];
  } else if (kind === 'facility') {
    metrics = [
      ['Power', properties['max_power'] || properties.max_power_kw
        ? `${properties['max_power'] || properties.max_power_kw}${String(properties['max_power'] || '').match(/[a-z]/i) ? '' : ' kW'}`
        : null],
      ['Connectors', properties.socket || properties.connectors || Object.keys(properties).some(key => key.startsWith('socket:'))
        ? [
          properties.socket || properties.connectors,
          ...Object.entries(properties)
            .filter(([key]) => key.startsWith('socket:'))
            .map(([key, value]) => `${key.slice('socket:'.length)}${Number(value) > 1 ? ` ×${value}` : ''}`),
        ].filter(Boolean).join(', ').split(/[;,]/).map(value => formatLocationName(value)).join(', ')
        : null],
    ];
  } else if (kind === 'landuse') {
    metrics = [
      ['Land price', formatMetric(properties.land_price_bdt_sqm, { unit: 'BDT/m²', digits: 0 })],
      ['Flood hazard', properties.is_flood_hazard === undefined ? null : (isFlagSet(properties.is_flood_hazard) ? 'Yes' : 'No')],
    ];
  } else {
    metrics = [
      ['Road length', formatMetric(Number(properties.length_m) / 1000, { unit: 'km' })],
      ['Speed limit', formatMetric(properties.maxspeed, { unit: 'km/h', digits: 0 })],
      ['Traffic flow', formatMetric(properties.pcu_per_hr, { unit: 'PCU/h', digits: 0 })],
      ['Congestion factor', formatMetric(properties.congestion_factor, { digits: 2 })],
    ];
  }

  return {
    name: name || 'Map location',
    type: type || 'Map feature',
    location: zone && zone !== name ? zone : '',
    reference: properties.candidate_id || properties.demand_id || properties.sub_id || '',
    metrics: metrics.filter(([, value]) => value !== null),
  };
}

function makeTooltipContent(properties, kind) {
  const details = tooltipDetails(properties, kind);
  const content = document.createElement('div');
  content.className = 'map-hover-content';
  const name = document.createElement('strong');
  name.className = 'map-hover-name';
  name.textContent = details.name;
  const type = document.createElement('span');
  type.className = 'map-hover-type';
  type.textContent = details.type;
  content.append(name, type);
  if (details.location) {
    const location = document.createElement('span');
    location.className = 'map-hover-location';
    location.textContent = details.location;
    content.append(location);
  }
  for (const [label, value] of details.metrics) {
    const metric = document.createElement('span');
    metric.className = 'map-hover-metric';
    metric.textContent = `${label}: ${value}`;
    content.append(metric);
  }
  if (details.reference) {
    const reference = document.createElement('small');
    reference.className = 'map-hover-reference';
    reference.textContent = `Reference: ${details.reference}`;
    content.append(reference);
  }
  return content;
}

function syncLayers(instance, state) {
  if (!instance.isStyleLoaded()) return;
  const { data, selectedIds, visibleLayers, basemap, onSelectRef, hasFittedData } = state.current;
  const candidateSource = instance.getSource('candidate-sites');
  const candidates = {
    type: 'FeatureCollection',
    features: (data?.candidates?.features || []).map(feature => ({
      ...feature,
      properties: {
        ...feature.properties,
        is_selected: selectedIds.has(feature.properties?.candidate_id),
      },
    })),
  };
  if (candidateSource) candidateSource.setData(candidates);
  else instance.addSource('candidate-sites', { type: 'geojson', data: candidates });
  if (candidates.features.length && !hasFittedData.current) {
    hasFittedData.current = true;
    state.current.fitDataBounds();
  }
  if (!instance.getLayer('candidate-sites')) {
    instance.addLayer({
      id: 'candidate-sites',
      type: 'circle',
      source: 'candidate-sites',
      paint: {
        'circle-radius': ['case', ['get', 'is_selected'], 10, 8],
        'circle-color': ['case', ['get', 'is_selected'], '#7455f7', '#2563eb'],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
      },
    });
    bindLayerEvents(instance, 'candidate-sites', () => {
      instance.on('click', 'candidate-sites', event => {
        const feature = event.features?.[0];
        if (feature?.properties) onSelectRef.current({ ...feature.properties, geometry: feature.geometry });
      });
      instance.on('mouseenter', 'candidate-sites', () => { instance.getCanvas().style.cursor = 'pointer'; });
      instance.on('mouseleave', 'candidate-sites', () => { instance.getCanvas().style.cursor = ''; });
      bindHoverTooltip(instance, 'candidate-sites', 'candidate');
    });
  }
  instance.setLayoutProperty('candidate-sites', 'visibility', visibleLayers.candidates ? 'visible' : 'none');

  const overlays = [
    ['demand', 'Demand points', 'circle', data?.demand, { 'circle-radius': 5, 'circle-color': '#0e7490', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1, 'circle-opacity': 0.9 }],
    ['roads', 'Road network', 'line', data?.roads, { 'line-color': '#d99a35', 'line-width': 1.5, 'line-opacity': 0.8 }],
    ['landuse', 'Land use', 'fill', data?.landuse, { 'fill-color': ['case', ['get', 'is_exclusion_zone'], '#e66b6b', '#59a98b'], 'fill-opacity': 0.25, 'fill-outline-color': '#428771' }],
    ['osm-facilities', 'Live OpenStreetMap facilities', 'circle', data?.live?.geojson, { 'circle-radius': 8, 'circle-color': '#087f62', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2, 'circle-opacity': 1 }],
  ];
  for (const [key, title, type, collection, paint] of overlays) {
    const sourceId = `overlay-${key}`;
    const layerId = `${sourceId}-layer`;
    const source = instance.getSource(sourceId);
    if (source) source.setData(collection || EMPTY_COLLECTION);
    else instance.addSource(sourceId, { type: 'geojson', data: collection || EMPTY_COLLECTION });
    if (!instance.getLayer(layerId)) {
      const layer = { id: layerId, type, source: sourceId, paint, metadata: { title } };
      if (key === 'osm-facilities') {
        layer.filter = ['==', ['get', 'is_ev_charger'], true];
      }
      instance.addLayer(layer);
      if (key === 'osm-facilities') {
        instance.addLayer({
          id: 'overlay-osm-fuel-layer',
          type: 'circle',
          source: sourceId,
          filter: ['==', ['get', 'is_fuel_station'], true],
          paint: { 'circle-radius': 8, 'circle-color': '#bd6900', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2, 'circle-opacity': 1 },
          metadata: { title: 'Live OpenStreetMap fuel stations' },
        });
      }
    }
    instance.setLayoutProperty(layerId, 'visibility', key === 'osm-facilities'
      ? (visibleLayers['osm-chargers'] ? 'visible' : 'none')
      : (visibleLayers[key] ? 'visible' : 'none'));
    if (key === 'osm-facilities') {
      instance.setLayoutProperty('overlay-osm-fuel-layer', 'visibility', visibleLayers['osm-fuel'] ? 'visible' : 'none');
    }
  }

  const showFacility = event => {
    const feature = event.features?.[0];
    if (!feature) return;
    const properties = feature.properties || {};
    const content = document.createElement('div');
    content.className = 'map-feature-content';
    const name = document.createElement('strong');
    name.className = 'map-feature-name';
    const facilityTypes = Array.isArray(properties.facility_types)
      ? properties.facility_types
      : [properties.amenity === 'charging_station' ? 'ev_charger' : 'fuel_station'];
    const isCharger = facilityTypes.includes('ev_charger');
    const isFuel = facilityTypes.includes('fuel_station');
    const typeLabel = isCharger && isFuel
      ? 'EV charger & fuel station'
      : isCharger ? 'EV charging station' : 'Fuel station';
    name.textContent = properties.name || typeLabel;
    const sourceLabel = document.createElement('div');
    sourceLabel.className = 'map-feature-source';
    sourceLabel.textContent = `OpenStreetMap · ${typeLabel}`;
    content.append(name, sourceLabel);
    if (properties.osm_url) {
      const link = document.createElement('a');
      link.href = properties.osm_url;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.className = 'map-feature-link';
      link.textContent = 'View OSM record';
      content.append(link);
    }
    new maplibregl.Popup({ closeButton: true, closeOnClick: true, className: 'map-feature-popup' })
      .setLngLat(event.lngLat)
      .setDOMContent(content)
      .addTo(instance);
  };
  for (const id of ['overlay-osm-facilities-layer', 'overlay-osm-fuel-layer']) {
    bindLayerEvents(instance, id, () => {
      instance.on('click', id, showFacility);
      instance.on('mouseenter', id, () => { instance.getCanvas().style.cursor = 'pointer'; });
      instance.on('mouseleave', id, () => { instance.getCanvas().style.cursor = ''; });
      bindHoverTooltip(instance, id, 'facility');
    });
  }
  for (const [layerId, kind] of [
    ['overlay-demand-layer', 'demand'],
    ['overlay-roads-layer', 'road'],
    ['overlay-landuse-layer', 'landuse'],
  ]) {
    bindHoverTooltip(instance, layerId, kind);
  }

  const substations = (data?.substations || [])
    .map(row => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [Number(row.lon), Number(row.lat)] },
      properties: row,
    }))
    .filter(feature => feature.geometry.coordinates.every(Number.isFinite));
  const substationSource = instance.getSource('overlay-substations');
  if (substationSource) substationSource.setData({ type: 'FeatureCollection', features: substations });
  else instance.addSource('overlay-substations', { type: 'geojson', data: { type: 'FeatureCollection', features: substations } });
  if (!instance.getLayer('overlay-substations-layer')) {
    instance.addLayer({
      id: 'overlay-substations-layer',
      type: 'circle',
      source: 'overlay-substations',
      paint: { 'circle-radius': 6, 'circle-color': '#7759bd', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 },
    });
  }
  bindHoverTooltip(instance, 'overlay-substations-layer', 'substation');
  instance.setLayoutProperty('overlay-substations-layer', 'visibility', visibleLayers.substations ? 'visible' : 'none');
  instance.moveLayer('candidate-sites');
}

function bindHoverTooltip(instance, layerId, kind) {
  bindLayerEvents(instance, `${layerId}-hover`, () => {
    let popup;
    instance.on('mouseenter', layerId, event => {
      const feature = event.features?.[0];
      if (!feature?.properties || !event.lngLat) return;
      instance.getCanvas().style.cursor = 'pointer';
      popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, className: 'map-hover-popup' })
        .setLngLat(event.lngLat)
        .setDOMContent(makeTooltipContent(feature.properties, kind))
        .addTo(instance);
    });
    instance.on('mousemove', layerId, event => {
      if (popup && event.lngLat) popup.setLngLat(event.lngLat);
    });
    instance.on('mouseleave', layerId, () => {
      instance.getCanvas().style.cursor = '';
      popup?.remove();
      popup = null;
    });
  });
}

export default function MapView({ data, selectedIds, visibleLayers, basemap = 'light', onSelect, status, setStatus, onReady }) {
  const node = useRef(null);
  const map = useRef(null);
  const activeStyle = useRef(null);
  const onSelectRef = useRef(onSelect);
  const hasFittedData = useRef(false);
  const fitDataBounds = useCallback(() => {
    fitFeatureBounds(state.current.data?.candidates?.features || [], map.current, 0, 12);
  }, []);
  const fitFacilityBounds = useCallback(() => {
    fitFeatureBounds(state.current.data?.live?.geojson?.features || [], map.current, 500, 13);
  }, []);
  const state = useRef({ data, selectedIds, visibleLayers, basemap, onSelectRef, hasFittedData, fitDataBounds });
  state.current = { data, selectedIds, visibleLayers, basemap, onSelectRef, hasFittedData, fitDataBounds };
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!node.current || map.current) return undefined;
    maplibregl.setWorkerUrl(mapLibreWorkerUrl);
    activeStyle.current = OPENFREEMAP_STYLE_URLS[basemap] || OPENFREEMAP_STYLE_URLS.light;
    const instance = new maplibregl.Map({
      container: node.current,
      center: [90.4, 23.785],
      zoom: 11.7,
      pitch: 0,
      style: activeStyle.current,
    });
    instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    instance.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }));
    instance.on('style.load', () => syncLayers(instance, state));
    instance.on('error', event => {
      if (!event?.error) return;
      const message = event.error.message || String(event.error);
      if (/abort|cancel/i.test(message)) return;
      const sourceId = event.sourceId;
      if (sourceId === 'openmaptiles' || sourceId === 'ne2_shaded' || /tiles\.openfreemap\.org/.test(message)) {
        setStatus(`OpenFreeMap basemap failed to load: ${message}. Check your network connection.`);
      } else if (sourceId) {
        setStatus(`Map data layer "${sourceId}" failed to load: ${message}.`);
      } else {
        setStatus(`The map failed to render: ${message}. Check the browser console for details.`);
      }
      console.warn('Map resource error', { sourceId, error: event.error });
    });
    map.current = instance;
    onReady?.({
      flyTo: options => instance.flyTo(options),
      fitDataBounds,
      fitFacilityBounds,
    });
    return () => { instance.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const styleUrl = OPENFREEMAP_STYLE_URLS[basemap] || OPENFREEMAP_STYLE_URLS.light;
    if (!map.current || activeStyle.current === styleUrl) return;
    activeStyle.current = styleUrl;
    map.current.setStyle(styleUrl);
  }, [basemap]);

  useEffect(() => {
    if (map.current) syncLayers(map.current, state);
  }, [data, selectedIds, visibleLayers, basemap]);

  return <div className="map-shell"><div ref={node} className="map-canvas" aria-label="Interactive map of EV charging candidates and live OpenStreetMap facilities" />
    {status && <div className="map-status" role="status">{status}</div>}
  </div>;
}

function fitFeatureBounds(features, map, duration, maxZoom) {
  if (!map || !features.length) return;
  const bounds = new maplibregl.LngLatBounds();
  for (const feature of features) {
    const coordinates = feature.geometry?.coordinates;
    if (feature.geometry?.type !== 'Point' || !Array.isArray(coordinates) || coordinates.length < 2) continue;
    const [longitude, latitude] = coordinates.map(Number);
    if (Number.isFinite(longitude) && Number.isFinite(latitude)) bounds.extend([longitude, latitude]);
  }
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 70, maxZoom, duration });
}
