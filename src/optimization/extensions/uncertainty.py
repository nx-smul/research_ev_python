"""Monte Carlo uncertainty screening for EVCS site selection."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.optimization.extensions._io import write_csv


def write_uncertainty_screen(path, scenario_path, distances, demand, candidates, solution, config, settings):
    """Run Monte Carlo heuristic site-screen under demand/distance/cost uncertainty."""
    sample_count = int(settings.get("samples", 250))
    if sample_count < 1:
        raise ValueError("research_extensions.uncertainty.samples must be positive.")
    opt = config["optimization"]
    n_demand, n_candidates = distances.shape
    if len(candidates) != n_candidates or len(demand) != n_demand:
        raise ValueError("Uncertainty-screen inputs are not aligned.")
    station_count = int(np.count_nonzero(solution.x))
    radius = float(opt["service_radius_rmax_m"])
    impedance = float(opt.get("lambda_impedance", 0.00035))
    rng = np.random.default_rng(int(settings.get("seed", 2026)))
    frequency = np.zeros(n_candidates, dtype=int)
    score_total = np.zeros(n_candidates, dtype=float)
    scenario_rows = []
    demand_low, demand_high = settings.get("demand_multiplier_range", [0.8, 1.2])
    distance_low, distance_high = settings.get("distance_multiplier_range", [0.85, 1.15])
    cost_low, cost_high = settings.get("site_cost_multiplier_range", [0.8, 1.2])
    land_area = float(config["economic"].get("land_acquisition_base_sqm", 120.0))
    connection_rate = float(config["economic"].get("grid_distance_penalty_bdt_per_m", 1200.0))
    suitability_sd = float(settings.get("suitability_noise_sd", 0.05))
    base_demand = np.asarray(demand, dtype=float)
    matrix = np.asarray(distances, dtype=float)
    base_suitability = np.array([
        float(candidate.get("ahp_suitability_score", 0.5) or 0.5)
        for candidate in candidates
    ])
    base_site_cost = np.array([
        max(1.0, float(candidate.get("land_cost_bdt_sqm", 1.0) or 1.0) * land_area
            + float(candidate.get("distance_to_substation_m", 0.0) or 0.0) * connection_rate)
        for candidate in candidates
    ])

    for _ in range(sample_count):
        demand_draw = base_demand * rng.uniform(demand_low, demand_high) * rng.lognormal(0.0, 0.12, n_demand)
        distances_draw = matrix * rng.uniform(distance_low, distance_high)
        cost_draw = base_site_cost * rng.uniform(cost_low, cost_high)
        suitability_draw = np.clip(
            base_suitability + rng.normal(0.0, suitability_sd, n_candidates), 0.0, 1.0,
        )
        reachable = distances_draw <= radius
        decay = np.exp(-impedance * distances_draw)
        uncovered = np.ones(n_demand, dtype=bool)
        chosen = []
        for _site in range(min(station_count, n_candidates)):
            gains = np.sum(
                demand_draw[:, None] * decay * reachable * uncovered[:, None],
                axis=0,
            )
            utility = gains / cost_draw * (0.75 + 0.5 * suitability_draw)
            if chosen:
                utility[chosen] = -np.inf
            selected = int(np.argmax(utility))
            chosen.append(selected)
            uncovered &= ~reachable[:, selected]
        frequency[chosen] += 1
        score_total += np.sum(demand_draw[:, None] * decay * reachable, axis=0)
        chosen_reachable = reachable[:, chosen]
        chosen_decay = np.where(chosen_reachable, decay[:, chosen], 0.0)
        best_decay = np.max(chosen_decay, axis=1)
        has_service = chosen_reachable.any(axis=1)
        demand_total = float(np.sum(demand_draw))
        scenario_rows.append({
            "sample": len(scenario_rows) + 1,
            "selected_candidate_ids": ";".join(
                str(candidates[index].get("candidate_id", index)) for index in chosen
            ),
            "reachable_demand_pct": float(np.sum(demand_draw[has_service]) / max(demand_total, 1e-12) * 100.0),
            "distance_weighted_coverage_pct": float(np.sum(demand_draw * best_decay) / max(demand_total, 1e-12) * 100.0),
            "selected_site_cost_proxy_bdt": float(np.sum(cost_draw[chosen])),
            "classification": "Monte Carlo heuristic site-screen; not repeated NSGA-II optimization",
        })

    records = []
    for index, candidate in enumerate(candidates):
        records.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "selected_samples": int(frequency[index]),
            "selection_frequency_pct": 100.0 * frequency[index] / sample_count,
            "mean_accessible_demand_score": float(score_total[index] / sample_count),
            "in_optimizer_solution": bool(solution.x[index]),
            "classification": "Monte Carlo heuristic site-screen; not repeated NSGA-II optimization",
        })
    site_frame = write_csv(pd.DataFrame(records).sort_values(
        ["selection_frequency_pct", "candidate_id"], ascending=[False, True],
    ), path)
    scenario_frame = write_csv(pd.DataFrame(scenario_rows), scenario_path)
    summary = {
        "samples": sample_count,
        "reachable_demand_pct_p05": float(np.percentile([row["reachable_demand_pct"] for row in scenario_rows], 5)),
        "reachable_demand_pct_mean": float(np.mean([row["reachable_demand_pct"] for row in scenario_rows])),
        "reachable_demand_pct_p95": float(np.percentile([row["reachable_demand_pct"] for row in scenario_rows], 95)),
        "distance_weighted_coverage_pct_p05": float(np.percentile([row["distance_weighted_coverage_pct"] for row in scenario_rows], 5)),
        "distance_weighted_coverage_pct_mean": float(np.mean([row["distance_weighted_coverage_pct"] for row in scenario_rows])),
        "distance_weighted_coverage_pct_p95": float(np.percentile([row["distance_weighted_coverage_pct"] for row in scenario_rows], 95)),
    }
    return site_frame, scenario_frame, summary
