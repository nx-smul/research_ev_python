import { useEffect } from 'react';

const ZONES = ['ALL', 'Gulshan / Banani / Baridhara', 'Motijheel Commercial Zone (CBD)', 'Mirpur (1, 10, 11, DOHS)', 'Uttara North Gateway', 'Mohakhali & Tejgaon Industrial', 'Dhanmondi & Mohammadpur', 'Old Dhaka (Lalbagh/Sutrapur/Sadarghat)', 'Purbachal 300ft Corridor'];
const DEFAULT_VISIBLE_LAYERS = { candidates: true, demand: true, roads: false, landuse: false, substations: false, 'osm-chargers': true, 'osm-fuel': true };

export function readInitialView() {
  const params = new URLSearchParams(window.location.search);
  const layersParam = params.get('layers');
  const layers = layersParam === null
    ? DEFAULT_VISIBLE_LAYERS
    : Object.fromEntries(Object.keys(DEFAULT_VISIBLE_LAYERS).map(key => [key, layersParam.split(',').includes(key)]));
  let viewport = null;
  const longitude = Number(params.get('lon'));
  const latitude = Number(params.get('lat'));
  const zoom = Number(params.get('zoom'));
  if (Number.isFinite(longitude) && Number.isFinite(latitude) && Number.isFinite(zoom)) {
    viewport = { center: [longitude, latitude], zoom };
  }
  return {
    zone: ZONES.includes(params.get('area')) ? params.get('area') : 'ALL',
    query: params.get('q') || '',
    minAhp: Math.max(0, Math.min(1, Number(params.get('min')) || 0)),
    maxAhp: Math.max(0, Math.min(1, Number(params.get('max')) || 1)),
    theme: ['auto', 'light', 'dark'].includes(params.get('theme')) ? params.get('theme') : null,
    visibleLayers: layers,
    comparisonIds: (params.get('compare') || '').split(',').filter(Boolean).slice(0, 3),
    solutionIndex: Math.max(0, Number.parseInt(params.get('solution') || '0', 10) || 0),
    selectedId: params.get('site') || '',
    viewport,
  };
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

export function useURLState(state, mapViewport, mapInstance) {
  useEffect(() => {
    const url = createViewUrl(state, mapViewport || mapInstance?.getViewState?.());
    window.history.replaceState({}, '', url);
  }, [mapInstance, mapViewport, state.zone, state.query, state.minAhp, state.maxAhp, state.visibleLayers, state.theme, state.comparisonIds, state.solutionIndex, state.selectedId]);
}

export { ZONES, DEFAULT_VISIBLE_LAYERS };
