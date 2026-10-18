"""Stage 2 — AHP-TOPSIS spatial ranking of candidate sites."""

import os

from src.spatial.ahp_mcdm import run_ahp_spatial_pipeline


def run_spatial_ranking(config, base_dir):
    """Run GIS-MCDM AHP-TOPSIS ranking and return candidate GeoDataFrame + metadata."""
    candidate_table_path = os.path.join(base_dir, "results", "tables", "candidate_sites.csv")
    candidate_gdf, weights, cr = run_ahp_spatial_pipeline(
        config, candidate_table_path, base_dir=base_dir,
    )
    return {
        "candidate_gdf": candidate_gdf,
        "weights": weights,
        "cr": cr,
        "candidate_table_path": candidate_table_path,
    }

