"""Tests for GIS spatial multi-criteria analysis (AHP-TOPSIS), buffering, and road networks."""

import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon

from src.spatial.ahp_mcdm import (
    calculate_ahp_weights,
    compute_consistency_ratio,
    standardize_criteria_fuzzy,
    topsis_ranking,
    compute_spatial_suitability,
    AHPInconsistencyError
)
from src.spatial.spatial_filter import SpatialFilter, filter_candidate_sites
from src.spatial.osm_network import OSMRoadNetwork


def test_ahp_weights_consistent(sample_pairwise_matrix):
    weights, lambda_max, CI, CR = calculate_ahp_weights(sample_pairwise_matrix)
    assert len(weights) == 3
    assert np.isclose(np.sum(weights), 1.0)
    assert np.all(weights > 0)
    assert CR < 0.10, f"Expected CR < 0.10, got {CR}"
    assert weights[0] > weights[1] > weights[2]


def test_ahp_inconsistency_detection(inconsistent_pairwise_matrix):
    weights, lambda_max, CI, CR = calculate_ahp_weights(inconsistent_pairwise_matrix)
    assert CR >= 0.10


def test_fuzzy_standardization():
    raw_vals = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    # Benefit criterion (higher is better)
    fuzzy_max = standardize_criteria_fuzzy(raw_vals, preference="max")
    assert np.isclose(fuzzy_max[0], 0.0)
    assert np.isclose(fuzzy_max[-1], 1.0)
    assert np.all(np.diff(fuzzy_max) >= 0)

    # Cost criterion (lower is better)
    fuzzy_min = standardize_criteria_fuzzy(raw_vals, preference="min_cost")
    assert np.isclose(fuzzy_min[0], 1.0)
    assert np.isclose(fuzzy_min[-1], 0.0)
    assert np.all(np.diff(fuzzy_min) <= 0)


def test_topsis_ranking():
    # 3 alternatives, 3 criteria
    decision_mat = np.array([
        [9.0, 8.0, 100.0],  # Alt 1: High traffic, High POI, Low land cost
        [5.0, 5.0, 200.0],  # Alt 2: Medium traffic, Medium POI, Med land cost
        [2.0, 2.0, 300.0],  # Alt 3: Low traffic, Low POI, High land cost
    ])
    weights = [0.4, 0.4, 0.2]
    types = ["max", "max", "min"]

    scores, ranks = topsis_ranking(decision_mat, weights, types)
    assert len(scores) == 3
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)
    assert ranks[0] == 0, "Alt 1 should be ranked 1st"
    assert scores[0] > scores[1] > scores[2]


def test_spatial_suitability_composite():
    df = pd.DataFrame({
        "crit1": [0.8, 0.5, 0.9],
        "crit2": [0.7, 0.6, 0.8],
        "excl": [1, 1, 0]  # Point 3 is in exclusion zone
    })
    weights = {"crit1": 0.6, "crit2": 0.4}
    suitability = compute_spatial_suitability(df, weights, exclusion_cols=["excl"])

    assert suitability[0] > 0.7
    assert suitability[2] == 0.0, "Excluded point must have suitability score 0.0"


def test_spatial_filter_exclusion(mock_candidate_gdf):
    # Exclusion polygon over Motijheel point (Point(90.420, 23.730))
    poly = Polygon([(90.415, 23.725), (90.425, 23.725), (90.425, 23.735), (90.415, 23.735)])
    landuse_gdf = gpd.GeoDataFrame({
        "zone_type": ["Waterbody"],
        "is_exclusion_zone": [1]
    }, geometry=[poly], crs="EPSG:4326")

    filtered = filter_candidate_sites(mock_candidate_gdf, landuse_gdf)
    assert "CS-02" not in filtered["candidate_id"].values
    assert len(filtered) < len(mock_candidate_gdf)


def test_spatial_filter_spacing(mock_candidate_gdf):
    # Add an identical point to test minimum spacing suppression
    duplicate_pt = mock_candidate_gdf.iloc[0:1].copy()
    duplicate_pt["candidate_id"] = "CS-DUP"
    duplicate_pt["ahp_suitability_score"] = 0.50  # Lower score
    combined = pd.concat([mock_candidate_gdf, duplicate_pt], ignore_index=True)

    s_filter = SpatialFilter({"spatial": {"candidate_site_generation": {"min_spacing_m": 500.0}}})
    spaced = s_filter.apply_spatial_spacing(combined, min_distance_m=500.0)
    assert len(spaced) == len(mock_candidate_gdf)
    assert "CS-01" in spaced["candidate_id"].values
