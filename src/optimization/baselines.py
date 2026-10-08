"""Simple reproducible site-selection baselines for comparison with NSGA-II."""

import numpy as np
import pandas as pd

from src.optimization.nsga2_solver import SolutionCandidate


def compare_site_selection_baselines(
    solver,
    optimizer_solution,
    candidate_metadata,
    ranked_candidates,
    output_path,
):
    """Evaluate AHP-ranked and demand-greedy sites at the optimizer's station count.

    Charger allocations from the selected NSGA-II solution are held fixed and moved
    onto each baseline's sites, isolating siting strategy from sizing decisions.
    """
    site_count = int(np.count_nonzero(optimizer_solution.x))
    if site_count < 1:
        raise ValueError("Cannot benchmark an optimizer solution with no open stations.")
    if site_count > len(candidate_metadata):
        raise ValueError("Optimizer station count exceeds the candidate-site count.")

    charger_patterns = optimizer_solution.Y[np.flatnonzero(optimizer_solution.x)]
    ids = [str(candidate.get("candidate_id")) for candidate in candidate_metadata]
    ranks = {}
    if isinstance(ranked_candidates, pd.DataFrame):
        for row in ranked_candidates.to_dict(orient="records"):
            try:
                ranks[str(row["candidate_id"])] = float(row.get("topsis_rank", np.inf))
            except (TypeError, ValueError):
                continue
    else:
        for row in ranked_candidates or []:
            try:
                ranks[str(row["candidate_id"])] = float(row.get("topsis_rank", np.inf))
            except (TypeError, ValueError):
                continue
    ranked_indices = sorted(
        range(len(candidate_metadata)),
        key=lambda index: (
            ranks.get(ids[index], np.inf),
            -float(candidate_metadata[index].get("ahp_suitability_score", 0) or 0),
            ids[index],
        ),
    )

    reachable = np.asarray(solver.dist_matrix) <= float(solver.r_max)
    uncovered = np.ones(solver.N, dtype=bool)
    greedy_indices = []
    for _ in range(site_count):
        best_index = None
        best_demand = -1.0
        for index in range(solver.M):
            if index in greedy_indices:
                continue
            newly_reachable = reachable[:, index] & uncovered
            covered_demand = float(np.sum(solver.demand_values[newly_reachable]))
            suitability = float(candidate_metadata[index].get("ahp_suitability_score", 0) or 0)
            tie_breaker = (covered_demand, suitability, ids[index])
            if best_index is None or tie_breaker > best_tie_breaker:
                best_index = index
                best_tie_breaker = tie_breaker
                best_demand = covered_demand
        if best_index is None:
            break
        greedy_indices.append(best_index)
        uncovered &= ~reachable[:, best_index]

    strategies = [
        ("NSGA-II knee solution", np.flatnonzero(optimizer_solution.x), "Optimized siting and sizing"),
        ("Top-ranked baseline", ranked_indices[:site_count], "TOPSIS-ranked sites; optimizer sizing held fixed"),
        ("Demand-greedy baseline", greedy_indices, "Greedy uncovered-demand proximity; optimizer sizing held fixed"),
    ]
    rows = []
    for name, selected_indices, method in strategies:
        x = np.zeros(solver.M, dtype=int)
        y = np.zeros_like(optimizer_solution.Y)
        for pattern_index, candidate_index in enumerate(selected_indices):
            x[candidate_index] = 1
            y[candidate_index] = charger_patterns[pattern_index]
        candidate = SolutionCandidate(x, y)
        solver.evaluate_individual(candidate)
        demand_denominator = float(np.sum(solver.demand_values))
        coverage_pct = 100.0 * candidate.F2_coverage / demand_denominator if demand_denominator else 0.0
        rows.append({
            "strategy": name,
            "method": method,
            "station_count": int(np.count_nonzero(x)),
            "selected_station_ids": ";".join(ids[index] for index in selected_indices),
            "system_cost_bdt": float(candidate.F1_cost),
            "demand_coverage_score_kwh": float(candidate.F2_coverage),
            "demand_coverage_pct": float(coverage_pct),
            "upfront_capex_bdt": float(candidate.capex_bdt),
            "budget_cap_bdt": solver.budget_cap_bdt,
            "budget_feasible": bool(candidate.budget_feasible),
        })

    frame = pd.DataFrame(rows)
    optimizer = frame.iloc[0]
    frame["cost_delta_vs_nsga_bdt"] = frame["system_cost_bdt"] - optimizer["system_cost_bdt"]
    frame["coverage_delta_vs_nsga_pp"] = frame["demand_coverage_pct"] - optimizer["demand_coverage_pct"]
    frame.to_csv(output_path, index=False)
    return frame
