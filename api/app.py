"""API for generated EVCS results and live OpenStreetMap facilities."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(os.environ.get("EVCS_DATA_ROOT", Path(__file__).resolve().parents[1])).resolve()
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("EVCS_CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if origin.strip()]
OVERPASS_URL = os.environ.get("EVCS_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
LIVE_MAP_CACHE_SECONDS = 900
LIVE_MAP_BBOX = (23.68, 90.32, 23.91, 90.48)
_live_map_cache = {"expires_at": 0.0, "payload": None}
_live_map_lock = asyncio.Lock()

app = FastAPI(title="Dhaka EVCS Atlas API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept"],
)


def _json_file(relative_path):
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid data path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Run artifact not found: {relative_path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Cannot read run artifact: {relative_path}") from exc


def _csv_records(relative_path):
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid data path")
    if not path.is_file():
        return []
    frame = pd.read_csv(path)
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def _research_data(manifest):
    """Load optional run-scoped analysis tables from manifest-contained paths."""
    analysis = manifest.get("analysis_outputs", {}) if isinstance(manifest, dict) else {}
    extensions = analysis.get("research_extensions", {})
    paths = extensions.get("outputs", {}) if isinstance(extensions, dict) else {}
    tables = (
        "uncertainty_site_screen",
        "uncertainty_scenario_metrics",
        "equity_accessibility",
        "time_of_day_load_profile",
        "queueing_screen",
        "grid_upgrade_screen",
        "field_validation_template",
        "investment_scenarios",
    )
    results = {
        key: _csv_records(paths[key]) if key in paths else []
        for key in tables
    }
    results["uncertainty_summary"] = extensions.get("uncertainty_summary", {}) if isinstance(extensions, dict) else {}
    return results


def _overpass_query():
    south, west, north, east = LIVE_MAP_BBOX
    bounds = f"{south},{west},{north},{east}"
    return (
        "[out:json][timeout:50];("
        f'nwr["amenity"~"^(charging_station|fuel)$"]({bounds});'
        f'nwr["fuel:charging_station"~"^(yes|public)$"]({bounds});'
        f'nwr["charging_station"~"^(yes|public)$"]({bounds});'
        ");out center tags;"
    )


def _facility_types(tags):
    amenity = tags.get("amenity")
    has_socket = any(key.startswith("socket:") for key in tags)
    charger_tag = tags.get("charging_station") in {"yes", "public"} or tags.get("fuel:charging_station") in {"yes", "public"}
    types = []
    if amenity == "charging_station" or charger_tag or has_socket:
        types.append("ev_charger")
    if amenity == "fuel":
        types.append("fuel_station")
    return types


async def _fetch_live_map():
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60),
            headers={"User-Agent": "DhakaEVCSAtlas/1.0 (+https://github.com/nx-smul/research_ev_python)"},
        ) as client:
            response = await client.post(OVERPASS_URL, data={"data": _overpass_query()})
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="OpenStreetMap Overpass request timed out; retry shortly.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenStreetMap Overpass returned HTTP {exc.response.status_code}; retry shortly.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="OpenStreetMap Overpass is unavailable; retry shortly.") from exc

    try:
        response_payload = response.json()
        if not isinstance(response_payload, dict):
            raise TypeError("Overpass response must be a JSON object.")
        elements = response_payload["elements"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="OpenStreetMap Overpass returned an invalid response.") from exc
    if not isinstance(elements, list):
        raise HTTPException(status_code=502, detail="OpenStreetMap Overpass returned an invalid element list.")
    osm3s = response_payload.get("osm3s")
    data_timestamp = osm3s.get("timestamp_osm_base") if isinstance(osm3s, dict) else None

    features = []
    seen = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        facility_types = _facility_types(tags)
        if not facility_types:
            continue
        if element.get("type") == "node":
            latitude, longitude = element.get("lat"), element.get("lon")
        else:
            center = element.get("center") or {}
            latitude, longitude = center.get("lat"), center.get("lon")
        try:
            longitude, latitude = float(longitude), float(latitude)
            osm_id = int(element["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            continue
        osm_type = element.get("type")
        if osm_type not in {"node", "way", "relation"}:
            continue
        feature_id = f"{osm_type}/{osm_id}"
        if feature_id in seen:
            continue
        seen.add(feature_id)
        features.append({
            "type": "Feature",
            "id": feature_id,
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {
                **{str(key): str(value) for key, value in tags.items()},
                "facility_types": facility_types,
                "is_ev_charger": "ev_charger" in facility_types,
                "is_fuel_station": "fuel_station" in facility_types,
                "osm_type": osm_type,
                "osm_id": osm_id,
                "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            },
        })

    return {
        "type": "FeatureCollection",
        "source": "OpenStreetMap",
        "source_url": "https://www.openstreetmap.org/copyright",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "osm_data_timestamp": data_timestamp,
        "features": features,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/run")
def run_metadata():
    path = ROOT / "results/run_manifest.json"
    return _json_file("results/run_manifest.json") if path.is_file() else {}


@app.get("/api/dashboard")
def dashboard():
    """Return the current run's read-only datasets and UI metadata."""
    manifest_path = ROOT / "results/run_manifest.json"
    manifest = _json_file("results/run_manifest.json") if manifest_path.is_file() else {}
    return {
        "run": manifest,
        "candidates": _json_file("data/processed/candidate_sites_filtered.geojson"),
        "demand": _json_file("data/processed/demand_grid_100m.geojson"),
        "roads": _json_file("data/raw/osm_dhaka_roads.geojson"),
        "landuse": _json_file("data/raw/rajuk_dap_landuse.geojson"),
        "substations": _csv_records("data/raw/dpdc_desco_substations.csv"),
        "pareto": _csv_records("results/tables/optimal_solutions_pareto.csv"),
        "ranked": _csv_records("results/tables/candidate_sites.csv"),
        "research": _research_data(manifest),
    }


@app.get("/api/live-map")
async def live_map(response: Response, refresh: bool = False):
    """Fetch recently replicated EV charging and fuel amenities from OpenStreetMap."""
    response.headers["Cache-Control"] = "no-store"
    now = time.monotonic()
    if not refresh and _live_map_cache["payload"] is not None and now < _live_map_cache["expires_at"]:
        return _live_map_cache["payload"]

    async with _live_map_lock:
        now = time.monotonic()
        if not refresh and _live_map_cache["payload"] is not None and now < _live_map_cache["expires_at"]:
            return _live_map_cache["payload"]
        try:
            payload = await _fetch_live_map()
        except HTTPException as exc:
            cached = _live_map_cache["payload"]
            if cached is None:
                raise
            payload = {**cached, "is_stale": True, "refresh_error": exc.detail}
            return payload
        payload["is_stale"] = False
        _live_map_cache.update(payload=payload, expires_at=time.monotonic() + LIVE_MAP_CACHE_SECONDS)
        return payload
