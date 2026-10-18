"""Stage 4 — NSGA-II optimization, baselines, research extensions, sensitivity."""

import os

import numpy as np
import pandas as pd

from src.optimization.nsga2_solver import NSGA2Solver, canonicalize_pareto_front, export_pareto_solutions
from src.optimization.baselines import compare_site_selection_baselines
from src.optimization.research_extensions import generate_research_extensions
from src.optimization.sensitivity import run_sensitivity
from src.visualization.pareto_front import find_knee_point_solution


def run_optimization(
    base_dir, config, dist_matrix, time_matrix, demand_values,
    demand_gdf, candidate_metadata, candidate_ids, demand_ids,
    run_id, population, generations, sensitivity, candidate_table_path,
):
    """Run NSGA-II, select knee solution, compute baselines and research extensions."""
    solver = NSGA2Solver(dist_matrix, time_matrix, demand_values, candidate_metadata, config)
    solver.pop_size = population
    solver.generations = generations

    pareto_front, _ = solver.solve(generations=generations)
    pareto_front = canonicalize_pareto_front(pareto_front)
    pareto_csv_path = os.path.join(base_dir, "results", "tables", "optimal_solutions_pareto.csv")
    pareto_df = export_pareto_solutions(pareto_front, candidate_metadata, config, pareto_csv_path)
    knee_idx, knee_sol = find_knee_point_solution(pareto_df)
    optimizer_solution = pareto_front[knee_idx]

    baseline_path = os.path.join(base_dir, "results", "tables", "baseline_comparison.csv")
    baseline_df = compare_site_selection_baselines(
        solver, optimizer_solution, candidate_metadata,
        pd.read_csv(candidate_table_path), baseline_path,
    )

    extension_dir = os.path.join(base_dir, "results", "research", run_id)
    research_extensions = generate_research_extensions(
        extension_dir, demand_gdf, demand_values, dist_matrix,
        candidate_metadata, optimizer_solution, pareto_df, pareto_front, config, time_matrix,
    )

    sensitivity_dir = os.path.join(base_dir, "results", "sensitivity", run_id)
    sensitivity_path = None
    if sensitivity:
        base_budget = config["optimization"]["budget_cap_bdt"]
        base_radius = float(config["optimization"]["service_radius_rmax_m"])
        scenarios = {
            "baseline": {},
            "demand_low": {"demand_multiplier": 0.8},
            "demand_high": {"demand_multiplier": 1.2},
            "service_radius_low": {"service_radius_rmax_m": base_radius * 0.8},
            "service_radius_high": {"service_radius_rmax_m": base_radius * 1.2},
        }
        if base_budget is not None:
            scenarios["budget_low"] = {"budget_cap_bdt": float(base_budget) * 0.9}
            scenarios["budget_high"] = {"budget_cap_bdt": float(base_budget) * 1.1}
            base_seed = int(config["optimization"]["nsga2"]["random_seed"])
            scenarios["optimizer_seed_1"] = {"random_seed": base_seed + 1}
            scenarios["optimizer_seed_2"] = {"random_seed": base_seed + 2}
        run_sensitivity(
            dist_matrix, time_matrix, demand_values, candidate_metadata, config,
            scenarios, sensitivity_dir, population=population, generations=generations,
        )
        sensitivity_path = os.path.join(sensitivity_dir, "sensitivity_results.csv")

    return {
        "solver": solver,
        "pareto_front": pareto_front,
        "pareto_df": pareto_df,
        "pareto_csv_path": pareto_csv_path,
        "knee_idx": knee_idx,
        "knee_sol": knee_sol,
        "optimizer_solution": optimizer_solution,
        "baseline_df": baseline_df,
        "baseline_path": baseline_path,
        "research_extensions": research_extensions,
        "sensitivity_path": sensitivity_path,
        "sensitivity_dir": sensitivity_dir,
    }

