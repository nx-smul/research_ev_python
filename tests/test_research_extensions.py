"""Tests for assumption-labeled decision-support analyses."""

import json

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import load_config
from src.optimization.nsga2_solver import SolutionCandidate
from src.optimization.research_extensions import generate_research_extensions
from shapely.geometry import Point


def test_research_extension_bundle_writes_labeled_outputs(base_dir, tmp_path, mock_candidate_gdf):
    config = load_config(f"{base_dir}/configs/default_config.yaml")
    demand = np.array([100.0, 200.0])
    demand_gdf = gpd.GeoDataFrame({
        "demand_id": ["D1", "D2"],
        "zone_name": ["North", "South"],
        "zone_type": ["Residential", "Commercial"],
    }, geometry=[Point(90.4, 23.8), Point(90.41, 23.75)], crs="EPSG:4326")
    distances = np.array([
        [100.0, 1200.0, 3000.0, 4000.0, 5000.0],
        [3000.0, 100.0, 2000.0, 3500.0, 4500.0],
    ])
    solution = SolutionCandidate(
        x=np.array([1, 1, 0, 0, 0]),
        Y=np.array([[1, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
    )
    solution.z_assignment = np.array([
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0],
    ])
    solution.demand_values = demand
    pareto = pd.DataFrame([{
        "solution_id": "SOL-001",
        "upfront_capex_bdt": 1_000_000.0,
        "total_cost_bdt": 1_200_000.0,
        "demand_coverage_pct": 50.0,
        "selected_station_ids": "CS-01;CS-02",
        "charger_allocations_json": '{"Type_1_AC_22kW": 1}',
    }])

    candidates = mock_candidate_gdf.to_dict(orient="records")
    candidates[0]["substation_headroom_mva"] = 0.0
    outputs = generate_research_extensions(
        tmp_path, demand_gdf, demand, distances,
        candidates,
        solution, pareto, [solution], config,
    )

    expected = {
        "uncertainty_site_screen", "uncertainty_scenario_metrics", "equity_accessibility", "time_of_day_load_profile",
        "queueing_screen", "grid_upgrade_screen", "field_validation_template",
        "investment_scenarios", "assumptions",
    }
    assert expected <= outputs.keys()
    for key in expected:
        assert (tmp_path / outputs[key].split("/")[-1]).is_file()
    uncertainty = pd.read_csv(outputs["uncertainty_site_screen"])
    assert uncertainty["selected_samples"].sum() == 250 * 2
    uncertainty_metrics = pd.read_csv(outputs["uncertainty_scenario_metrics"])
    assert len(uncertainty_metrics) == 250
    assert uncertainty_metrics["reachable_demand_pct"].between(0, 100).all()
    equity = pd.read_csv(outputs["equity_accessibility"])
    assert set(equity["group"]) == {"North", "South"}
    assert equity["interpretation"].str.contains("not socioeconomic equity").all()
    time_profile = pd.read_csv(outputs["time_of_day_load_profile"])
    assert len(time_profile) == 24 * 2 * 2
    assert np.isclose(
        time_profile.query("day_type == 'weekday' and season == 'dry'")["modeled_energy_kwh"].sum(),
        demand.sum(),
    )
    field_template = pd.read_csv(outputs["field_validation_template"])
    assert set(field_template["candidate_id"]) == {"CS-01", "CS-02"}
    assert field_template["record_status"].eq("not_visited").all()
    grid_screen = pd.read_csv(outputs["grid_upgrade_screen"])
    assert grid_screen.loc[grid_screen["candidate_id"] == "CS-01", "feeder_upgrade_cost_proxy_bdt"].iloc[0] > 0
    assert outputs["uncertainty_summary"]["samples"] == 250
    assert pd.read_csv(outputs["investment_scenarios"])["classification"].str.contains("assumption").all()
    assumptions = json.loads((tmp_path / "assumptions.json").read_text())
    assert "No socioeconomic" in assumptions["equity_limit"]
