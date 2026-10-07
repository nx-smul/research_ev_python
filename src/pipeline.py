"""End-to-end automated research workflow pipeline for Dhaka EVCS placement & grid simulation."""

import os
from pathlib import Path
import yaml
import numpy as np
import pandas as pd
import geopandas as gpd

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


def run_full_pipeline(config_path="configs/default_config.yaml", generations=100, population=60, base_dir=None):
    """Execute complete research pipeline end-to-end."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config_full_path = os.path.join(base_dir, config_path) if not os.path.isabs(config_path) else config_path
    with open(config_full_path, "r") as f:
        config = yaml.safe_load(f)

    print("=" * 78)
    print("  DHAKA EV CHARGING STATION (EVCS) SPATIAL & GRID OPTIMIZATION FRAMEWORK  ")
    print("=" * 78)

    # 1. Data Verification
    print("\n>>> STEP 1: Spatial & Power Grid Data Verification")
    generate_all_data(base_dir)

    # 2. GIS-MCDM AHP-TOPSIS Ranking
    print("\n>>> STEP 2: Spatial Multi-Criteria Decision Making (AHP-TOPSIS)")
    candidate_table_path = os.path.join(base_dir, "results", "tables", "candidate_sites.csv")
    candidate_gdf, weights, cr = run_ahp_spatial_pipeline(config_full_path, candidate_table_path)

    # 3. OSM Road Graph & OD Travel Time Matrix
    print("\n>>> STEP 3: Road Network Graph & Origin-Destination (OD) Matrix")
    demand_geojson_path = os.path.join(base_dir, "data", "processed", "demand_grid_100m.geojson")
    candidate_geojson_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
    roads_geojson_path = os.path.join(base_dir, "data", "raw", "osm_dhaka_roads.geojson")
    od_npz_path = os.path.join(base_dir, "data", "processed", "od_travel_time_matrix.npz")

    compute_od_matrices(demand_geojson_path, candidate_geojson_path, roads_geojson_path, od_npz_path)

    # 4. Multi-Objective Optimization (NSGA-II)
    print("\n>>> STEP 4: Multi-Objective Genetic Optimization (NSGA-II)")
    data = np.load(od_npz_path)
    dist_matrix = data["distances"]
    time_matrix = data["travel_times"]
    demand_values = data["demand_values"]

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
    build_responsive_map_html(Path(base_dir), responsive_html_path)

    print("\n" + "=" * 78)
    print("  RESEARCH PIPELINE COMPLETED SUCCESSFULLY!  ")
    print("=" * 78)

    return {
        "status": "Success",
        "cr": cr,
        "pareto_solutions_count": len(pareto_df),
        "knee_solution": knee_sol.to_dict(),
        "grid_feasible": ev_v_met["is_compliant"] and ev_t_met["is_thermal_compliant"]
    }
