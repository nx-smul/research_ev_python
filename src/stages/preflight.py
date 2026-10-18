"""Stage 1 — input verification and synthetic demo generation."""

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import geopandas as gpd

from src.config import load_config
from src.data_generator import generate_all_data
from src.core.exceptions import RealDataPreflightError


REAL_DATA_REQUIRED_INPUTS = {
    "OSM road network": (
        "data/raw/osm_dhaka_roads.geojson",
        "mapped road geometry and routing attributes",
    ),
    "authoritative candidate sites": (
        "data/processed/candidate_sites_filtered.geojson",
        "candidate_id, geometry, and documented suitability inputs",
    ),
    "zoning and land-use constraints": (
        "data/raw/rajuk_dap_landuse.geojson",
        "documented zone_type and exclusion constraints",
    ),
    "utility substation attributes": (
        "data/raw/dpdc_desco_substations.csv",
        "substation IDs, geospatial location, rated capacity, and baseline load",
    ),
    "measured spatial EV charging demand": (
        "data/processed/demand_grid_100m.geojson",
        "demand_id, geometry, and observed daily_demand_kwh",
    ),
    "authoritative distribution grid model": (
        "data/grid_models/dpdc_33kv_subnetwork.json",
        "utility-provided topology, ratings, and operating baseline",
    ),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_geojson_layer(layer, relative_path, label, missing):
    schemas = {
        "data/processed/demand_grid_100m.geojson": {"demand_id", "daily_demand_kwh"},
        "data/processed/candidate_sites_filtered.geojson": {
            "candidate_id", "traffic_density_score", "poi_score", "parking_score",
            "substation_headroom_mva", "land_cost_bdt_sqm", "distance_to_substation_m",
            "ahp_suitability_score",
        },
        "data/raw/rajuk_dap_landuse.geojson": {"zone_type", "is_exclusion_zone"},
        "data/raw/osm_dhaka_roads.geojson": {
            "u", "v", "length_m", "maxspeed", "lanes", "pcu_per_hr",
            "maxspeed_source", "lanes_source", "pcu_source",
        },
    }
    required_fields = schemas.get(relative_path, set())
    absent = sorted(required_fields - set(layer.columns))
    if layer.empty or layer.geometry.is_empty.any() or layer.geometry.isna().any():
        missing.append(f"- {label}: dataset must contain non-empty geometries.")
    if layer.crs is None or layer.crs.to_epsg() != 4326:
        missing.append(f"- {label}: geometry must declare CRS EPSG:4326.")
    elif not layer.empty:
        bounds = layer.total_bounds
        if (
            not np.isfinite(bounds).all()
            or bounds[0] < -180 or bounds[2] > 180
            or bounds[1] < -90 or bounds[3] > 90
        ):
            missing.append(f"- {label}: geometry coordinates fall outside longitude/latitude bounds.")
    if absent:
        missing.append(f"- {label}: dataset lacks required fields {', '.join(absent)}.")
    if not absent:
        id_field = {
            "data/processed/demand_grid_100m.geojson": "demand_id",
            "data/processed/candidate_sites_filtered.geojson": "candidate_id",
        }.get(relative_path)
        if id_field and (
            layer[id_field].isna().any()
            or layer[id_field].astype(str).str.strip().eq("").any()
            or layer[id_field].astype(str).duplicated().any()
        ):
            missing.append(f"- {label}: {id_field} values must be non-empty and unique.")
        numeric_fields = {
            "data/processed/demand_grid_100m.geojson": ("daily_demand_kwh",),
            "data/processed/candidate_sites_filtered.geojson": (
                "traffic_density_score", "poi_score", "parking_score", "substation_headroom_mva",
                "land_cost_bdt_sqm", "distance_to_substation_m", "ahp_suitability_score",
            ),
            "data/raw/osm_dhaka_roads.geojson": ("length_m", "maxspeed", "lanes", "pcu_per_hr"),
        }.get(relative_path, ())
        for field in numeric_fields:
            values = pd.to_numeric(layer[field], errors="coerce")
            if values.isna().any() or not np.isfinite(values).all():
                missing.append(f"- {label}: {field} must be finite for every feature.")
                continue
            if (values < 0).any() or (field in {"daily_demand_kwh", "length_m", "maxspeed", "lanes"} and (values == 0).any()):
                missing.append(f"- {label}: {field} must be positive or non-negative as appropriate.")
            if field in {"traffic_density_score", "poi_score", "parking_score", "ahp_suitability_score"} and ((values < 0) | (values > 1)).any():
                missing.append(f"- {label}: {field} must be within [0, 1].")
        if relative_path == "data/processed/candidate_sites_filtered.geojson":
            if layer.geometry.geom_type.ne("Point").any():
                missing.append(f"- {label}: candidate geometry must contain Point features.")
        elif relative_path == "data/processed/demand_grid_100m.geojson":
            if not layer.geometry.geom_type.isin(["Point", "Polygon", "MultiPolygon"]).all():
                missing.append(f"- {label}: demand geometry must be points or grid polygons.")
        elif relative_path == "data/raw/rajuk_dap_landuse.geojson":
            if layer["zone_type"].isna().any() or not layer["is_exclusion_zone"].isin([0, 1, True, False]).all():
                missing.append(f"- {label}: zone_type and binary is_exclusion_zone values are required.")
        elif relative_path == "data/raw/osm_dhaka_roads.geojson":
            if not layer.geometry.geom_type.isin(["LineString", "MultiLineString"]).all():
                missing.append(f"- {label}: road geometry must contain line features.")
            if layer["u"].isna().any() or layer["v"].isna().any():
                missing.append(f"- {label}: routing endpoint IDs u and v must be present.")
            elif (
                layer["u"].astype(str).str.strip().eq("").any()
                or layer["v"].astype(str).str.strip().eq("").any()
            ):
                missing.append(f"- {label}: routing endpoint IDs u and v must be non-empty.")
            for field in ("maxspeed_source", "lanes_source", "pcu_source"):
                if layer[field].isna().any() or layer[field].astype(str).str.strip().eq("").any():
                    missing.append(f"- {label}: {field} must classify every value as sourced, assumed, or otherwise documented.")


def _validate_csv_table(table, label, missing):
    required_fields = {"sub_id", "name", "utility", "lon", "lat", "rated_mva", "base_load_mva"}
    absent = sorted(required_fields - set(table.columns))
    if table.empty or absent:
        missing.append(f"- {label}: CSV is empty or lacks fields {', '.join(absent)}.")
        return
    if table["sub_id"].isna().any() or table["sub_id"].astype(str).duplicated().any():
        missing.append(f"- {label}: sub_id values must be non-empty and unique.")
    for field in ("lon", "lat", "rated_mva", "base_load_mva"):
        values = pd.to_numeric(table[field], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            missing.append(f"- {label}: {field} must be finite for every substation.")
            continue
        if field in {"rated_mva", "base_load_mva"} and (values < 0).any():
            missing.append(f"- {label}: {field} must be non-negative.")
        if field == "rated_mva" and (values <= 0).any():
            missing.append(f"- {label}: rated_mva must be positive.")
        if field == "lon" and ((values < -180) | (values > 180)).any():
            missing.append(f"- {label}: longitude must be within [-180, 180].")
        if field == "lat" and ((values < -90) | (values > 90)).any():
            missing.append(f"- {label}: latitude must be within [-90, 90].")
    rated = pd.to_numeric(table["rated_mva"], errors="coerce")
    load = pd.to_numeric(table["base_load_mva"], errors="coerce")
    if ((load - rated) > 1e-9).any():
        missing.append(f"- {label}: base_load_mva cannot exceed rated_mva.")


def _validate_grid_model(network, label, missing):
    if not isinstance(network, dict) or not network:
        missing.append(f"- {label}: grid-model JSON must contain a non-empty object.")
        return
    if not {"bus", "line", "load", "ext_grid"}.issubset(network):
        missing.append(f"- {label}: grid-model JSON lacks required bus, line, load, or ext_grid tables.")
        return
    for name in ("bus", "line", "load", "ext_grid"):
        if not isinstance(network[name], list):
            missing.append(f"- {label}: grid-model '{name}' table must be a list.")
    if not network.get("bus") or not network.get("ext_grid"):
        missing.append(f"- {label}: grid model must define at least one bus and external grid.")


def validate_real_data_inputs(base_dir):
    """Validate required inputs and return content-addressed provenance records."""
    root = Path(base_dir)
    missing = []
    records = []
    for label, (relative_path, expected) in REAL_DATA_REQUIRED_INPUTS.items():
        path = root / relative_path
        if not path.is_file():
            missing.append(f"- {label}: missing {relative_path} (expected {expected}).")
            continue
        provenance_path = path.with_suffix(path.suffix + ".provenance.json")
        if not provenance_path.is_file():
            missing.append(
                f"- {label}: {relative_path} has no provenance sidecar "
                f"({provenance_path.name}); source and observational status are unverified."
            )
            continue
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            missing.append(f"- {label}: invalid provenance sidecar {provenance_path.name}: {exc}.")
            continue
        if not isinstance(provenance, dict):
            missing.append(f"- {label}: provenance sidecar must contain a JSON object.")
            continue
        required_metadata = {"source_url", "license", "coverage", "units", "transformation", "data_class"}
        date_field = "generated_at" if provenance.get("data_class") == "synthetic_demo" else "retrieved_at"
        required_metadata.add(date_field)
        absent_metadata = sorted(required_metadata - provenance.keys())
        if absent_metadata:
            missing.append(f"- {label}: provenance sidecar lacks {', '.join(absent_metadata)}.")
        elif not all(isinstance(provenance[key], str) and provenance[key].strip() for key in required_metadata):
            missing.append(f"- {label}: provenance metadata values must all be non-empty strings.")
        else:
            if date_field == "retrieved_at":
                try:
                    date.fromisoformat(provenance["retrieved_at"][:10])
                except ValueError:
                    missing.append(f"- {label}: retrieved_at must begin with an ISO date (YYYY-MM-DD).")
            elif provenance["generated_at"] != "not recorded":
                try:
                    date.fromisoformat(provenance["generated_at"][:10])
                except ValueError:
                    missing.append(f"- {label}: generated_at must be an ISO date (YYYY-MM-DD) or 'not recorded'.")
            if provenance.get("data_class") not in {"observed", "official_source", "derived_from_observed"}:
                missing.append(
                    f"- {label}: data_class '{provenance.get('data_class')}' is not eligible for real-data analysis."
                )
            parsed_url = urlparse(provenance["source_url"])
            if parsed_url.scheme not in {"https", "http"} or not parsed_url.netloc:
                missing.append(f"- {label}: source_url must be an absolute HTTP(S) URL.")
            try:
                if path.suffix.lower() == ".geojson":
                    layer = gpd.read_file(path)
                    _validate_geojson_layer(layer, relative_path, label, missing)
                elif path.suffix.lower() == ".csv":
                    table = pd.read_csv(path)
                    _validate_csv_table(table, label, missing)
                elif relative_path.endswith("dpdc_33kv_subnetwork.json"):
                    network = json.loads(path.read_text(encoding="utf-8"))
                    _validate_grid_model(network, label, missing)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                missing.append(f"- {label}: input could not be validated: {exc}.")
            records.append({
                "label": label,
                "path": relative_path,
                "sha256": sha256_file(path),
                "provenance_path": str(provenance_path.relative_to(root)),
                "provenance_sha256": sha256_file(provenance_path),
                "provenance": provenance,
                "data_class": provenance.get("data_class"),
                "source_url": provenance.get("source_url"),
                "license": provenance.get("license"),
                "retrieved_at": provenance.get("retrieved_at"),
                "generated_at": provenance.get("generated_at"),
                "coverage": provenance.get("coverage"),
                "units": provenance.get("units"),
                "transformation": provenance.get("transformation"),
                "validation": "passed" if not any(item.startswith(f"- {label}:") for item in missing) else "failed",
            })
    road_path = root / "data/raw/osm_dhaka_roads.geojson"
    spatial_paths = {
        "candidate sites": root / "data/processed/candidate_sites_filtered.geojson",
        "demand zones": root / "data/processed/demand_grid_100m.geojson",
    }
    if road_path.is_file() and all(path.is_file() for path in spatial_paths.values()):
        try:
            roads = gpd.read_file(road_path)
            road_bounds = roads.to_crs(4326).total_bounds
            min_x, min_y, max_x, max_y = road_bounds
            for lbl, p in spatial_paths.items():
                layer = gpd.read_file(p).to_crs(4326)
                points = layer.geometry.representative_point()
                outside = (
                    (points.x < min_x) | (points.x > max_x)
                    | (points.y < min_y) | (points.y > max_y)
                )
                if outside.any():
                    missing.append(
                        f"- {lbl}: {int(outside.sum())} features fall outside the road-network "
                        "extent; confirm the study areas and coordinate reference systems align."
                    )
        except (OSError, ValueError, TypeError) as exc:
            missing.append(f"- Spatial coverage check could not be completed: {exc}.")
    if missing:
        details = "\n".join(missing)
        raise RealDataPreflightError(
            "Real-data analysis cannot proceed. The required public inputs below are "
            "missing or not provenance-verified; no synthetic replacements were generated.\n"
            f"{details}\nObtain source datasets and metadata (provider URL, license, "
            "retrieval date, coverage, units, and transformations), then retry. "
            "For a clearly labeled synthetic demonstration, use --data-mode demo."
        )
    return records


def generate_demo_inputs(base_dir):
    """Generate synthetic demo data and return provenance records."""
    generate_all_data(base_dir)
    records = []
    for label, (relative_path, _) in REAL_DATA_REQUIRED_INPUTS.items():
        input_path = Path(base_dir) / relative_path
        if input_path.is_file():
            records.append({
                "label": label,
                "path": relative_path,
                "sha256": sha256_file(input_path),
                "data_class": "synthetic_demo",
                "validation": "demo-generated",
            })
    return records

