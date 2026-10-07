"""Tests for multi-objective optimization (NSGA-II & MILP) and cost models."""

import pytest
import numpy as np

from src.optimization.cost_functions import (
    calculate_pv_factor,
    calculate_station_capex,
    calculate_station_opex_pv,
    calculate_grid_connection_cost,
    calculate_user_travel_delay_cost,
    evaluate_objectives
)
from src.optimization.nsga2_solver import NSGA2Solver, SolutionCandidate
from src.optimization.milp_model import CMO_EVCS_MILP


def test_pv_factor_calculation():
    r = 0.08
    n = 10
    expected_pv = (1.0 - (1.0 + r) ** (-n)) / r
    actual_pv = calculate_pv_factor(discount_rate=r, lifetime_years=n)
    assert np.isclose(expected_pv, actual_pv)
    assert np.isclose(actual_pv, 6.7100813989)

    # Edge case: zero discount rate
    assert calculate_pv_factor(discount_rate=0.0, lifetime_years=10) == 10.0


def test_station_capex_and_opex(sample_config):
    charger_specs = sample_config["chargers"]
    y_j = [2, 1, 0, 1]  # 2 Type1, 1 Type2, 0 Type3, 1 Type4 = 4 chargers total
    land_price = 200000.0  # BDT/sqm

    capex, land_cost, equip_cost, inst_cost = calculate_station_capex(
        y_j=y_j,
        land_cost_per_sqm=land_price,
        charger_specs=charger_specs,
        base_land_sqm=120.0,
        land_sqm_per_charger=25.0
    )

    expected_land_area = 120.0 + 4 * 25.0  # 220 sqm
    expected_land_cost = 220.0 * 200000.0  # 44,000,000 BDT
    assert np.isclose(land_cost, expected_land_cost)

    expected_equip = (
        2 * charger_specs["Type_1_AC_22kW"]["cap_cost_bdt"] +
        1 * charger_specs["Type_2_DC_60kW"]["cap_cost_bdt"] +
        1 * charger_specs["Type_4_Swap_Depot"]["cap_cost_bdt"]
    )
    assert np.isclose(equip_cost, expected_equip)
    assert capex == land_cost + equip_cost + inst_cost

    # Test OPEX PV
    opex_pv = calculate_station_opex_pv(y_j, charger_specs, discount_rate=0.08, lifetime_years=10)
    assert opex_pv > 0


def test_grid_connection_cost():
    power_kw = 500.0
    dist_m = 800.0
    cost = calculate_grid_connection_cost(
        station_power_kw=power_kw,
        distance_to_substation_m=dist_m,
        cost_per_kw=4500.0,
        dist_penalty_per_m=1200.0
    )
    expected_cost = (500.0 * 4500.0) + (0.8 * 1200.0 * 1000.0)
    assert np.isclose(cost, expected_cost)


def test_user_travel_delay_cost():
    demand_served = np.array([[100.0, 0.0], [0.0, 200.0]])
    travel_time_min = np.array([[15.0, 30.0], [25.0, 10.0]])
    vot = 250.0  # BDT/hr
    alpha = 0.60

    travel_hours = travel_time_min / 60.0
    weighted_delay = demand_served * travel_hours
    expected_travel_cost = alpha * np.sum(weighted_delay) * vot

    actual_cost = calculate_user_travel_delay_cost(
        demand_served_matrix=demand_served,
        travel_time_matrix=travel_time_min,
        vot_bdt_per_hr=vot,
        alpha=alpha
    )
    assert np.isclose(actual_cost, expected_travel_cost)


def test_evaluate_objectives(mock_candidate_gdf, mock_od_matrices, sample_config):
    dist_mat, time_mat, demand_values = mock_od_matrices
    M = len(mock_candidate_gdf)
    K = 4

    x = np.array([1, 1, 0, 1, 0], dtype=np.int32)
    Y = np.zeros((M, K), dtype=np.int32)
    Y[0] = [2, 1, 0, 0]
    Y[1] = [1, 2, 1, 0]
    Y[3] = [2, 0, 1, 1]

    candidate_metadata = mock_candidate_gdf.to_dict("records")
    F1, F2, z_ij, penalties = evaluate_objectives(
        x=x,
        Y=Y,
        dist_matrix=dist_mat,
        time_matrix=time_mat,
        demand_values=demand_values,
        candidate_metadata=candidate_metadata,
        config=sample_config
    )

    assert F1 > 0, "Objective 1 (Cost) must be strictly positive"
    assert F2 >= 0, "Objective 2 (Coverage) must be non-negative"
    assert z_ij.shape == (len(demand_values), M)


def test_nsga2_solver_components(mock_candidate_gdf, mock_od_matrices, sample_config):
    dist_mat, time_mat, demand_values = mock_od_matrices
    candidate_metadata = mock_candidate_gdf.to_dict("records")

    solver = NSGA2Solver(
        dist_matrix=dist_mat,
        time_matrix=time_mat,
        demand_values=demand_values,
        candidate_metadata=candidate_metadata,
        config=sample_config
    )

    # Initialize population
    pop = solver.initialize_population()
    assert len(pop) == solver.pop_size

    # Test non-dominated sorting
    fronts = solver.fast_non_dominated_sort(pop)
    assert len(fronts) > 0
    assert sum(len(f) for f in fronts) == len(pop)

    # Test crowding distance assignment
    solver.calculate_crowding_distance(fronts[0])
    assert fronts[0][0].crowding_distance >= 0


def test_nsga2_solver_run(mock_candidate_gdf, mock_od_matrices, sample_config):
    dist_mat, time_mat, demand_values = mock_od_matrices
    candidate_metadata = mock_candidate_gdf.to_dict("records")

    cfg = sample_config.copy()
    cfg["optimization"]["nsga2"]["generations"] = 5
    cfg["optimization"]["nsga2"]["population_size"] = 10

    solver = NSGA2Solver(
        dist_matrix=dist_mat,
        time_matrix=time_mat,
        demand_values=demand_values,
        candidate_metadata=candidate_metadata,
        config=cfg
    )

    pareto_front, _ = solver.solve(generations=cfg["optimization"]["nsga2"]["generations"])
    assert len(pareto_front) > 0

    best_sol = pareto_front[0]
    assert hasattr(best_sol, "F1_cost")
    assert hasattr(best_sol, "F2_coverage")
    assert best_sol.F1_cost > 0


def test_milp_solver(mock_candidate_gdf, mock_od_matrices, sample_config):
    dist_mat, time_mat, demand_values = mock_od_matrices
    candidate_metadata = mock_candidate_gdf.to_dict("records")

    milp_builder = CMO_EVCS_MILP(
        dist_matrix=dist_mat,
        time_matrix=time_mat,
        demand_values=demand_values,
        candidate_metadata=candidate_metadata,
        config=sample_config
    )

    # 1. Test Pyomo Model Construction
    pyomo_model = milp_builder.build_pyomo_model(p_stations=3)
    assert pyomo_model is not None
    assert hasattr(pyomo_model, "x")
    assert hasattr(pyomo_model, "y")
    assert hasattr(pyomo_model, "z")

    # 2. Test SciPy MILP Fallback solver
    scipy_res = milp_builder.solve_scipy_milp_fallback(p_stations=3)
    assert "x" in scipy_res
    assert scipy_res["selected_station_count"] <= 3
    assert len(scipy_res["selected_indices"]) <= 3
