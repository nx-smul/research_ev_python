"""End-to-end automated research workflow pipeline for Dhaka EVCS placement & grid simulation."""

import hashlib
import importlib.metadata
import json
import os
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import geopandas as gpd

from src.config import load_config
from src.data_generator import generate_all_data
from src.spatial.ahp_mcdm import run_ahp_spatial_pipeline
from src.spatial.osm_network import compute_od_matrices
from src.optimization.nsga2_solver import NSGA2Solver, export_pareto_solutions
from src.grid.power_flow import GridPowerFlowSimulator, plot_voltage_profile_comparison
from src.visualization.map_plots import (
    plot_ahp_suitability_map,
    plot_optimal_cs_locations,
    generate_interactive_folium_map
)
from src.visualization.generate_responsive_map import build_responsive_map_html
from src.visualization.pareto_front import plot_pareto_front_2d, find_knee_point_solution


class RealDataPreflightError(ValueError):
    """Raised when required, provenance-verified public inputs are unavailable."""


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


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_real_data_inputs(base_dir):
    """Validate required inputs and return content-addressed provenance records.

    Metadata and structural checks document claims and detect incompatibility; they do
    not authenticate the publisher or prove that observational claims are true.
    """
    root = Path(base_dir)
    missing = []
    records = []
    for label, (relative_path, expected) in REAL_DATA_REQUIRED_INPUTS.items():
        path = root / relative_path
        if not path.is_file():
            missing.append(f"- {label}: missing {relative_path} (expected {expected}).")
            continue
        # No checked-in input currently carries verifiable source metadata. Require a
        # sidecar before interpreting an artifact as observational data.
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
        required_metadata = {"source_url", "license", "retrieved_at", "coverage", "units", "transformation", "data_class"}
        absent_metadata = sorted(required_metadata - provenance.keys())
        if absent_metadata:
            missing.append(f"- {label}: provenance sidecar lacks {', '.join(absent_metadata)}.")
        elif provenance.get("data_class") not in {"observed", "official_source", "derived_from_observed"}:
            missing.append(f"- {label}: data_class must identify observed/official data, not an estimate or demo.")
        elif not all(isinstance(provenance[key], str) and provenance[key].strip() for key in required_metadata):
            missing.append(f"- {label}: provenance metadata values must all be non-empty strings.")
        else:
            try:
                date.fromisoformat(provenance["retrieved_at"][:10])
            except ValueError:
                missing.append(f"- {label}: retrieved_at must begin with an ISO date (YYYY-MM-DD).")
            parsed_url = urlparse(provenance["source_url"])
            if parsed_url.scheme not in {"https", "http"} or not parsed_url.netloc:
                missing.append(f"- {label}: source_url must be an absolute HTTP(S) URL.")
            # Structural checks catch corruption and incompatible files; they do not
            # independently authenticate the publisher or observational claims.
            try:
                if path.suffix.lower() == ".geojson":
                    layer = gpd.read_file(path)
                    schemas = {
                        "data/processed/demand_grid_100m.geojson": {"demand_id", "daily_demand_kwh"},
                        "data/processed/candidate_sites_filtered.geojson": {
                            "candidate_id", "traffic_density_score", "poi_score", "parking_score",
                            "substation_headroom_mva", "land_cost_bdt_sqm", "distance_to_substation_m",
                            "ahp_suitability_score",
                        },
                        "data/raw/rajuk_dap_landuse.geojson": {"zone_type", "is_exclusion_zone"},
                        "data/raw/osm_dhaka_roads.geojson": {"u", "v", "length_m", "maxspeed", "lanes", "pcu_per_hr"},
                    }
                    required_fields = schemas.get(relative_path, set())
                    absent = sorted(required_fields - set(layer.columns))
                    if layer.empty or layer.geometry.is_empty.any() or layer.geometry.isna().any():
                        missing.append(f"- {label}: dataset must contain non-empty geometries.")
                    if layer.crs is None or layer.crs.to_epsg() != 4326:
                        missing.append(f"- {label}: geometry must declare CRS EPSG:4326.")
                    if absent:
                        missing.append(f"- {label}: dataset lacks required fields {', '.join(absent)}.")
                    if not absent:
                        id_field = {
                            "data/processed/demand_grid_100m.geojson": "demand_id",
                            "data/processed/candidate_sites_filtered.geojson": "candidate_id",
                        }.get(relative_path)
                        if id_field and (layer[id_field].isna().any() or layer[id_field].astype(str).duplicated().any()):
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
                elif path.suffix.lower() == ".csv":
                    table = pd.read_csv(path)
                    required_fields = {"sub_id", "name", "utility", "lon", "lat", "rated_mva", "base_load_mva"}
                    absent = sorted(required_fields - set(table.columns))
                    if table.empty or absent:
                        missing.append(f"- {label}: CSV is empty or lacks fields {', '.join(absent)}.")
                    if not absent and not table.empty:
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
                elif relative_path.endswith("dpdc_33kv_subnetwork.json"):
                    network = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(network, dict) or not network:
                        missing.append(f"- {label}: grid-model JSON must contain a non-empty object.")
                    elif not {"bus", "line", "load", "ext_grid"}.issubset(network):
                        missing.append(f"- {label}: grid-model JSON lacks required bus, line, load, or ext_grid tables.")
                    else:
                        for name in ("bus", "line", "load", "ext_grid"):
                            if not isinstance(network[name], list):
                                missing.append(f"- {label}: grid-model '{name}' table must be a list.")
                        if not network.get("bus") or not network.get("ext_grid"):
                            missing.append(f"- {label}: grid model must define at least one bus and external grid.")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                missing.append(f"- {label}: input could not be validated: {exc}.")
            records.append({
                "label": label,
                "path": relative_path,
                "sha256": _sha256_file(path),
                "provenance_path": str(provenance_path.relative_to(root)),
                "provenance_sha256": _sha256_file(provenance_path),
                "provenance": provenance,
                "validation": "passed" if not any(item.startswith(f"- {label}:") for item in missing) else "failed",
            })
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


def _software_versions():
    versions = {}
    for package in ("numpy", "pandas", "geopandas", "pandapower", "networkx", "PyYAML"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def _git_revision(base_dir):
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=base_dir, check=True,
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _write_run_manifest(path, manifest):
    """Atomically persist JSON run metadata without exposing secrets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_full_pipeline(config_path="configs/default_config.yaml", generations=None, population=None, base_dir=None, settings_path=None, data_mode="real", output_deploy_copies=False, manifest_path=None):
    """Execute the pipeline using provenance-verified public inputs or explicit demo data."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config_full_path = os.path.join(base_dir, config_path) if not os.path.isabs(config_path) else config_path
    settings_full_path = None
    if settings_path:
        settings_full_path = os.path.join(base_dir, settings_path) if not os.path.isabs(settings_path) else settings_path
    config = load_config(config_full_path, settings_full_path)
    nsga_config = config["optimization"]["nsga2"]
    generations = generations if generations is not None else nsga_config["generations"]
    population = population if population is not None else nsga_config["population_size"]
    nsga_config["generations"] = generations
    nsga_config["population_size"] = population

    print("=" * 78)
    print("  DHAKA EV CHARGING STATION (EVCS) SPATIAL & GRID OPTIMIZATION FRAMEWORK  ")
    print("=" * 78)

    # 1. Preflight inputs before any pipeline outputs are written.
    print("\n>>> STEP 1: Spatial & Power Grid Data Verification")
    if data_mode == "demo":
        print("[Pipeline] DEMO MODE: generating synthetic benchmark inputs; results are not observations.")
        generate_all_data(base_dir)
        input_records = []
        for label, (relative_path, _) in REAL_DATA_REQUIRED_INPUTS.items():
            input_path = Path(base_dir) / relative_path
            if input_path.is_file():
                input_records.append({
                    "label": label,
                    "path": relative_path,
                    "sha256": _sha256_file(input_path),
                    "data_class": "synthetic_demo",
                    "validation": "demo-generated",
                })
    elif data_mode == "real":
        input_records = validate_real_data_inputs(base_dir)
        print("[Pipeline] Required public inputs passed structural/provenance checks; source claims are not independently authenticated.")
    else:
        raise ValueError("data_mode must be either 'real' or 'demo'.")

    run_id = uuid.uuid4().hex

    # 2. GIS-MCDM AHP-TOPSIS Ranking
    print("\n>>> STEP 2: Spatial Multi-Criteria Decision Making (AHP-TOPSIS)")
    candidate_table_path = os.path.join(base_dir, "results", "tables", "candidate_sites.csv")
    candidate_gdf, weights, cr = run_ahp_spatial_pipeline(
        config, candidate_table_path, base_dir=base_dir
    )

    # 3. OSM Road Graph & OD Travel Time Matrix
    print("\n>>> STEP 3: Road Network Graph & Origin-Destination (OD) Matrix")
    demand_geojson_path = os.path.join(base_dir, "data", "processed", "demand_grid_100m.geojson")
    candidate_geojson_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
    roads_geojson_path = os.path.join(base_dir, "data", "raw", "osm_dhaka_roads.geojson")
    od_npz_path = os.path.join(base_dir, "data", "processed", "od_travel_time_matrix.npz")

    compute_od_matrices(
        demand_geojson_path, candidate_geojson_path, roads_geojson_path, od_npz_path,
        allow_approximate_fallback=(data_mode == "demo"),
    )

    # 4. Multi-Objective Optimization (NSGA-II)
    print("\n>>> STEP 4: Multi-Objective Genetic Optimization (NSGA-II)")
    data = np.load(od_npz_path)
    dist_matrix = data["distances"]
    time_matrix = data["travel_times"]
    demand_values = data["demand_values"]

    demand_gdf = gpd.read_file(demand_geojson_path)
    candidate_ids = candidate_gdf["candidate_id"].astype(str).tolist()
    demand_ids = demand_gdf["demand_id"].astype(str).tolist()
    if "candidate_ids" in data and data["candidate_ids"].astype(str).tolist() != candidate_ids:
        raise ValueError("OD matrix candidate_ids do not match candidate-site input order.")
    if "demand_ids" in data and data["demand_ids"].astype(str).tolist() != demand_ids:
        raise ValueError("OD matrix demand_ids do not match demand input order.")
    if dist_matrix.shape != (len(demand_ids), len(candidate_ids)) or time_matrix.shape != dist_matrix.shape:
        raise ValueError("OD matrix dimensions do not match demand and candidate inputs.")
    if not np.isfinite(dist_matrix).all() or not np.isfinite(time_matrix).all() or (dist_matrix < 0).any() or (time_matrix < 0).any():
        raise ValueError("OD matrices must contain finite non-negative distance and travel-time values.")
    if len(demand_values) != len(demand_ids) or not np.isfinite(demand_values).all() or (demand_values <= 0).any():
        raise ValueError("OD demand values must be finite, positive, and aligned with demand input rows.")

    candidate_metadata = candidate_gdf.to_dict(orient="records")
    solver = NSGA2Solver(dist_matrix, time_matrix, demand_values, candidate_metadata, config)
    solver.pop_size = population
    solver.generations = generations

    pareto_front, _ = solver.solve(generations=generations)
    pareto_csv_path = os.path.join(base_dir, "results", "tables", "optimal_solutions_pareto.csv")
    pareto_df = export_pareto_solutions(pareto_front, candidate_metadata, config, pareto_csv_path)

    # 5. Grid AC Power Flow Simulation on Knee-Point Solution
    print("\n>>> STEP 5: Distribution Grid Power Flow Simulation (pandapower)")
    knee_idx, knee_sol = find_knee_point_solution(pareto_df)
    print(f"[Pipeline] Selected Knee-Point Compromise Solution: '{knee_sol['solution_id']}'")
    print(f"  - Total Social Cost: BDT {knee_sol['total_cost_million_bdt']:.2f} Million (~${knee_sol['total_cost_million_usd']:.2f}M USD)")
    print(f"  - Spatial Demand Coverage: {knee_sol['demand_coverage_pct']:.1f}%")
    print(f"  - Deployed Stations: {knee_sol['open_station_count']} sites")
    print(f"  - Aggregated Peak Grid Load: {knee_sol['total_grid_power_kw']:.1f} kW")

    dpdc_net_path = os.path.join(base_dir, "data", "grid_models", "dpdc_33kv_subnetwork.json")
    sim = GridPowerFlowSimulator(dpdc_net_path)
    base_bus, base_line, base_v_met, base_t_met = sim.run_baseline_power_flow()

    selected_ids = str(knee_sol["selected_station_ids"]).split(";")
    active_stations_df = candidate_gdf[candidate_gdf["candidate_id"].isin(selected_ids)].copy()
    active_stations_df["total_grid_power_kw"] = float(knee_sol["total_grid_power_kw"]) / max(1, len(selected_ids))

    sim.inject_ev_station_loads(active_stations_df)
    ev_bus, ev_line, ev_v_met, ev_t_met = sim.run_ev_power_flow()

    voltage_fig_path = os.path.join(base_dir, "results", "figures", "voltage_profile_comparison.png")
    plot_voltage_profile_comparison(base_bus, ev_bus, voltage_fig_path)

    # 6. Spatial & Pareto Visualizations
    print("\n>>> STEP 6: Visualization Generation (Static & Interactive Maps)")
    landuse_path = os.path.join(base_dir, "data", "raw", "rajuk_dap_landuse.geojson")
    landuse_gdf = gpd.read_file(landuse_path) if os.path.exists(landuse_path) else None

    substations_csv = os.path.join(base_dir, "data", "raw", "dpdc_desco_substations.csv")
    substations_df = pd.read_csv(substations_csv) if os.path.exists(substations_csv) else None

    ahp_map_path = os.path.join(base_dir, "results", "figures", "ahp_suitability_map.png")
    plot_ahp_suitability_map(candidate_gdf, landuse_gdf, ahp_map_path)

    loc_map_path = os.path.join(base_dir, "results", "figures", "optimal_cs_locations.png")
    plot_optimal_cs_locations(candidate_gdf, selected_ids, substations_df, loc_map_path)

    pareto_fig_path = os.path.join(base_dir, "results", "figures", "pareto_frontier_tradeoff.png")
    plot_pareto_front_2d(pareto_df, pareto_fig_path)

    folium_html_path = os.path.join(base_dir, "results", "figures", "dhaka_evcs_interactive_map.html")
    generate_interactive_folium_map(candidate_gdf, selected_ids, substations_df, folium_html_path)

    responsive_html_path = Path(base_dir) / "results" / "figures" / "dhaka_evcs_responsive_map.html"
    dashboard_config = {**config, "optimization": {**config["optimization"], "nsga2": dict(nsga_config)}}
    run_id = uuid.uuid4().hex
    build_responsive_map_html(
        Path(base_dir), responsive_html_path, config=dashboard_config,
        data_mode=data_mode, deploy_copies=output_deploy_copies,
        run_metadata={
            "run_id": run_id,
            "provenance_status": "Synthetic demonstration inputs" if data_mode == "demo" else "Source claims documented; not independently authenticated",
        },
    )

    print("\n" + "=" * 78)
    print("  RESEARCH PIPELINE COMPLETED SUCCESSFULLY!  ")
    print("=" * 78)

    input_records.extend([
        {"label": "scenario configuration", "path": str(config_full_path), "sha256": _sha256_file(config_full_path), "data_class": "configuration"},
    ])
    if settings_full_path:
        input_records.append({"label": "user settings", "path": str(settings_full_path), "sha256": _sha256_file(settings_full_path), "data_class": "configuration"})
    if os.path.isfile(od_npz_path):
        input_records.append({"label": "OD matrices", "path": os.path.relpath(od_npz_path, base_dir), "sha256": _sha256_file(od_npz_path), "data_class": "derived_intermediate"})

    output_paths = [
        candidate_table_path, pareto_csv_path, voltage_fig_path, ahp_map_path,
        loc_map_path, pareto_fig_path, folium_html_path, str(responsive_html_path),
    ]
    output_records = [
        {"path": os.path.relpath(path, base_dir), "sha256": _sha256_file(path)}
        for path in output_paths if os.path.isfile(path)
    ]
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "data_mode": data_mode,
        "data_class": "synthetic_demo" if data_mode == "demo" else "provenance-documented public inputs; source claims not independently authenticated",
        "configuration": config,
        "configuration_sources": {"scenario": str(config_full_path), "settings": str(settings_full_path) if settings_full_path else None},
        "inputs": input_records,
        "outputs": output_records,
        "code_revision": _git_revision(base_dir),
        "software_versions": _software_versions(),
    }
    resolved_manifest_path = Path(manifest_path) if manifest_path else Path(base_dir) / "results" / "run_manifest.json"
    if not resolved_manifest_path.is_absolute():
        resolved_manifest_path = Path(base_dir) / resolved_manifest_path
    _write_run_manifest(resolved_manifest_path, manifest)

    return {
        "status": "Success",
        "run_id": run_id,
        "manifest_path": str(resolved_manifest_path),
        "cr": cr,
        "pareto_solutions_count": len(pareto_df),
        "knee_solution": knee_sol.to_dict(),
        "grid_feasible": ev_v_met["is_compliant"] and ev_t_met["is_thermal_compliant"],
        "data_mode": data_mode,
        "service_radius_rmax_m": config["optimization"]["service_radius_rmax_m"],
    }
