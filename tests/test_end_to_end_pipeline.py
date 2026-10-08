"""End-to-end integration test executing the complete pipeline."""

import os
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
        output_deploy_copies=False,
    )

    assert results is not None
    assert "pareto_solutions_count" in results
    assert "knee_solution" in results
    assert "grid_feasible" in results

    # Check generated files
    expected_files = [
        os.path.join(tmp_path, "results", "tables", "candidate_sites.csv"),
        os.path.join(tmp_path, "results", "tables", "optimal_solutions_pareto.csv"),
        os.path.join(tmp_path, "results", "figures", "pareto_frontier_tradeoff.png"),
        os.path.join(tmp_path, "results", "figures", "optimal_cs_locations.png"),
        os.path.join(tmp_path, "results", "figures", "voltage_profile_comparison.png"),
        os.path.join(tmp_path, "results", "figures", "dhaka_evcs_interactive_map.html")
    ]

    for f_path in expected_files:
        assert os.path.exists(f_path), f"Expected output file {f_path} not found"
        assert os.path.getsize(f_path) > 0, f"Output file {f_path} is empty"
