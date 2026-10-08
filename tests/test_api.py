from fastapi.testclient import TestClient
import json
import pandas as pd

from api import app as app_module


def test_health_endpoint():
    assert TestClient(app_module.app).get("/api/health").json() == {"status": "ok"}


def test_dashboard_endpoint_serves_run_artifacts():
    response = TestClient(app_module.app).get("/api/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"]["type"] == "FeatureCollection"
    assert payload["candidates"]["features"]
    assert payload["demand"]["features"]
    assert payload["candidates"]["features"][0]["geometry"]["type"] == "Point"
    assert payload["demand"]["features"][0]["geometry"]["type"] == "Point"
    assert isinstance(payload["pareto"], list)
    assert "run_id" in payload["run"]
    assert isinstance(payload["research"], dict)


def test_research_endpoint_data_is_loaded_from_manifest_outputs(tmp_path, monkeypatch):
    research_dir = tmp_path / "results" / "research" / "test-run"
    research_dir.mkdir(parents=True)
    table = research_dir / "equity_accessibility.csv"
    pd.DataFrame([{"group": "Central", "modeled_access_pct": 72.5}]).to_csv(table, index=False)
    manifest = {
        "analysis_outputs": {
            "research_extensions": {
                "outputs": {"equity_accessibility": str(table.relative_to(tmp_path))},
                "uncertainty_summary": {"samples": 250, "reachable_demand_pct_mean": 80.0},
            },
        },
    }

    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    payload = app_module._research_data(manifest)

    assert payload["equity_accessibility"] == [{"group": "Central", "modeled_access_pct": 72.5}]
    assert payload["uncertainty_summary"]["samples"] == 250
    assert payload["queueing_screen"] == []


def test_live_map_returns_and_caches_openstreetmap_facilities(monkeypatch):
    elements = [
        {
            "type": "node",
            "id": 101,
            "lat": 23.75,
            "lon": 90.39,
            "tags": {"amenity": "charging_station", "name": "Live Charger"},
        },
        {
            "type": "way",
            "id": 202,
            "center": {"lat": 23.76, "lon": 90.40},
            "tags": {"amenity": "fuel", "operator": "Example"},
        },
        {
            "type": "node",
            "id": 404,
            "lat": 23.77,
            "lon": 90.41,
            "tags": {"amenity": "fuel", "fuel:charging_station": "yes"},
        },
        {
            "type": "node",
            "id": 505,
            "lat": 23.78,
            "lon": 90.42,
            "tags": {"socket:type2": "2"},
        },
        {"type": "node", "id": 303, "tags": {"amenity": "parking"}},
    ]
    requests = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "osm3s": {"timestamp_osm_base": "2026-10-09T00:00:00Z"},
                "elements": elements,
            }

    class FakeClient:
        def __init__(self, **kwargs):
            requests.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            requests.append({"url": url, "data": data})
            return FakeResponse()

    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    app_module._live_map_cache.update(payload=None, expires_at=0)

    with TestClient(app_module.app) as client:
        first = client.get("/api/live-map")
        second = client.get("/api/live-map")
        refreshed = client.get("/api/live-map?refresh=true")

    assert first.status_code == 200
    payload = first.json()
    assert payload["source"] == "OpenStreetMap"
    assert payload["source_url"] == "https://www.openstreetmap.org/copyright"
    assert payload["osm_data_timestamp"] == "2026-10-09T00:00:00Z"
    assert len(payload["features"]) == 4
    assert payload["features"][0]["geometry"]["coordinates"] == [90.39, 23.75]
    assert payload["features"][0]["properties"]["osm_url"] == "https://www.openstreetmap.org/node/101"
    assert payload["features"][0]["properties"]["facility_types"] == ["ev_charger"]
    assert payload["features"][0]["properties"]["is_ev_charger"] is True
    assert payload["features"][0]["properties"]["is_fuel_station"] is False
    assert payload["features"][1]["geometry"]["coordinates"] == [90.4, 23.76]
    assert payload["features"][1]["properties"]["amenity"] == "fuel"
    assert payload["features"][1]["properties"]["facility_types"] == ["fuel_station"]
    assert payload["features"][1]["properties"]["is_ev_charger"] is False
    assert payload["features"][1]["properties"]["is_fuel_station"] is True
    assert payload["features"][2]["properties"]["facility_types"] == ["ev_charger", "fuel_station"]
    assert payload["features"][2]["properties"]["is_ev_charger"] is True
    assert payload["features"][2]["properties"]["is_fuel_station"] is True
    assert payload["features"][3]["properties"]["facility_types"] == ["ev_charger"]
    assert second.json() == payload
    assert first.headers["cache-control"] == "no-store"
    assert len([request for request in requests if "url" in request]) == 2
    assert refreshed.status_code == 200
    assert refreshed.json()["features"] == payload["features"]
    assert refreshed.json()["osm_data_timestamp"] == payload["osm_data_timestamp"]
    assert "charging_station|fuel" in requests[-1]["data"]["data"]
    assert "fuel:charging_station" in requests[-1]["data"]["data"]
    assert "timeout:50" in requests[-1]["data"]["data"]


def test_live_map_reports_upstream_failure(monkeypatch):
    async def unavailable():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="OpenStreetMap Overpass is unavailable; retry shortly.")

    monkeypatch.setattr(app_module, "_fetch_live_map", unavailable)
    app_module._live_map_cache.update(payload=None, expires_at=0)

    response = TestClient(app_module.app).get("/api/live-map")

    assert response.status_code == 503
    assert "OpenStreetMap Overpass is unavailable" in response.json()["detail"]


def test_live_map_keeps_last_successful_facilities_when_refresh_fails(monkeypatch):
    app_module._live_map_cache.update(
        payload={
            "type": "FeatureCollection",
            "source": "OpenStreetMap",
            "features": [{"type": "Feature", "properties": {"is_fuel_station": True}}],
        },
        expires_at=0,
    )

    async def unavailable():
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="OpenStreetMap Overpass returned HTTP 504; retry shortly.")

    monkeypatch.setattr(app_module, "_fetch_live_map", unavailable)
    response = TestClient(app_module.app).get("/api/live-map?refresh=true")

    assert response.status_code == 200
    assert response.json()["features"][0]["properties"]["is_fuel_station"] is True
    assert response.json()["is_stale"] is True
    assert "HTTP 504" in response.json()["refresh_error"]
