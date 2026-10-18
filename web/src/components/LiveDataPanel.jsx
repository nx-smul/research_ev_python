import { useMemo } from 'react';

export default function LiveDataPanel({ liveData, liveLoading, liveError, onRefresh }) {
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

  return (
    <div className={`live-data-note ${liveError ? 'has-error' : ''}`} role={liveError ? 'alert' : 'status'}>
      <div className="live-data-heading"><span className="live-data-icon" aria-hidden="true">↗</span><div><strong>{liveLoading ? 'Loading live OSM assets…' : liveError ? 'Live map data unavailable' : liveData?.is_stale ? 'Showing cached OSM assets' : 'OpenStreetMap assets'}</strong><span>{liveError ? liveError : liveData?.is_stale ? `Refresh failed: ${liveData.refresh_error}` : liveData?.osm_data_timestamp ? `OSM edits through ${new Date(liveData.osm_data_timestamp).toLocaleString()}` : liveData?.retrieved_at ? `Fetched ${new Date(liveData.retrieved_at).toLocaleString()} · OSM edit time unavailable` : 'Public amenities · not modeled demand'}</span></div></div>
      {!liveError && <div className="live-asset-counts"><span><i className="legend-dot osm-charge" />{liveLoading ? '—' : `${liveCounts.chargers} ${liveCounts.chargers === 1 ? 'EV charger' : 'EV chargers'}`}</span><span><i className="legend-dot osm-fuel" />{liveLoading ? '—' : `${liveCounts.fuel} ${liveCounts.fuel === 1 ? 'fuel station' : 'fuel stations'}`}</span><button type="button" className="live-refresh" aria-label="Refresh live OSM data" title="Refresh live OSM data" onClick={onRefresh}>↻</button></div>}
      {liveError && <button className="text-button" onClick={onRefresh}>Retry live data</button>}
    </div>
  );
}
