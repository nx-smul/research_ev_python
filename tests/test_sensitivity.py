"""Tests for bounded deterministic optimization sensitivity analysis."""

import json

import numpy as np

from src.config import load_config
from src.optimization.sensitivity import run_sensitivity


def test_sensitivity_writes_labeled_scenarios_without_mutating_config(tmp_path, base_dir, mock_candidate_gdf):
    config = load_config(f"{base_dir}/configs/default_config.yaml")
    config["optimization"].update({"min_open_stations": 1, "max_open_stations": 2})
    config["optimization"]["nsga2"].update({"population_size": 4, "generations": 2, "random_seed": 17})
    original = json.dumps(config, sort_keys=True)
    candidates = mock_candidate_gdf.copy()
    candidates["land_cost_bdt_sqm"] = 1000.0
    candidates["distance_to_substation_m"] = 100.0
    candidates["substation_headroom_mva"] = 100.0
    metadata = candidates.to_dict(orient="records")
    distances = np.array([[100.0, 250.0, 400.0, 550.0, 700.0], [300.0, 120.0, 500.0, 650.0, 800.0]])
    times = distances / 500.0
    demand = np.array([10.0, 20.0])
    scenarios = {
        "baseline": {},
        "radius_case": {"service_radius_rmax_m": 200.0, "demand_multiplier": 1.2},
    }

    results = run_sensitivity(
        distances, times, demand, metadata, config, scenarios, tmp_path / "sensitivity",
        population=4, generations=2, seed=17,
    )

    assert set(results["scenario"]) == {"baseline", "radius_case"}
    assert results["scenario_class"].str.contains("not an observation").all()
    assert json.dumps(config, sort_keys=True) == original
    manifest = json.loads((tmp_path / "sensitivity" / "sensitivity_manifest.json").read_text())
    assert len(manifest["scenarios"]) == 2
    assert (tmp_path / "sensitivity" / "radius_case" / "scenario.json").is_file()


def test_sensitivity_rejects_path_traversal_names(tmp_path, base_dir, mock_candidate_gdf):
    config = load_config(f"{base_dir}/configs/default_config.yaml")
    with __import__("pytest").raises(ValueError, match="collide after output-path normalization"):
        run_sensitivity(
            np.zeros((1, 5)), np.zeros((1, 5)), np.array([1.0]),
            mock_candidate_gdf.to_dict(orient="records"), config,
            {"../outside": {"demand_multiplier": 1}, "outside": {"demand_multiplier": 1}}, tmp_path,
        )


def test_sensitivity_rejects_invalid_demand_multiplier(tmp_path, base_dir, mock_candidate_gdf):
    config = load_config(f"{base_dir}/configs/default_config.yaml")
    with __import__("pytest").raises(ValueError, match="demand_multiplier"):
        run_sensitivity(
            np.zeros((1, 2)), np.zeros((1, 2)), np.array([1.0]),
            mock_candidate_gdf.to_dict(orient="records"), config,
            {"bad": {"demand_multiplier": 0}}, tmp_path,
        )
