"""Stage 6 — Static map and Pareto-front visualizations."""

import os

import pandas as pd
import geopandas as gpd

from src.visualization.map_plots import plot_ahp_suitability_map, plot_optimal_cs_locations
from src.visualization.pareto_front import plot_pareto_front_2d


def generate_visualizations(base_dir, candidate_gdf, selected_ids, pareto_df):
    """Generate AHP suitability, optimal locations, and Pareto front plots."""
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

    return {
        "ahp_map_path": ahp_map_path,
        "loc_map_path": loc_map_path,
        "pareto_fig_path": pareto_fig_path,
    }

