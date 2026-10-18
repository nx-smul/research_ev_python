"""Tests for exact solver and optimality gap analysis."""

import numpy as np
import pytest

from src.optimization.exact_solver import solve_exact, compute_optimality_gap
from src.optimization.feasibility_checker import check_feasibility_invariants


@pytest.fixture
def small_instance_config():
    """Configuration for small test instance."""
    return {
        "chargers": {"level2": {"power_kw": 7.2, "cap_cost_bdt": 50000, "inst_cost_bdt": 20000}},
        "optimization": {
            "min_open_stations": 2,
            "max_open_stations": 3,
            "min_chargers_per_station": 2,
            "max_chargers_per_station": 4,
            "service_radius_rmax_m": 5000.0,
            "budget_cap_bdt": 100000000,
            "nsga2": {"random_seed": 42},
        },
        "economic": {"land_acquisition_base_sqm": 120.0, "currency_usd_to_bdt": 115.0},
        "grid": {"power_factor": 0.95},
    }


@pytest.fixture
def small_instance_data(small_instance_config):
    """Small test instance with 5 candidates."""
    np.random.seed(42)
    M = 5
    N = 10

    dist_matrix = np.random.uniform(500, 4000, (N, M)).astype(np.float32)
    time_matrix = dist_matrix / 40.0 * 60.0
    demand_values = np.random.uniform(500, 2000, N)

    candidate_metadata = [
        {
            "candidate_id": f"CS-{i:02d}",
            "site_name": f"Site {i}",
            "land_cost_bdt_sqm": np.random.uniform(100000, 200000),
            "distance_to_substation_m": np.random.uniform(1000, 4000),
            "substation_headroom_mva": np.random.uniform(5, 20),
        }
        for i in range(M)
    ]

    return dist_matrix, time_matrix, demand_values, candidate_metadata, small_instance_config


class TestExactSolver:
    """Tests for exact solver."""

    def test_solve_exact_small_instance(self, small_instance_data):
        """Test exact solver on small instance."""
        dist_matrix, time_matrix, demand_values, candidate_metadata, config = small_instance_data

        pareto_front, all_solutions = solve_exact(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config
        )

        assert len(pareto_front) > 0
        assert all(sol.F1_cost >= 0 for sol in pareto_front)
        assert all(sol.F2_coverage >= 0 for sol in pareto_front)

    def test_exact_solver_pareto_property(self, small_instance_data):
        """Verify Pareto front property: no solution dominates another."""
        dist_matrix, time_matrix, demand_values, candidate_metadata, config = small_instance_data

        pareto_front, _ = solve_exact(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config
        )

        # Check no solution dominates another
        for i, sol1 in enumerate(pareto_front):
            for j, sol2 in enumerate(pareto_front):
                if i != j:
                    # sol2 should not strictly dominate sol1
                    assert not (
                        sol2.F1_cost < sol1.F1_cost and sol2.F2_coverage >= sol1.F2_coverage
                    )
                    assert not (
                        sol2.F1_cost <= sol1.F1_cost and sol2.F2_coverage > sol1.F2_coverage
                    )

    def test_exact_solver_constraint_satisfaction(self, small_instance_data):
        """Verify exact solver respects constraints."""
        dist_matrix, time_matrix, demand_values, candidate_metadata, config = small_instance_data

        pareto_front, _ = solve_exact(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config
        )

        min_open = config["optimization"]["min_open_stations"]
        max_open = config["optimization"]["max_open_stations"]

        for sol in pareto_front:
            n_open = np.count_nonzero(sol.x)
            assert min_open <= n_open <= max_open


class TestOptimalityGap:
    """Tests for optimality gap calculation."""

    def test_gap_calculation(self, small_instance_data):
        """Test optimality gap calculation."""
        dist_matrix, time_matrix, demand_values, candidate_metadata, config = small_instance_data

        exact_front, _ = solve_exact(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config
        )

        # Create mock NSGA-II solutions with known gaps
        mock_nsga_solutions = [
            type('Sol', (), {
                'F1_cost': sol.F1_cost * 1.05,  # 5% worse cost
                'F2_coverage': sol.F2_coverage * 0.98,  # 2% worse coverage
            })()
            for sol in exact_front[:2]
        ]

        gap = compute_optimality_gap(mock_nsga_solutions, exact_front)

        assert gap["cost_gap_pct"] is not None
        assert gap["coverage_gap_pct"] is not None
        assert gap["cost_gap_pct"] >= 0
        assert gap["coverage_gap_pct"] >= 0


class TestFeasibilityChecker:
    """Tests for feasibility invariant checker."""

    def test_check_feasibility_valid_solution(self, small_instance_data):
        """Test checker with valid solution."""
        dist_matrix, time_matrix, demand_values, candidate_metadata, config = small_instance_data

        pareto_front, _ = solve_exact(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config
        )

        sol = pareto_front[0]
        result = check_feasibility_invariants(
            sol, dist_matrix, demand_values, candidate_metadata, config
        )

        assert result["all_invariants_passed"] is True
        assert result["station_count_valid"] is True


class TestExactSolverLimits:
    """Tests for exact solver limits."""

    def test_large_instance_rejection(self):
        """Test that exact solver rejects large instances."""
        import numpy as np

        dist_matrix = np.random.uniform(500, 4000, (20, 20))
        time_matrix = dist_matrix / 40.0 * 60.0
        demand_values = np.random.uniform(500, 2000, 20)
        candidate_metadata = [{"candidate_id": f"CS-{i}"} for i in range(20)]

        config = {
            "chargers": {"level2": {"power_kw": 7.2}},
            "optimization": {
                "min_open_stations": 2,
                "max_open_stations": 5,
                "min_chargers_per_station": 2,
                "max_chargers_per_station": 4,
            },
        }

        with pytest.raises(ValueError, match="limited to 15"):
            solve_exact(dist_matrix, time_matrix, demand_values, candidate_metadata, config)
