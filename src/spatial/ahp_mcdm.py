"""Analytic Hierarchy Process (AHP) and TOPSIS Multi-Criteria Decision Making (MCDM) for spatial suitability analysis."""

import argparse
import os
import sys
import yaml
import numpy as np
import pandas as pd
import geopandas as gpd


# Random Index (RI) lookup table from Saaty (1980) for n = 1 to 10
RANDOM_INDEX = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49
}


class AHPInconsistencyError(ValueError):
    """Raised when AHP Pairwise Comparison Matrix has Consistency Ratio CR >= 0.10."""
    pass


def calculate_ahp_weights(pairwise_matrix, method="eigenvector"):
    """Calculate criterion weights and consistency metrics from a pairwise comparison matrix.

    Args:
        pairwise_matrix (np.ndarray or list of lists): n x n reciprocal comparison matrix.
        method (str): 'eigenvector' (principal eigenvector) or 'geometric_mean'.

    Returns:
        tuple: (weights, lambda_max, CI, CR)
            - weights (np.ndarray): Normalized weights summing to 1.0.
            - lambda_max (float): Maximum eigenvalue.
            - CI (float): Consistency Index.
            - CR (float): Consistency Ratio.
    """
    matrix = np.array(pairwise_matrix, dtype=np.float64)
    n = matrix.shape[0]

    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"Pairwise comparison matrix must be square, got {matrix.shape}")

    if method == "eigenvector":
        eigenvalues, eigenvectors = np.linalg.eig(matrix)
        # Principal eigenvalue is the maximum real part
        max_idx = np.argmax(np.real(eigenvalues))
        lambda_max = float(np.real(eigenvalues[max_idx]))
        principal_vec = np.real(eigenvectors[:, max_idx])
        weights = np.abs(principal_vec) / np.sum(np.abs(principal_vec))
    elif method == "geometric_mean":
        geo_means = np.prod(matrix, axis=1) ** (1.0 / n)
        weights = geo_means / np.sum(geo_means)
        weighted_sum = np.dot(matrix, weights)
        lambda_max = float(np.mean(weighted_sum / weights))
    else:
        raise ValueError(f"Unknown method '{method}', choose 'eigenvector' or 'geometric_mean'")

    if n <= 2:
        CI = 0.0
        CR = 0.0
    else:
        CI = float((lambda_max - n) / (n - 1))
        ri = RANDOM_INDEX.get(n, 1.49)
        CR = float(CI / ri) if ri > 0 else 0.0

    return weights, lambda_max, CI, CR


def compute_consistency_ratio(pairwise_matrix):
    """Convenience helper returning only the Consistency Ratio (CR)."""
    _, _, _, CR = calculate_ahp_weights(pairwise_matrix)
    return CR


def standardize_criteria_fuzzy(values, preference="max", lower_bound=None, upper_bound=None):
    """Standardize raw spatial criterion values into fuzzy membership scores [0, 1].

    Args:
        values (np.ndarray or list): Raw metric values.
        preference (str): 'max' (higher is better), 'min' or 'min_cost'/'min_distance' (lower is better).
        lower_bound (float, optional): Custom minimum bound.
        upper_bound (float, optional): Custom maximum bound.

    Returns:
        np.ndarray: Fuzzy membership scores in [0.0, 1.0].
    """
    arr = np.array(values, dtype=np.float64)
    v_min = lower_bound if lower_bound is not None else np.min(arr)
    v_max = upper_bound if upper_bound is not None else np.max(arr)

    if np.isclose(v_max, v_min):
        return np.ones_like(arr, dtype=np.float64)

    if preference in ["max", "benefit"]:
        fuzzy = (arr - v_min) / (v_max - v_min)
    elif preference in ["min", "cost", "min_cost", "min_distance", "min_risk"]:
        fuzzy = (v_max - arr) / (v_max - v_min)
    else:
        raise ValueError(f"Unknown preference type: {preference}")

    return np.clip(fuzzy, 0.0, 1.0)


def topsis_ranking(decision_matrix, weights, criteria_types):
    """Technique for Order Preference by Similarity to Ideal Solution (TOPSIS).

    Args:
        decision_matrix (np.ndarray): m alternatives x n criteria.
        weights (np.ndarray or list): Weight vector of length n.
        criteria_types (list of str): 'max' for benefit, 'min' for cost per criterion.

    Returns:
        tuple: (relative_closeness, rank_indices)
            - relative_closeness (np.ndarray): Relative closeness score C_i in [0, 1].
            - rank_indices (np.ndarray): Indices sorted from best (1st) to worst.
    """
    X = np.array(decision_matrix, dtype=np.float64)
    m, n = X.shape
    w = np.array(weights, dtype=np.float64)
    w = w / np.sum(w)

    # 1. Vector Normalization
    denom = np.sqrt(np.sum(X**2, axis=0))
    denom[denom == 0] = 1.0
    R = X / denom

    # 2. Weighted Normalization
    V = R * w

    # 3. Determine Positive Ideal (A+) and Negative Ideal (A-) Solutions
    A_plus = np.zeros(n)
    A_minus = np.zeros(n)

    for j in range(n):
        if criteria_types[j] in ["max", "benefit"]:
            A_plus[j] = np.max(V[:, j])
            A_minus[j] = np.min(V[:, j])
        else:
            A_plus[j] = np.min(V[:, j])
            A_minus[j] = np.max(V[:, j])

    # 4. Calculate Euclidean Separation Distances
    S_plus = np.sqrt(np.sum((V - A_plus)**2, axis=1))
    S_minus = np.sqrt(np.sum((V - A_minus)**2, axis=1))

    # 5. Relative Closeness to Ideal Solution C_i = S- / (S+ + S-)
    total_dist = S_plus + S_minus
    total_dist[total_dist == 0] = 1.0
    C = S_minus / total_dist

    rank_indices = np.argsort(-C)  # Descending order: highest score is rank 1
    return C, rank_indices


def compute_spatial_suitability(criteria_df, weights_dict, exclusion_cols=None):
    """Compute composite spatial suitability index S(x, y) = sum(w_k * f_k) * prod(C_m).

    Args:
        criteria_df (pd.DataFrame or gpd.GeoDataFrame): DataFrame with fuzzy standardized criteria.
        weights_dict (dict): Dictionary mapping criterion column name -> weight.
        exclusion_cols (list, optional): List of boolean columns (1 = allowed, 0 = excluded).

    Returns:
        pd.Series: Composite suitability index for each spatial entity.
    """
    total_weight = sum(weights_dict.values())
    suitability = np.zeros(len(criteria_df), dtype=np.float64)

    for col, w in weights_dict.items():
        if col in criteria_df.columns:
            suitability += (w / total_weight) * criteria_df[col].to_numpy(dtype=np.float64)

    if exclusion_cols:
        exclusion_mask = np.ones(len(criteria_df), dtype=np.float64)
        for excl_col in exclusion_cols:
            if excl_col in criteria_df.columns:
                exclusion_mask *= criteria_df[excl_col].astype(float).to_numpy()
        suitability *= exclusion_mask

    return pd.Series(np.clip(suitability, 0.0, 1.0), index=criteria_df.index, name="composite_suitability")


def run_ahp_spatial_pipeline(config_path, output_csv=None):
    """Execute complete AHP-TOPSIS spatial evaluation pipeline."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    pairwise_matrix = config["ahp_mcdm"]["pairwise_matrix"]
    weights, lambda_max, CI, CR = calculate_ahp_weights(pairwise_matrix)

    print(f"[AHP] Principal Eigenvalue (lambda_max): {lambda_max:.4f}")
    print(f"[AHP] Consistency Index (CI): {CI:.4f}")
    print(f"[AHP] Consistency Ratio (CR): {CR:.4f}")

    if CR >= 0.10:
        raise AHPInconsistencyError(f"AHP Consistency Ratio {CR:.4f} exceeds threshold 0.10! Revise comparison matrix.")

    print(f"[AHP] Criteria Weights:")
    crit_keys = list(config["ahp_mcdm"]["criteria"].keys())
    for k, w in zip(crit_keys, weights):
        print(f"  - {k}: {w:.4f}")

    # Load candidate sites GeoJSON or generate if absent
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate_geojson_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
    if not os.path.exists(candidate_geojson_path):
        from src.data_generator import generate_all_data
        generate_all_data(base_dir)

    candidate_gdf = gpd.read_file(candidate_geojson_path)

    # Perform TOPSIS ranking across candidate sites
    feature_cols = [
        "traffic_density_score",
        "poi_score",
        "parking_score",
        "substation_headroom_mva",
        "land_cost_bdt_sqm",
        "distance_to_substation_m"
    ]

    types = ["max", "max", "max", "max", "min", "min"]
    sub_weights = weights[:len(feature_cols)]
    sub_weights = sub_weights / np.sum(sub_weights)

    decision_mat = candidate_gdf[feature_cols].to_numpy()
    topsis_scores, ranks = topsis_ranking(decision_mat, sub_weights, types)

    candidate_gdf["topsis_score"] = topsis_scores.round(4)
    candidate_gdf["topsis_rank"] = np.argsort(ranks) + 1

    # Save output table
    if output_csv:
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        export_df = candidate_gdf[[
            "candidate_id", "site_name", "zone_name", "ahp_suitability_score",
            "topsis_score", "topsis_rank", "land_cost_bdt_sqm",
            "distance_to_substation_m", "substation_headroom_mva"
        ]].copy()
        export_df.sort_values(by="topsis_rank", inplace=True)
        export_df.to_csv(output_csv, index=False)
        print(f"[AHP-TOPSIS] Successfully exported candidate site rankings to {output_csv}")

    return candidate_gdf, weights, CR


def main():
    parser = argparse.ArgumentParser(description="Spatial GIS Multi-Criteria Decision Making (AHP-TOPSIS) for EVCS placement.")
    parser.add_argument("--config", type=str, default="configs/default_config.yaml", help="Path to configuration YAML file.")
    parser.add_argument("--output", type=str, default="results/tables/candidate_sites.csv", help="Output path for ranked candidate sites CSV.")
    args = parser.parse_args()

    run_ahp_spatial_pipeline(args.config, args.output)


if __name__ == "__main__":
    main()
