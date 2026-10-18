"""Portfolio stability and robustness analysis."""

from pathlib import Path
import numpy as np
import pandas as pd
from collections import Counter


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def write_portfolio_robustness(path, sensitivity_results_path, optimizer_solution, candidates, config):
    """Analyze portfolio stability across sensitivity scenarios."""
    sensitivity_results = pd.read_csv(sensitivity_results_path)

    # Group by scenario and extract station selections
    scenario_sites = {}
    for _, row in sensitivity_results.iterrows():
        scenario = row["scenario"]
        station_ids = set(str(row["selected_station_ids"]).split(";")) if row["selected_station_ids"] else set()
        scenario_sites[scenario] = (station_ids, row)

    # Calculate pairwise Jaccard similarity
    scenarios = list(scenario_sites.keys())
    n = len(scenarios)

    similarity_rows = []
    for i in range(n):
        for j in range(i + 1, n):
            set1, _ = scenario_sites[scenarios[i]]
            set2, _ = scenario_sites[scenarios[j]]
            sim = _jaccard_similarity(set1, set2)
            similarity_rows.append({
                "scenario_1": scenarios[i],
                "scenario_2": scenarios[j],
                "jaccard_similarity": round(sim, 3),
                "shared_stations": len(set1 & set2),
                "unique_to_scenario_1": len(set1 - set2),
                "unique_to_scenario_2": len(set2 - set1),
            })

    # Core sites (selected in >80% of scenarios)
    all_station_counts = Counter()
    for scenario, (stations, _) in scenario_sites.items():
        for station in stations:
            all_station_counts[station] += 1

    total_scenarios = len(scenarios)
    core_threshold = 0.8

    core_sites = []
    peripheral_sites = []
    variable_sites = []

    for station_id, count in all_station_counts.items():
        freq = count / total_scenarios
        row = {
            "candidate_id": station_id,
            "times_selected": count,
            "selection_frequency_pct": round(100.0 * freq, 1),
        }

        if freq >= core_threshold:
            core_sites.append(row)
        elif freq <= 0.2:
            peripheral_sites.append(row)
        else:
            variable_sites.append(row)

    # Portfolio overlap summary
    avg_similarity = np.mean([s["jaccard_similarity"] for s in similarity_rows]) if similarity_rows else 0.0

    # Core vs peripheral breakdown
    core_count = len(core_sites)
    peripheral_count = len(peripheral_sites)
    variable_count = len(variable_sites)

    rows = pd.DataFrame(similarity_rows)
    write_csv(rows, path)

    summary = pd.DataFrame([{
        "metric": "portfolio_stability",
        "value": round(avg_similarity, 3),
        "unit": "mean Jaccard similarity",
    }, {
        "metric": "core_sites_count",
        "value": core_count,
        "unit": "stations",
    }, {
        "metric": "peripheral_sites_count",
        "value": peripheral_count,
        "unit": "stations",
    }, {
        "metric": "variable_sites_count",
        "value": variable_count,
        "unit": "stations",
    }, {
        "metric": "core_threshold_pct",
        "value": 100.0 * core_threshold,
        "unit": "%",
    }])

    write_csv(summary, str(path).replace(".csv", "_summary.csv"))

    return {
        "similarity_matrix_path": str(path),
        "core_sites": core_sites,
        "peripheral_sites": peripheral_sites,
        "variable_sites": variable_sites,
        "mean_stability": avg_similarity,
        "classification": "portfolio overlap across model scenarios; not empirical validation",
    }


def write_site_stability_matrix(path, sensitivity_results_path, candidates, config):
    """Create site-level stability matrix showing selection frequency per scenario."""
    sensitivity_results = pd.read_csv(sensitivity_results_path)

    candidate_ids = [c.get("candidate_id") for c in candidates]
    n_candidates = len(candidate_ids)

    # Extract scenarios
    scenarios = sensitivity_results["scenario"].unique().tolist()
    n_scenarios = len(scenarios)

    # Build selection matrix (scenarios x candidates)
    selection_matrix = np.zeros((n_scenarios, n_candidates), dtype=float)

    for i, scenario in enumerate(scenarios):
        row = sensitivity_results[sensitivity_results["scenario"] == scenario].iloc[0]
        selected_ids = set(str(row["selected_station_ids"]).split(";")) if row["selected_station_ids"] else set()

        for j, cid in enumerate(candidate_ids):
            if cid in selected_ids:
                selection_matrix[i, j] = 1.0

    # Calculate frequency per site
    freq_per_site = np.mean(selection_matrix, axis=0)

    # Create summary table
    rows = []
    for j, cid in enumerate(candidate_ids):
        freq = freq_per_site[j]
        rows.append({
            "candidate_id": cid,
            "selection_frequency_pct": round(100.0 * freq, 1),
            "selected_in_scenarios": int(np.sum(selection_matrix[:, j])),
            "total_scenarios": n_scenarios,
            "stability_category": "core" if freq >= 0.8 else "variable" if freq >= 0.2 else "peripheral",
        })

    frame = pd.DataFrame(rows)
    write_csv(frame, path)

    return path, {
        "n_candidates": n_candidates,
        "n_scenarios": n_scenarios,
        "mean_selection_frequency_pct": float(100.0 * np.mean(freq_per_site)),
        "classification": "scenario-based stability analysis; not empirical validation",
    }
