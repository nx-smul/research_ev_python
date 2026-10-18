"""Investment scenario analysis."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.optimization.extensions._io import write_csv


def write_investment_scenarios(path, pareto, solutions, config, settings):
    """Generate investment scenarios under different budget and operating models."""
    budget = config["optimization"].get("budget_cap_bdt")
    if budget is None:
        raise ValueError("Investment scenarios require optimization.budget_cap_bdt.")
    multipliers = settings.get("budget_multipliers", [0.5, 0.75, 1.0, 1.25])
    models = settings.get("operating_models", {
        "public_access": {"tariff_bdt_kwh": 20.0},
        "commercial": {"tariff_bdt_kwh": 26.0},
        "concessional": {"tariff_bdt_kwh": 16.0},
    })
    energy_cost = float(settings.get("electricity_cost_bdt_kwh", 12.0))
    grid_emissions = float(settings.get("grid_emissions_kg_co2_kwh", 0.56))
    fleet_emissions = settings.get("counterfactual_ice_kg_co2_per_km", {})
    fleet = config.get("fleet", {})
    annual_energy_by_solution = {}
    annual_om_by_solution = {}
    for index, solution in enumerate(solutions):
        daily_served = float(np.sum(np.asarray(solution.z_assignment) * np.asarray(solution.demand_values)[:, None]))
        annual_energy_by_solution[index] = daily_served * 365.0
        annual_om_by_solution[index] = sum(
            int(count) * float(spec.get("annual_om_bdt", 0.0))
            for count, spec in zip(np.sum(solution.Y, axis=0), config["chargers"].values())
        )
    weighted_ice_kg_per_kwh = 0.0
    fleet_daily_kwh = 0.0
    for vehicle, spec in fleet.items():
        daily_energy = float(spec.get("count", 0)) * float(spec.get("daily_km", 0)) * float(spec.get("kwh_per_km", 0))
        fleet_daily_kwh += daily_energy
        kg_per_km = float(fleet_emissions.get(vehicle, 0.0))
        weighted_ice_kg_per_kwh += daily_energy * kg_per_km / max(float(spec.get("kwh_per_km", 0)), 1e-12)
    weighted_ice_kg_per_kwh /= max(fleet_daily_kwh, 1e-12)

    rows = []
    for multiplier in multipliers:
        cap = float(budget) * float(multiplier)
        feasible = [
            index for index, record in enumerate(pareto.to_dict(orient="records"))
            if float(record["upfront_capex_bdt"]) <= cap
        ]
        scenario_name = f"budget_{float(multiplier):g}x"
        if not feasible:
            rows.append({
                "budget_scenario": scenario_name, "budget_cap_bdt": cap,
                "operating_model": "", "status": "no_pareto_solution_within_cap",
                "classification": "illustrative investment screen; optimizer Pareto set only",
            })
            continue
        chosen_index = max(
            feasible,
            key=lambda index: (
                float(pareto.iloc[index]["demand_coverage_pct"]),
                -float(pareto.iloc[index]["total_cost_bdt"]),
            ),
        )
        record = pareto.iloc[chosen_index]
        annual_energy = annual_energy_by_solution.get(chosen_index, 0.0)
        annual_emissions_net_benefit = annual_energy * (weighted_ice_kg_per_kwh - grid_emissions)
        for model_name, model in models.items():
            tariff = float(model["tariff_bdt_kwh"])
            revenue = annual_energy * tariff
            annual_energy_cost = annual_energy * energy_cost
            annual_om = annual_om_by_solution.get(chosen_index, 0.0)
            net = revenue - annual_energy_cost - annual_om
            capex = float(record["upfront_capex_bdt"])
            rows.append({
                "budget_scenario": scenario_name,
                "budget_cap_bdt": cap,
                "operating_model": model_name,
                "status": "screened_pareto_solution",
                "solution_id": record["solution_id"],
                "selected_station_ids": record["selected_station_ids"],
                "charger_allocations_json": record["charger_allocations_json"],
                "upfront_capex_bdt": capex,
                "modeled_coverage_pct": float(record["demand_coverage_pct"]),
                "annual_modeled_energy_served_kwh": annual_energy,
                "assumed_tariff_bdt_kwh": tariff,
                "assumed_electricity_cost_bdt_kwh": energy_cost,
                "annual_net_operating_surplus_bdt": net,
                "simple_payback_years": capex / net if net > 0 else None,
                "estimated_net_avoided_kg_co2_year": annual_emissions_net_benefit,
                "classification": "illustrative operating/emissions scenario; assumptions are not measured",
            })
    return write_csv(pd.DataFrame(rows), path)
