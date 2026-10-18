"""Feasibility invariant validation for optimization solutions."""

import numpy as np


def check_feasibility_invariants(solution, dist_matrix, demand_values, candidate_metadata, config):
    """
    Validate all feasibility constraints and invariants.

    Returns dict with pass/fail status for each invariant.
    """
    M = len(candidate_metadata)
    N = len(demand_values)

    opt = config["optimization"]
    min_open = opt.get("min_open_stations", 3)
    max_open = min(opt.get("max_open_stations", M), M)
    y_min = opt.get("min_chargers_per_station", 2)
    y_max = opt.get("max_chargers_per_station", 12)
    r_max = opt.get("service_radius_rmax_m", 5000.0)
    budget = opt.get("budget_cap_bdt")

    x = solution.x
    Y = solution.Y

    results = {
        "station_count_valid": False,
        "charger_count_valid": False,
        "budget_feasible": False,
        "demand_assignment_valid": False,
        "reachability_valid": False,
        "no_duplicates": True,
        "all_invariants_passed": False,
        "details": {},
    }

    # 1. Station count constraint
    n_open = int(np.count_nonzero(x))
    if min_open <= n_open <= max_open:
        results["station_count_valid"] = True
        results["details"]["station_count"] = n_open
    else:
        results["details"]["station_count"] = n_open
        results["details"]["station_count_error"] = (
            f"Expected {min_open} to {max_open}, got {n_open}"
        )

    # 2. Charger count constraints per station
    charger_valid = True
    for j in range(M):
        if x[j] == 1:
            total_chargers = int(np.sum(Y[j]))
            if y_min <= total_chargers <= y_max:
                results["details"][f"station_{j}_chargers"] = total_chargers
            else:
                charger_valid = False
                results["details"][f"station_{j}_charger_error"] = (
                    f"Expected {y_min} to {y_max}, got {total_chargers}"
                )
    results["charger_count_valid"] = charger_valid

    # 3. Budget constraint
    if budget is not None:
        if solution.capex_bdt <= budget:
            results["budget_feasible"] = True
        else:
            results["details"]["budget_overrun_bdt"] = solution.capex_bdt - budget
    else:
        results["budget_feasible"] = True  # No budget constraint set

    # 4. Demand assignment validity
    z = solution.z_assignment
    if z is not None:
        # All assignments should be non-negative
        if (z >= 0).all():
            results["demand_assignment_valid"] = True
            results["details"]["demand_assignment_sum"] = float(np.sum(z))
            results["details"]["served_demand_kwh"] = float(np.sum(z * demand_values[:, None]))
        else:
            results["details"]["demand_assignment_error"] = "Found negative assignments"

    # 5. Reachability check (assignments should be within service radius)
    reachable = dist_matrix <= r_max
    if z is not None and reachable.shape == z.shape:
        # Check if any assignments are outside service radius
        assigned = (z > 0)
        if not (assigned <= reachable).all():
            n_unreachable = np.sum(assigned & ~reachable)
            results["details"]["unreachable_assignments"] = int(n_unreachable)
            results["reachability_valid"] = False
        else:
            results["reachability_valid"] = True
    else:
        results["reachability_valid"] = False

    # 6. Check for station selection duplicates (should be binary)
    if not np.array_equal(x, (x == 1).astype(int)):
        results["no_duplicates"] = False
        results["details"]["station_binary_error"] = "Station selection not binary"

    # Overall pass/fail
    results["all_invariants_passed"] = all([
        results["station_count_valid"],
        results["charger_count_valid"],
        results["budget_feasible"],
        results["demand_assignment_valid"],
        results["reachability_valid"],
        results["no_duplicates"],
    ])

    return results


def validate_pareto_front(pareto_front, dist_matrix, demand_values, candidate_metadata, config):
    """Validate all solutions in a Pareto front."""
    results = {
        "total_solutions": len(pareto_front),
        "all_valid": True,
        "valid_count": 0,
        "invalid_count": 0,
        "details": [],
    }

    for i, sol in enumerate(pareto_front):
        inv_result = check_feasibility_invariants(
            sol, dist_matrix, demand_values, candidate_metadata, config
        )
        inv_result["solution_id"] = i
        results["details"].append(inv_result)

        if inv_result["all_invariants_passed"]:
            results["valid_count"] += 1
        else:
            results["invalid_count"] += 1
            results["all_valid"] = False

    return results
