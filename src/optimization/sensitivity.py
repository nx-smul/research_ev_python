"""Small deterministic one-factor-at-a-time optimization sensitivity runs."""

from copy import deepcopy
from collections import Counter
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import validate_config
from src.optimization.nsga2_solver import NSGA2Solver, export_pareto_solutions
from src.visualization.pareto_front import find_knee_point_solution


def _safe_case_name(name):
    """Keep scenario output directories confined to the chosen parent."""
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in name).strip("._")
    if not safe:
        raise ValueError("Scenario name must contain at least one alphanumeric character.")
    return safe


def run_sensitivity(
    dist_matrix,
    time_matrix,
    demand_values,
    candidate_metadata,
    base_config,
    scenarios,
    output_dir,
    *,
    population=None,
    generations=None,
    seed=None,
):
    """Run named independent scenarios on precomputed inputs and write CSV/JSON summaries.

    Supported scenario fields: demand_multiplier, budget_cap_bdt,
    service_radius_rmax_m, random_seed, and charger_mix (a mapping of charger key
    to positive relative weight). This is a model sensitivity study, not a forecast.
    """
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError("scenarios must be a non-empty mapping of scenario names to overrides.")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    all_rows = []
    scenario_records = []
    summary_rows = []
    seed_site_selections = []

    for name, overrides in scenarios.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(overrides, dict):
            raise ValueError("Each sensitivity scenario needs a non-empty name and mapping of overrides.")
        case_name = _safe_case_name(name)
        if any(record["directory"] == case_name for record in scenario_records):
            raise ValueError(f"Scenario names collide after output-path normalization: '{name}'.")
        unknown = set(overrides) - {
            "demand_multiplier", "budget_cap_bdt", "service_radius_rmax_m",
            "random_seed", "charger_mix",
        }
        if unknown:
            raise ValueError(f"Unsupported sensitivity parameters: {', '.join(sorted(unknown))}.")
        config = deepcopy(base_config)
        demand = np.asarray(demand_values, dtype=float).copy()
        multiplier = overrides.get("demand_multiplier", 1.0)
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or not np.isfinite(multiplier) or multiplier <= 0:
            raise ValueError(f"Scenario '{name}' demand_multiplier must be finite and positive.")
        demand *= multiplier
        for key in ("budget_cap_bdt", "service_radius_rmax_m"):
            if key in overrides:
                config["optimization"][key] = overrides[key]
        mix = overrides.get("charger_mix")
        if mix is not None:
            if not isinstance(mix, dict) or set(mix) != set(config["chargers"]):
                raise ValueError(f"Scenario '{name}' charger_mix must specify every configured charger key.")
            weights = {}
            for charger, weight in mix.items():
                if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not np.isfinite(weight) or weight <= 0:
                    raise ValueError(f"Scenario '{name}' charger_mix weights must be finite and positive.")
                weights[charger] = float(weight)
            total = sum(weights.values())
            for charger, weight in weights.items():
                config["chargers"][charger]["power_kw"] *= weight / total
        if population is not None:
            config["optimization"]["nsga2"]["population_size"] = population
        if generations is not None:
            config["optimization"]["nsga2"]["generations"] = generations
        effective_seed = overrides.get("random_seed", seed)
        if effective_seed is not None:
            config["optimization"]["nsga2"]["random_seed"] = effective_seed
        validate_config(config)

        solver = NSGA2Solver(dist_matrix, time_matrix, demand, candidate_metadata, config)
        solver.pop_size = config["optimization"]["nsga2"]["population_size"]
        solver.generations = config["optimization"]["nsga2"]["generations"]
        front, _ = solver.solve(show_progress=False)
        case_dir = target / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        frame = export_pareto_solutions(front, candidate_metadata, config, case_dir / "pareto_solutions.csv")
        frame.insert(0, "scenario", name)
        frame.insert(1, "scenario_class", "sensitivity analysis; not an observation or forecast")
        frame.insert(2, "demand_multiplier", float(multiplier))
        frame.insert(3, "service_radius_rmax_m", config["optimization"].get("service_radius_rmax_m"))
        frame.insert(4, "scenario_budget_cap_bdt", config["optimization"].get("budget_cap_bdt"))
        frame.insert(5, "random_seed", config["optimization"]["nsga2"].get("random_seed"))
        frame.to_csv(case_dir / "pareto_solutions.csv", index=False)
        all_rows.extend(frame.to_dict(orient="records"))
        _, knee = find_knee_point_solution(frame)
        summary_rows.append({
            "scenario": name,
            "scenario_class": "sensitivity analysis; not an observation or forecast",
            "random_seed": int(config["optimization"]["nsga2"]["random_seed"]),
            "knee_solution_id": knee["solution_id"],
            "selected_station_ids": knee["selected_station_ids"],
            "open_station_count": int(knee["open_station_count"]),
            "total_cost_bdt": float(knee["total_cost_bdt"]),
            "demand_coverage_pct": float(knee["demand_coverage_pct"]),
        })
        if "random_seed" in overrides:
            seed_site_selections.extend(str(knee["selected_station_ids"]).split(";"))
        scenario_record = {
            "scenario": name,
            "directory": case_name,
            "scenario_class": "sensitivity analysis; not an observation or forecast",
            "overrides": overrides,
            "effective_config": config,
            "solutions": len(frame),
            "output": str((case_dir / "pareto_solutions.csv").relative_to(target)),
        }
        (case_dir / "scenario.json").write_text(json.dumps(scenario_record, indent=2, default=str) + "\n", encoding="utf-8")
        scenario_records.append(scenario_record)

    combined = pd.DataFrame(all_rows)
    combined.to_csv(target / "sensitivity_results.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(target / "sensitivity_knee_summary.csv", index=False)
    seed_count = sum("random_seed" in overrides for overrides in scenarios.values())
    seed_frequencies = Counter(seed_site_selections)
    stability = pd.DataFrame([
        {
            "candidate_id": candidate_id,
            "selected_seed_runs": count,
            "selection_frequency_pct": 100.0 * count / seed_count,
            "seed_run_count": seed_count,
            "classification": "knee-site selection stability across optimizer seeds; not empirical validation",
        }
        for candidate_id, count in sorted(seed_frequencies.items())
    ], columns=[
        "candidate_id", "selected_seed_runs", "selection_frequency_pct",
        "seed_run_count", "classification",
    ])
    stability.to_csv(target / "optimizer_seed_site_stability.csv", index=False)
    (target / "sensitivity_manifest.json").write_text(json.dumps({
        "classification": "scenario sensitivity analysis; not observed data or a forecast",
        "scenarios": scenario_records,
        "summary": "sensitivity_knee_summary.csv",
        "optimizer_seed_site_stability": "optimizer_seed_site_stability.csv",
    }, indent=2, default=str) + "\n", encoding="utf-8")
    return combined
