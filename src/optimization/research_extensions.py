"""Transparent follow-on analyses for EVCS planning scenarios.

These screens use configured assumptions and modeled inputs. They are not field
measurements, socioeconomic equity estimates, utility studies, or forecasts.

This module now delegates to specialized submodules in src.optimization.extensions.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.optimization.extensions.uncertainty import write_uncertainty_screen as _write_uncertainty_screen
from src.optimization.extensions.equity import write_equity_accessibility as _write_equity_accessibility
from src.optimization.extensions.time_profiles import write_time_profiles as _write_time_profiles, DEFAULT_HOURLY_SHARES
from src.optimization.extensions.queueing import write_queue_screen as _write_queue_screen
from src.optimization.extensions.grid_upgrade import write_grid_upgrade_screen as _write_grid_upgrade_screen
from src.optimization.extensions.field_validation import write_field_template as _write_field_template
from src.optimization.extensions.investment import write_investment_scenarios as _write_investment_scenarios
from src.optimization.extensions.carbon import write_carbon_analysis as _write_carbon_analysis
from src.optimization.extensions.utilization import write_utilization_analysis as _write_utilization_analysis
from src.optimization.extensions.robustness import write_portfolio_robustness as _write_portfolio_robustness, write_site_stability_matrix as _write_site_stability_matrix
from src.optimization.extensions.unmet_demand import write_unmet_demand_analysis as _write_unmet_demand_analysis, write_access_burden_analysis as _write_access_burden_analysis
from src.optimization.extensions.ahp_sensitivity import write_ahp_weight_sensitivity as _write_ahp_weight_sensitivity


def generate_research_extensions(
    output_dir, demand_gdf, demand_values, distances, candidate_metadata,
    optimizer_solution, pareto_df, pareto_solutions, config, time_matrix=None,
):
    """Write uncertainty, access, temporal, queue, grid, field, and investment screens."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    settings = config.get("research_extensions", {})
    uncertainty, uncertainty_metrics, uncertainty_summary = _write_uncertainty_screen(
        root / "uncertainty_site_screen.csv", root / "uncertainty_scenario_metrics.csv", distances, demand_values,
        candidate_metadata, optimizer_solution, config, settings.get("uncertainty", {}),
    )
    equity = _write_equity_accessibility(
        root / "equity_accessibility.csv", demand_gdf, demand_values,
        distances, optimizer_solution,
    )
    assignments = np.asarray(optimizer_solution.z_assignment, dtype=float)
    total_served = float(np.sum(assignments * np.asarray(demand_values)[:, None]))
    time_profile, hourly_shares = _write_time_profiles(
        root / "time_of_day_load_profile.csv", total_served,
        settings.get("time_of_day", {}),
    )
    queue = _write_queue_screen(
        root / "queueing_screen.csv", candidate_metadata, optimizer_solution,
        demand_values, hourly_shares, config, settings.get("queueing", {}),
    )
    grid = _write_grid_upgrade_screen(
        root / "grid_upgrade_screen.csv", candidate_metadata, optimizer_solution, config,
    )
    field_template = _write_field_template(
        root / "field_validation_template.csv", demand_gdf, candidate_metadata, optimizer_solution,
    )
    investment = _write_investment_scenarios(
        root / "investment_scenarios.csv", pareto_df, pareto_solutions, config,
        settings.get("investment", {}),
    )

    # New research extensions
    fleet_emissions = settings.get("carbon", {}).get("fleet_emissions", {
        "grid_emissions_kg_co2_kwh": 0.56,
        "rickshaw_kg_co2_per_km": 0.15,
        "auto_kg_co2_per_km": 0.20,
        "private_car_kg_co2_per_km": 0.18,
    })
    carbon, carbon_summary = _write_carbon_analysis(
        root / "carbon_analysis.csv", config, optimizer_solution, demand_values,
        candidate_metadata, fleet_emissions,
    )

    utilization, utilization_summary = _write_utilization_analysis(
        root / "utilization_analysis.csv", config, optimizer_solution, demand_values,
        candidate_metadata, hourly_shares,
    )

    # Portfolio robustness (requires sensitivity results path)
    robustness_summary = None
    sensitivity_path = root.parent / "sensitivity" / root.name / "sensitivity_results.csv"
    if sensitivity_path.exists():
        robustness = _write_portfolio_robustness(
            root / "portfolio_robustness.csv", str(sensitivity_path),
            optimizer_solution, candidate_metadata, config,
        )
        robustness_summary = robustness
        _write_site_stability_matrix(
            root / "site_stability_matrix.csv", str(sensitivity_path),
            candidate_metadata, config,
        )

    # Unmet demand analysis
    unmet = _write_unmet_demand_analysis(
        root / "unmet_demand_analysis.csv", demand_gdf, demand_values,
        distances, candidate_metadata, optimizer_solution, config, time_matrix,
    )

    # Travel burden analysis
    burden = _write_access_burden_analysis(
        root / "travel_burden_analysis.csv", demand_gdf, demand_values,
        distances, time_matrix if time_matrix is not None else distances * 2.0 / 40.0,  # rough approximation
        optimizer_solution, config,
    )
    burden_summary = burden

    # AHP weight sensitivity
    ahp_sensitivity = _write_ahp_weight_sensitivity(
        root / "ahp_weight_sensitivity.csv", candidate_metadata, config,
        settings.get("ahp_sensitivity", {}),
    )

    assumptions = {
        "classification": "assumption-based research screens; not observations or forecasts",
        "uncertainty_screen": settings.get("uncertainty", {}),
        "carbon": {
            "grid_emissions_kg_per_kwh": fleet_emissions.get("grid_emissions_kg_co2_kwh", 0.56),
            "fleet_composition": fleet_emissions,
        },
        "utilization": {
            "service_hours_per_day": 8.0,
            "peak_hour": int(np.argmax(DEFAULT_HOURLY_SHARES)),
        },
        "time_of_day": {
            **settings.get("time_of_day", {}),
            "hourly_energy_shares": settings.get("time_of_day", {}).get(
                "hourly_energy_shares", DEFAULT_HOURLY_SHARES.tolist(),
            ),
        },
        "queueing": settings.get("queueing", {}),
        "grid_upgrade": {
            "power_factor": config.get("grid", {}).get("power_factor"),
            "tx_upgrade_cost_bdt_per_mva": config.get("grid", {}).get("tx_upgrade_cost_bdt_per_mva"),
            "feeder_reconductoring_cost_bdt_per_km": config.get("grid", {}).get("feeder_reconductoring_cost_bdt_per_km"),
        },
        "investment": settings.get("investment", {}),
        "equity_limit": "No socioeconomic or demographic data were supplied; only spatial access by input zone is reported.",
        "ahp_sensitivity": settings.get("ahp_sensitivity", {}),
    }
    (root / "assumptions.json").write_text(
        json.dumps(assumptions, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return {
        "directory": str(root),
        "uncertainty_site_screen": str(uncertainty),
        "uncertainty_scenario_metrics": str(uncertainty_metrics),
        "equity_accessibility": str(equity),
        "time_of_day_load_profile": str(time_profile),
        "queueing_screen": str(queue),
        "grid_upgrade_screen": str(grid),
        "field_validation_template": str(field_template),
        "investment_scenarios": str(investment),
        "carbon_analysis": str(carbon),
        "utilization_analysis": str(utilization),
        "portfolio_robustness": str(robustness_summary.get("path", "")) if robustness_summary else None,
        "site_stability_matrix": str(root / "site_stability_matrix.csv"),
        "unmet_demand_analysis": str(unmet.get("path", "")) if isinstance(unmet, dict) else str(unmet),
        "travel_burden_analysis": str(burden.get("path", "")) if isinstance(burden, dict) else str(burden),
        "ahp_weight_sensitivity": str(ahp_sensitivity.get("path", "")) if isinstance(ahp_sensitivity, dict) else str(ahp_sensitivity),
        "assumptions": str(root / "assumptions.json"),
        "uncertainty_summary": uncertainty_summary,
        "carbon_summary": carbon_summary,
        "utilization_summary": utilization_summary,
        "most_frequently_selected_sites": (
            pd.read_csv(uncertainty).head(5)["candidate_id"].astype(str).tolist()
        ),
    }
