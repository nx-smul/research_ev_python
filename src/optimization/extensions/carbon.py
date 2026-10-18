"""Carbon emissions and energy displacement analysis."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_carbon_analysis(path, config, optimizer_solution, demand_values, candidates, fleet_emissions):
    """Calculate carbon emissions avoided by displacing ICE vehicles."""
    # Get total served demand
    assignments = np.asarray(optimizer_solution.z_assignment, dtype=float)
    total_served_kwh_day = float(np.sum(assignments * np.asarray(demand_values)[:, None]))

    # Fleet composition and emissions
    fleet = config.get("fleet", {})

    # Calculate weighted ICE emissions factor (kg CO2 per kWh equivalent)
    weighted_ice_kg_per_kwh = 0.0
    fleet_daily_kwh = 0.0

    for vehicle, spec in fleet.items():
        count = float(spec.get("count", 0))
        daily_km = float(spec.get("daily_km", 0))
        kwh_per_km = float(spec.get("kwh_per_km", 0))
        kg_co2_per_km = float(fleet_emissions.get(vehicle, 0.0))

        daily_energy = count * daily_km * kwh_per_km
        fleet_daily_kwh += daily_energy

        if kwh_per_km > 0:
            weighted_ice_kg_per_kwh += count * daily_km * kg_co2_per_km

    weighted_ice_kg_per_kwh /= max(fleet_daily_kwh, 1e-12)

    # Grid emissions
    grid_emissions_kg_per_kwh = float(fleet_emissions.get("grid_emissions_kg_co2_kwh", 0.56))

    # Annual calculations
    annual_served_kwh = total_served_kwh_day * 365.0

    # Avoided emissions: ICE that would have been used for this travel
    avoided_ice_emissions_kg = annual_served_kwh * weighted_ice_kg_per_kwh

    # Added emissions from grid charging
    grid_emissions_kg = annual_served_kwh * grid_emissions_kg_per_kwh

    # Net benefit
    net_avoided_kg = avoided_ice_emissions_kg - grid_emissions_kg
    net_avoided_tons = net_avoided_kg / 1000.0

    # Per-station breakdown
    station_demand = assignments.T @ np.asarray(demand_values, dtype=float)

    rows = []
    for index in np.flatnonzero(optimizer_solution.x):
        candidate = candidates[index]
        station_kwh_day = station_demand[index]
        station_annual_kwh = station_kwh_day * 365.0

        station_avoided_kg = station_annual_kwh * weighted_ice_kg_per_kwh
        station_grid_kg = station_annual_kwh * grid_emissions_kg_per_kwh
        station_net_kg = station_avoided_kg - station_grid_kg

        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "modeled_annual_kwh_served": round(station_annual_kwh, 1),
            "avoided_ice_emissions_kg_co2": round(station_avoided_kg, 1),
            "added_grid_emissions_kg_co2": round(station_grid_kg, 1),
            "net_avoided_emissions_kg_co2": round(station_net_kg, 1),
            "net_avoided_emissions_tons_co2": round(station_net_kg / 1000.0, 4),
        })

    summary = pd.DataFrame([{
        "metric": "annual_energy_served_kwh",
        "value": round(annual_served_kwh, 1),
        "unit": "kWh",
    }, {
        "metric": "avoided_ice_emissions_tons_co2",
        "value": round(avoided_ice_emissions_kg / 1000.0, 2),
        "unit": "tons CO2",
    }, {
        "metric": "added_grid_emissions_tons_co2",
        "value": round(grid_emissions_kg / 1000.0, 2),
        "unit": "tons CO2",
    }, {
        "metric": "net_avoided_emissions_tons_co2",
        "value": round(net_avoided_tons, 2),
        "unit": "tons CO2",
    }, {
        "metric": "avoidance_factor",
        "value": round(weighted_ice_kg_per_kwh / max(grid_emissions_kg_per_kwh, 1e-12), 2),
        "unit": "ratio",
    }])

    frame = pd.DataFrame(rows)
    write_csv(frame, path)
    write_csv(summary, str(path).replace(".csv", "_summary.csv"))

    return path, {
        "annual_served_kwh": annual_served_kwh,
        "avoided_ice_emissions_tons": avoided_ice_emissions_kg / 1000.0,
        "added_grid_emissions_tons": grid_emissions_kg / 1000.0,
        "net_avoided_tons": net_avoided_tons,
        "ice_factor_kg_per_kwh": weighted_ice_kg_per_kwh,
        "grid_emissions_kg_per_kwh": grid_emissions_kg_per_kwh,
        "classification": "assumption-based carbon screen; fleet composition and emissions factors are estimated",
    }
