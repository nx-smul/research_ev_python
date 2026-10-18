"""Stage 5 — Distribution grid AC power flow simulation."""

import os

import numpy as np

from src.grid.power_flow import GridPowerFlowSimulator, plot_voltage_profile_comparison


def run_grid_analysis(base_dir, config, candidate_gdf, candidate_metadata, optimizer_solution, knee_sol):
    """Run pandapower AC power flow for the selected knee-point solution."""
    dpdc_net_path = os.path.join(base_dir, "data", "grid_models", "dpdc_33kv_subnetwork.json")
    sim = GridPowerFlowSimulator(dpdc_net_path)
    base_bus, base_line, base_v_met, base_t_met = sim.run_baseline_power_flow()

    selected_ids = str(knee_sol["selected_station_ids"]).split(";")
    active_stations_df = candidate_gdf[candidate_gdf["candidate_id"].isin(selected_ids)].copy()
    charger_specs = list(config["chargers"].values())
    station_power = {
        candidate_metadata[index]["candidate_id"]: float(
            sum(count * spec["power_kw"] for count, spec in zip(optimizer_solution.Y[index], charger_specs))
        )
        for index in np.flatnonzero(optimizer_solution.x)
    }
    active_stations_df["total_grid_power_kw"] = active_stations_df["candidate_id"].map(station_power)

    sim.inject_ev_station_loads(active_stations_df)
    ev_bus, ev_line, ev_v_met, ev_t_met = sim.run_ev_power_flow()

    voltage_fig_path = os.path.join(base_dir, "results", "figures", "voltage_profile_comparison.png")
    plot_voltage_profile_comparison(base_bus, ev_bus, voltage_fig_path)

    return {
        "sim": sim,
        "base_bus": base_bus,
        "ev_bus": ev_bus,
        "ev_v_met": ev_v_met,
        "ev_t_met": ev_t_met,
        "voltage_fig_path": voltage_fig_path,
        "selected_ids": selected_ids,
        "active_stations_df": active_stations_df,
    }

