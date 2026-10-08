"""End-to-end integration test executing the complete pipeline."""

import os
import json
import geopandas as gpd
import pandas as pd
import numpy as np
import pytest
from src.pipeline import RealDataPreflightError, run_full_pipeline


def test_real_mode_fails_before_generation_or_outputs(base_dir, tmp_path, monkeypatch):
    def unexpected_generation(_):
        pytest.fail("real mode must never invoke the synthetic data generator")

    monkeypatch.setattr("src.pipeline.generate_all_data", unexpected_generation)
    with pytest.raises(RealDataPreflightError, match="no synthetic replacements"):
        run_full_pipeline(
            config_path=os.path.join(base_dir, "configs", "default_config.yaml"),
            base_dir=tmp_path,
            settings_path=None,
        )
    assert not (tmp_path / "results").exists()


def test_full_pipeline_execution(base_dir, tmp_path):
    """Test end-to-end pipeline execution using temporary directory for outputs."""
    # Ensure directories exist
    os.makedirs(os.path.join(tmp_path, "results", "tables"), exist_ok=True)
    os.makedirs(os.path.join(tmp_path, "results", "figures"), exist_ok=True)

    # Run a fast end-to-end pipeline run (5 generations, pop 10)
    config_path = os.path.join(base_dir, "configs", "default_config.yaml")
    results = run_full_pipeline(
        config_path=config_path,
        generations=5,
        population=10,
        base_dir=tmp_path,
        data_mode="demo",
    )

    assert results is not None
    assert "pareto_solutions_count" in results
    assert "knee_solution" in results
    assert "grid_feasible" in results

    # Check generated files
    expected_files = [
        os.path.join(tmp_path, "results", "tables", "candidate_sites.csv"),
        os.path.join(tmp_path, "results", "tables", "optimal_solutions_pareto.csv"),
        os.path.join(tmp_path, "results", "tables", "candidate_road_distances.csv"),
        os.path.join(tmp_path, "results", "tables", "baseline_comparison.csv"),
        os.path.join(tmp_path, "results", "run_manifest.json"),
        os.path.join(tmp_path, "results", "reports", f"run_{results['run_id']}.md"),
        os.path.join(tmp_path, "results", "figures", "pareto_frontier_tradeoff.png"),
        os.path.join(tmp_path, "results", "figures", "optimal_cs_locations.png"),
        os.path.join(tmp_path, "results", "figures", "voltage_profile_comparison.png"),
    ]
    extension_dir = os.path.join(tmp_path, "results", "research", results["run_id"])
    expected_files.extend(os.path.join(extension_dir, name) for name in [
        "uncertainty_site_screen.csv",
        "uncertainty_scenario_metrics.csv",
        "equity_accessibility.csv",
        "time_of_day_load_profile.csv",
        "queueing_screen.csv",
        "grid_upgrade_screen.csv",
        "field_validation_template.csv",
        "investment_scenarios.csv",
        "assumptions.json",
    ])

    for f_path in expected_files:
        assert os.path.exists(f_path), f"Expected output file {f_path} not found"
        assert os.path.getsize(f_path) > 0, f"Output file {f_path} is empty"

    road_distances = pd.read_csv(expected_files[2])
    candidates = gpd.read_file(os.path.join(tmp_path, "data", "processed", "candidate_sites_filtered.geojson"))
    baselines = pd.read_csv(expected_files[3])
    with np.load(os.path.join(tmp_path, "data", "processed", "od_travel_time_matrix.npz")) as od:
        assert od["routing_method"].item() == "directed_road_network_dijkstra"
    assert len(road_distances) == len(candidates) * (len(candidates) - 1)
    assert {"road_distance_m", "from_road_snap_distance_m", "to_road_snap_distance_m", "route_status"} <= set(road_distances.columns)
    assert results["candidate_road_distances_path"] == expected_files[2]
    assert set(baselines["strategy"]) == {"NSGA-II knee solution", "Top-ranked baseline", "Demand-greedy baseline"}
    assert baselines["station_count"].nunique() == 1
    manifest = json.loads(open(expected_files[4], encoding="utf-8").read())
    assert manifest["grid_validation"]["validated_against_utility_measurements"] is False
    assert manifest["od_routing_method"] == "directed_road_network_dijkstra"
    assert "research_extensions" in manifest["analysis_outputs"]
    assert manifest["analysis_outputs"]["research_extensions"]["uncertainty_summary"]["samples"] == 250
    report = open(expected_files[5], encoding="utf-8").read()
    assert "ordered pairs" in report
    assert "not against utility observations" in report
    assert "not socioeconomic equity" in report
