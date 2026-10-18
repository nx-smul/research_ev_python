"""Exact solver for small instances - provides optimality bounds."""

import itertools
import numpy as np
from src.optimization.cost_functions import evaluate_objectives
from src.optimization.nsga2_solver import SolutionCandidate


def enumerate_feasible_portfolios(M, min_open, max_open, y_min, y_max):
    """Generate all valid station/charger configurations for small instances."""
    if M > 15:
        raise ValueError(
            f"Exact solver limited to 15 candidates for tractability. "
            f"Found {M} candidates. Use NSGA-II for larger instances."
        )

    # Generate all valid station selection patterns
    station_patterns = []
    for n_stations in range(min_open, max_open + 1):
        for station_combo in itertools.combinations(range(M), n_stations):
            x = np.zeros(M, dtype=int)
            x[list(station_combo)] = 1
            station_patterns.append(x)

    # For each station pattern, generate valid charger allocations
    configurations = []
    K = y_max  # Number of charger types (simplified: assume max charger types)

    for x in station_patterns:
        open_indices = np.flatnonzero(x)

        # Generate all valid charger allocations for open stations
        # For each open station, allocate chargers between y_min and y_max (type 0)
        charger_ranges = [range(y_min, y_max + 1) for _ in open_indices]
        for allocation in itertools.product(*charger_ranges):
            Y = np.zeros((M, 1), dtype=int)
            for idx, count in zip(open_indices, allocation):
                Y[idx, 0] = count
            configurations.append((x.copy(), Y.copy()))

    return configurations


def solve_exact(dist_matrix, time_matrix, demand_values, candidate_metadata, config):
    """
    Exhaustive search over feasible portfolios to find true Pareto front.

    Returns exact Pareto optimal solutions for verification purposes.
    Limited to small instances (M <= 15 candidates) due to combinatorial explosion.
    """
    M = len(candidate_metadata)
    K = len(config["chargers"])

    opt = config["optimization"]
    min_open = opt.get("min_open_stations", 3)
    max_open = min(opt.get("max_open_stations", M), M)
    y_min = opt.get("min_chargers_per_station", 2)
    y_max = opt.get("max_chargers_per_station", 12)

    if M > 15:
        raise ValueError(
            f"Exact solver limited to 15 candidates (found {M}). "
            f"Use NSGA-II for larger instances; exact search is combinatorially expensive."
        )

    # Generate all feasible configurations
    configs = enumerate_feasible_portfolios(M, min_open, max_open, y_min, y_max)

    if not configs:
        raise ValueError("No feasible configurations exist with given constraints.")

    # Evaluate each configuration
    solutions = []
    for x, Y in configs:
        F1, F2, z_mat, penalties = evaluate_objectives(
            x, Y, dist_matrix, time_matrix,
            demand_values, candidate_metadata, config
        )

        capex = sum(
            float(candidate_metadata[j].get("land_cost_bdt_sqm", 0) or 0) * config["economic"].get("land_acquisition_base_sqm", 120.0)
            for j in np.flatnonzero(x)
        )

        sol = SolutionCandidate(x, Y)
        sol.F1_cost = F1
        sol.F2_coverage = F2
        sol.objectives = [F1, -F2]
        sol.capex_bdt = capex
        sol.demand_values = demand_values.copy()
        sol.z_assignment = z_mat
        solutions.append(sol)

    # Extract Pareto front (non-dominated solutions)
    pareto_front = []
    for i, sol in enumerate(solutions):
        dominated = False
        for j, other in enumerate(solutions):
            if i != j:
                # Check if other dominates sol
                if other.F1_cost <= sol.F1_cost and other.F2_coverage >= sol.F2_coverage:
                    if other.F1_cost < sol.F1_cost or other.F2_coverage > sol.F2_coverage:
                        dominated = True
                        break
        if not dominated:
            pareto_front.append(sol)

    # Sort by cost
    pareto_front.sort(key=lambda s: s.F1_cost)

    return pareto_front, solutions


def compute_optimality_gap(nsga_front, exact_front):
    """
    Calculate optimality gap of NSGA-II solutions relative to exact optimum.

    Returns gap percentages for both objectives.
    """
    if not exact_front:
        return {"cost_gap_pct": None, "coverage_gap_pct": None}

    # Find best values from exact front
    best_cost = min(s.F1_cost for s in exact_front)
    best_coverage = max(s.F2_coverage for s in exact_front)

    # Calculate gaps for NSGA-II solutions
    gaps = []
    for sol in nsga_front:
        cost_gap = (sol.F1_cost - best_cost) / max(best_cost, 1e-12) * 100
        coverage_gap = (best_coverage - sol.F2_coverage) / max(best_coverage, 1e-12) * 100
        gaps.append((cost_gap, coverage_gap))

    return {
        "cost_gap_pct": np.mean([g[0] for g in gaps]),
        "coverage_gap_pct": np.mean([g[1] for g in gaps]),
        "best_cost_bdt": best_cost,
        "best_coverage_kwh": best_coverage,
        "nsga2_solutions": len(nsga_front),
        "exact_solutions": len(exact_front),
    }
