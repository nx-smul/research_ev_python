"""Thin orchestrator for the Dhaka EVCS placement pipeline.

All domain logic lives in src.stages.*; this module sequences them and assembles
the run manifest.
"""

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_config
from src.core.exceptions import RealDataPreflightError
from src.stages import (
    REAL_DATA_REQUIRED_INPUTS,
    generate_all_data,
    generate_demo_inputs,
    sha256_file,
    validate_real_data_inputs,
    run_spatial_ranking,
    compute_road_network,
    run_optimization,
    run_grid_analysis,
    generate_visualizations,
    generate_report,
    write_run_manifest,
)

# Backward compatibility: re-export for existing imports
_sha256_file = sha256_file
_write_run_manifest = write_run_manifest
__all__ = ["RealDataPreflightError", "run_full_pipeline", "validate_real_data_inputs", "generate_all_data", "_sha256_file", "_write_run_manifest"]


def _software_versions():
    import importlib.metadata
    versions = {}
    for package in ("numpy", "pandas", "geopandas", "pandapower", "networkx", "PyYAML"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def _git_revision(base_dir):
    import subprocess
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=base_dir, check=True,
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def run_full_pipeline(
    config_path="configs/default_config.yaml",
    generations=None,
    population=None,
    base_dir=None,
    settings_path=None,
    data_mode="real",
    manifest_path=None,
    sensitivity=False,
):
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

    # Stage 1: Preflight
    print("\n>>> STEP 1: Spatial & Power Grid Data Verification")
    if data_mode == "demo":
        print("[Pipeline] DEMO MODE: generating synthetic benchmark inputs; results are not observations.")
        generate_demo_inputs(base_dir)
        input_records = []
        for label, (relative_path, _) in REAL_DATA_REQUIRED_INPUTS.items():
            input_path = Path(base_dir) / relative_path
            if input_path.is_file():
                input_records.append({
                    "label": label,
                    "path": relative_path,
                    "sha256": sha256_file(input_path),
                    "data_class": "synthetic_demo",
                    "validation": "demo-generated",
                })
    elif data_mode == "real":
        input_records = validate_real_data_inputs(base_dir)
        print("[Pipeline] Required public inputs passed structural/provenance checks; source claims are not independently authenticated.")
    else:
        raise ValueError("data_mode must be either 'real' or 'demo'.")

    run_id = uuid.uuid4().hex

    # Stage 2: Spatial ranking
    print("\n>>> STEP 2: Spatial Multi-Criteria Decision Making (AHP-TOPSIS)")
    ranking = run_spatial_ranking(config, base_dir)
    candidate_gdf = ranking["candidate_gdf"]
    cr = ranking["cr"]
    candidate_table_path = ranking["candidate_table_path"]

    # Stage 3: Road network
    print("\n>>> STEP 3: Road Network Graph & Origin-Destination (OD) Matrix")
    network = compute_road_network(base_dir, candidate_gdf)
    dist_matrix = network["dist_matrix"]
    time_matrix = network["time_matrix"]
    demand_values = network["demand_values"]
    demand_gdf = network["demand_gdf"]
    candidate_ids = network["candidate_ids"]
    demand_ids = network["demand_ids"]
    candidate_metadata = network["candidate_metadata"]
    routing_method = network["routing_method"]
    road_network = network["road_network"]
    candidate_road_distances = network["candidate_road_distances"]
    od_npz_path = network["od_npz_path"]
    candidate_road_distances_path = network["candidate_road_distances_path"]

    # Stage 4: Optimization
    print("\n>>> STEP 4: Multi-Objective Genetic Optimization (NSGA-II)")
    opt = run_optimization(
        base_dir, config, dist_matrix, time_matrix, demand_values,
        demand_gdf, candidate_metadata, candidate_ids, demand_ids,
        run_id, population, generations, sensitivity, candidate_table_path,
    )
    pareto_df = opt["pareto_df"]
    pareto_csv_path = opt["pareto_csv_path"]
    knee_sol = opt["knee_sol"]
    optimizer_solution = opt["optimizer_solution"]
    baseline_df = opt["baseline_df"]
    baseline_path = opt["baseline_path"]
    research_extensions = opt["research_extensions"]
    sensitivity_path = opt["sensitivity_path"]
    sensitivity_dir = opt["sensitivity_dir"]

    # Stage 5: Grid analysis
    print("\n>>> STEP 5: Distribution Grid Power Flow Simulation (pandapower)")
    print(f"[Pipeline] Selected Knee-Point Compromise Solution: '{knee_sol['solution_id']}'")
    print(f"  - Total Social Cost: BDT {knee_sol['total_cost_million_bdt']:.2f} Million (~${knee_sol['total_cost_million_usd']:.2f}M USD)")
    print(f"  - Spatial Demand Coverage: {knee_sol['demand_coverage_pct']:.1f}%")
    print(f"  - Deployed Stations: {knee_sol['open_station_count']} sites")
    print(f"  - Aggregated Peak Grid Load: {knee_sol['total_grid_power_kw']:.1f} kW")
    grid = run_grid_analysis(base_dir, config, candidate_gdf, candidate_metadata, optimizer_solution, knee_sol)
    ev_v_met = grid["ev_v_met"]
    ev_t_met = grid["ev_t_met"]
    voltage_fig_path = grid["voltage_fig_path"]
    selected_ids = grid["selected_ids"]

    # Stage 6: Visualization
    print("\n>>> STEP 6: Visualization Generation (Static & Interactive Maps)")
    viz = generate_visualizations(base_dir, candidate_gdf, selected_ids, pareto_df)
    ahp_map_path = viz["ahp_map_path"]
    loc_map_path = viz["loc_map_path"]
    pareto_fig_path = viz["pareto_fig_path"]

    print("\n" + "=" * 78)
    print("  RESEARCH PIPELINE COMPLETED SUCCESSFULLY!  ")
    print("=" * 78)

    # Stage 7: Reporting
    input_records.extend([
        {"label": "scenario configuration", "path": str(config_full_path), "sha256": sha256_file(config_full_path), "data_class": "configuration"},
    ])
    if settings_full_path:
        input_records.append({"label": "user settings", "path": str(settings_full_path), "sha256": sha256_file(settings_full_path), "data_class": "configuration"})
    if os.path.isfile(od_npz_path):
        input_records.append({"label": "OD matrices", "path": os.path.relpath(od_npz_path, base_dir), "sha256": sha256_file(od_npz_path), "data_class": "derived_intermediate"})

    output_paths = [
        candidate_table_path, pareto_csv_path, candidate_road_distances_path,
        baseline_path, voltage_fig_path, ahp_map_path, loc_map_path, pareto_fig_path,
    ]
    output_paths.extend(research_extensions[key] for key in (
        "uncertainty_site_screen", "uncertainty_scenario_metrics", "equity_accessibility", "time_of_day_load_profile",
        "queueing_screen", "grid_upgrade_screen", "field_validation_template",
        "investment_scenarios", "assumptions", "carbon_analysis", "utilization_analysis",
        "portfolio_robustness", "site_stability_matrix", "unmet_demand_analysis",
        "travel_burden_analysis", "ahp_weight_sensitivity",
    ) if research_extensions.get(key))
    if sensitivity_path:
        output_paths.extend([
            sensitivity_path,
            os.path.join(sensitivity_dir, "sensitivity_knee_summary.csv"),
            os.path.join(sensitivity_dir, "optimizer_seed_site_stability.csv"),
            os.path.join(sensitivity_dir, "sensitivity_manifest.json"),
        ])

    road_route_status = candidate_road_distances["route_status"].value_counts().to_dict()
    report_outputs = [os.path.relpath(path, base_dir) for path in output_paths if path and os.path.isfile(path)]
    report_path = generate_report(base_dir, {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": data_mode,
        "data_class": "synthetic demonstration inputs" if data_mode == "demo" else "provenance-documented inputs; source claims not independently authenticated",
        "inputs": input_records,
        "solution": knee_sol.to_dict(),
        "baselines": baseline_df,
        "candidate_count": len(candidate_gdf),
        "demand_count": len(demand_gdf),
        "od_routing_method": routing_method,
        "road_edge_count": road_network.graph.number_of_edges(),
        "road_node_count": road_network.graph.number_of_nodes(),
        "road_attribute_sources": road_network.attribute_source_summary(),
        "route_count": road_route_status.get("routed", 0),
        "route_pair_count": len(candidate_road_distances),
        "same_node_count": road_route_status.get("same_road_node", 0),
        "unrouted_count": road_route_status.get("no_road_route", 0),
        "grid_voltage": ev_v_met,
        "grid_thermal": ev_t_met,
        "sensitivity_path": os.path.relpath(sensitivity_path, base_dir) if sensitivity_path else None,
        "research_extensions": {
            "outputs": {
                key: os.path.relpath(value, base_dir)
                for key, value in research_extensions.items()
                if value and key in {
                    "uncertainty_site_screen", "uncertainty_scenario_metrics", "equity_accessibility",
                    "time_of_day_load_profile", "queueing_screen", "grid_upgrade_screen",
                    "field_validation_template", "investment_scenarios", "assumptions",
                    "carbon_analysis", "utilization_analysis", "portfolio_robustness",
                    "site_stability_matrix", "unmet_demand_analysis", "travel_burden_analysis",
                    "ahp_weight_sensitivity",
                }
            },
            "most_frequently_selected_sites": research_extensions.get("most_frequently_selected_sites", []),
            "uncertainty_summary": research_extensions.get("uncertainty_summary", {}),
        },
        "outputs": report_outputs,
    })
    output_paths.append(report_path)

    run_dir = Path(base_dir) / "results" / "research" / run_id
    dashboard_artifacts = {}
    for name, source in {
        "candidates": "data/processed/candidate_sites_filtered.geojson",
        "demand": "data/processed/demand_grid_100m.geojson",
        "roads": "data/raw/osm_dhaka_roads.geojson",
        "landuse": "data/raw/rajuk_dap_landuse.geojson",
        "substations": "data/raw/dpdc_desco_substations.csv",
        "ranked": "results/tables/candidate_sites.csv",
        "pareto": "results/tables/optimal_solutions_pareto.csv",
    }.items():
        source_path = Path(base_dir) / source
        if source_path.is_file():
            destination = run_dir / "dashboard_data" / source_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            dashboard_artifacts[name] = os.path.relpath(destination, base_dir)

    output_records = [
        {"path": os.path.relpath(path, base_dir), "sha256": sha256_file(path)}
        for path in output_paths if path and os.path.isfile(path)
    ]

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "data_mode": data_mode,
        "od_routing_method": routing_method,
        "road_attribute_sources": road_network.attribute_source_summary(),
        "data_class": "synthetic_demo" if data_mode == "demo" else "provenance-documented public inputs; source claims not independently authenticated",
        "evidence_summary": {
            "status": "synthetic_demo" if data_mode == "demo" else "provenance_documented_unverified",
            "modeled_results_are_observations": False,
            "live_osm_used_in_optimization": False,
            "limitations": [
                "Siting metrics are conditional on the run inputs and model assumptions, not measured utilization or a demand forecast.",
                "Declared source provenance and structural checks do not independently authenticate source claims.",
                "Grid checks are simulation checks against configured limits, not validation against utility measurements.",
            ],
            "input_counts": {
                "total": len(input_records),
                "synthetic": sum(record.get("data_class") == "synthetic_demo" for record in input_records),
                "observed_or_derived": sum(record.get("data_class") in {"observed", "official_source", "derived_from_observed"} for record in input_records),
                "validation_passed": sum(record.get("validation") == "passed" for record in input_records),
            },
        },
        "configuration": config,
        "configuration_sources": {"scenario": str(config_full_path), "settings": str(settings_full_path) if settings_full_path else None},
        "inputs": input_records,
        "outputs": output_records,
        "dashboard_artifacts": dashboard_artifacts,
        "grid_validation": {
            "model_vs_configured_limits_only": True,
            "voltage": ev_v_met,
            "thermal": ev_t_met,
            "validated_against_utility_measurements": False,
        },
        "analysis_outputs": {
            "baseline_comparison": os.path.relpath(baseline_path, base_dir),
            "candidate_road_distances": os.path.relpath(candidate_road_distances_path, base_dir),
            "sensitivity_results": os.path.relpath(sensitivity_path, base_dir) if sensitivity_path else None,
            "sensitivity_knee_summary": os.path.relpath(
                os.path.join(sensitivity_dir, "sensitivity_knee_summary.csv"), base_dir
            ) if sensitivity_path else None,
            "optimizer_seed_site_stability": os.path.relpath(
                os.path.join(sensitivity_dir, "optimizer_seed_site_stability.csv"), base_dir
            ) if sensitivity_path else None,
            "research_report": os.path.relpath(report_path, base_dir),
            "research_extensions": {
                "outputs": {
                    key: os.path.relpath(value, base_dir)
                    for key, value in research_extensions.items()
                    if key in {
                        "uncertainty_site_screen", "uncertainty_scenario_metrics", "equity_accessibility",
                        "time_of_day_load_profile", "queueing_screen", "grid_upgrade_screen",
                        "field_validation_template", "investment_scenarios", "assumptions",
                    }
                },
                "uncertainty_summary": research_extensions["uncertainty_summary"],
            },
        },
        "code_revision": _git_revision(base_dir),
        "software_versions": _software_versions(),
    }

    resolved_manifest_path = Path(manifest_path) if manifest_path else Path(base_dir) / "results" / "run_manifest.json"
    if not resolved_manifest_path.is_absolute():
        resolved_manifest_path = Path(base_dir) / resolved_manifest_path
    write_run_manifest(resolved_manifest_path, manifest)
    write_run_manifest(Path(base_dir) / "results" / "research" / run_id / "manifest.json", manifest)

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
        "candidate_road_distances_path": candidate_road_distances_path,
        "baseline_comparison_path": baseline_path,
        "sensitivity_results_path": sensitivity_path,
        "research_extensions": research_extensions,
        "research_report_path": report_path,
    }

