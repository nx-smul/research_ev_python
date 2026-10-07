"""Distribution Grid AC Power Flow Simulation (Newton-Raphson) using pandapower."""

import argparse
import os
import json
import math
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import pandapower as pp
import pandapower.networks as nw

from .voltage_stability import evaluate_voltage_stability, evaluate_thermal_loading


class GridPowerFlowSimulator:
    """Simulates AC power flow on Dhaka distribution networks (DPDC 33kV & DESCO 11kV)."""

    def __init__(self, network_json_path=None):
        self.net = None
        self.base_net = None
        if network_json_path and os.path.exists(network_json_path):
            self.load_network(network_json_path)

    def load_network(self, network_json_path):
        """Load pandapower network from JSON."""
        self.net = pp.from_json(network_json_path)
        self.base_net = pp.from_json(network_json_path)

    def run_baseline_power_flow(self):
        """Run AC power flow on baseline grid (without added EV charging loads)."""
        try:
            pp.runpp(self.base_net, algorithm="nr", numba=False, enforce_q_lims=False)
        except Exception:
            pp.runpp(self.base_net, algorithm="bfsw", numba=False)

        bus_res = self.base_net.res_bus.copy()
        line_res = self.base_net.res_line.copy()
        trafo_res = self.base_net.res_trafo.copy() if hasattr(self.base_net, "res_trafo") else None

        metrics = evaluate_voltage_stability(bus_res)
        thermal = evaluate_thermal_loading(line_res, trafo_res)
        return bus_res, line_res, metrics, thermal

    def inject_ev_station_loads(self, stations_df, power_factor=0.95):
        """Map and inject EVCS charging power demands into nearest grid buses.

        Args:
            stations_df (pd.DataFrame): DataFrame of selected stations with coordinates or sub_ids.
            power_factor (float): Power factor of EV chargers (default 0.95).
        """
        # Create working copy of network
        self.net = pp.from_json(pp.to_json(self.base_net))

        q_mult = math.tan(math.acos(power_factor))

        for _, row in stations_df.iterrows():
            power_kw = float(row.get("total_grid_power_kw", row.get("total_power_kw", 800.0)))
            if power_kw <= 0:
                continue

            p_mw = power_kw / 1000.0
            q_mvar = p_mw * q_mult

            # Match to bus by nearest coordinate or name
            target_bus = None
            if "nearest_substation_id" in row and row["nearest_substation_id"]:
                sub_id = str(row["nearest_substation_id"])
                # Match in bus names
                for b_idx, b_name in self.net.bus["name"].items():
                    if sub_id in str(b_name):
                        target_bus = b_idx
                        break

            if target_bus is None and "lon" in row and "lat" in row:
                # Coordinate matching
                lon, lat = float(row["lon"]), float(row["lat"])
                min_d = float("inf")
                for b_idx, b_row in self.net.bus.iterrows():
                    b_geo = self.net.bus_geodata.loc[b_idx] if b_idx in self.net.bus_geodata.index else None
                    if b_geo is not None:
                        d = (b_geo["x"] - lon)**2 + (b_geo["y"] - lat)**2
                        if d < min_d:
                            min_d = d
                            target_bus = b_idx

            if target_bus is None:
                # Default to a random non-slack bus
                target_bus = self.net.bus.index[1 % len(self.net.bus)]

            # Add EV load element
            pp.create_load(
                self.net,
                bus=target_bus,
                p_mw=p_mw,
                q_mvar=q_mvar,
                name=f"EVCS_{row.get('candidate_id', 'Station')}"
            )

    def run_ev_power_flow(self):
        """Run AC power flow on EV-integrated network."""
        try:
            pp.runpp(self.net, algorithm="nr", numba=False, enforce_q_lims=False)
        except Exception:
            pp.runpp(self.net, algorithm="bfsw", numba=False)

        bus_res = self.net.res_bus.copy()
        line_res = self.net.res_line.copy()
        trafo_res = self.net.res_trafo.copy() if hasattr(self.net, "res_trafo") else None

        metrics = evaluate_voltage_stability(bus_res)
        thermal = evaluate_thermal_loading(line_res, trafo_res)
        return bus_res, line_res, metrics, thermal


def run_ac_power_flow(network_path, stations_df=None):
    """Convenience helper to run power flow simulation."""
    sim = GridPowerFlowSimulator(network_path)
    base_bus, base_line, base_v_met, base_t_met = sim.run_baseline_power_flow()

    if stations_df is not None and not stations_df.empty:
        sim.inject_ev_station_loads(stations_df)
        ev_bus, ev_line, ev_v_met, ev_t_met = sim.run_ev_power_flow()
    else:
        ev_bus, ev_line, ev_v_met, ev_t_met = base_bus, base_line, base_v_met, base_t_met

    return {
        "base_bus": base_bus,
        "base_line": base_line,
        "base_voltage_metrics": base_v_met,
        "base_thermal_metrics": base_t_met,
        "ev_bus": ev_bus,
        "ev_line": ev_line,
        "ev_voltage_metrics": ev_v_met,
        "ev_thermal_metrics": ev_t_met,
    }


def plot_voltage_profile_comparison(base_bus_df, ev_bus_df, output_fig_path):
    """Generate high-resolution publication plot of bus voltage profiles."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

    buses = base_bus_df.index.tolist()
    v_base = base_bus_df["vm_pu"].to_numpy()
    v_ev = ev_bus_df["vm_pu"].to_numpy()

    # Upper subplot: Voltage Profiles
    ax1.plot(buses, v_base, marker="o", color="#1f77b4", linewidth=2.0, label="Baseline Grid (No EV)")
    ax1.plot(buses, v_ev, marker="s", color="#d62728", linewidth=2.0, linestyle="--", label="Optimal EVCS Integrated")

    # Statutory limits (0.95 - 1.05 p.u.)
    ax1.axhline(1.05, color="gray", linestyle=":", label="Upper Voltage Limit (1.05 p.u.)")
    ax1.axhline(0.95, color="red", linestyle="-.", label="Lower Voltage Limit (0.95 p.u.)")
    ax1.axhline(1.00, color="green", linestyle="--", alpha=0.5, label="Nominal Voltage (1.00 p.u.)")
    ax1.fill_between(buses, 0.95, 1.05, color="green", alpha=0.06)

    ax1.set_ylabel("Bus Voltage (p.u.)", fontsize=12, fontweight="bold")
    ax1.set_title("Distribution Grid Bus Voltage Profile: Baseline vs. Optimal EVCS Load (Dhaka)", fontsize=14, fontweight="bold", pad=12)
    ax1.legend(loc="lower left", frameon=True, fontsize=10)
    ax1.set_ylim(0.92, 1.06)

    # Lower subplot: Delta Voltage Drop
    delta_v = (v_ev - v_base) * 100.0  # in percentage drop
    colors = ["#d62728" if d < 0 else "#2ca02c" for d in delta_v]
    ax2.bar(buses, delta_v, color=colors, alpha=0.8, width=0.5)
    ax2.set_xlabel("Distribution Substation Bus Index", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Delta V (%)", fontsize=11, fontweight="bold")
    ax2.axhline(0, color="black", linewidth=0.8)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_fig_path), exist_ok=True)
    plt.savefig(output_fig_path, dpi=300)
    plt.close()
    print(f"[Power Flow] Voltage profile comparison plot saved to: {output_fig_path}")


def main():
    parser = argparse.ArgumentParser(description="Distribution Grid AC Power Flow Validation for EVCS placements.")
    parser.add_argument("--network", type=str, default="data/grid_models/dpdc_33kv_subnetwork.json", help="Path to pandapower network JSON.")
    parser.add_argument("--stations", type=str, default="results/tables/optimal_solutions_pareto.csv", help="Path to optimal stations CSV.")
    parser.add_argument("--output", type=str, default="results/figures/voltage_profile_comparison.png", help="Output path for voltage profile plot.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    net_path = os.path.join(base_dir, args.network) if not os.path.isabs(args.network) else args.network
    stations_path = os.path.join(base_dir, args.stations) if not os.path.isabs(args.stations) else args.stations
    out_fig_path = os.path.join(base_dir, args.output) if not os.path.isabs(args.output) else args.output

    if not os.path.exists(net_path):
        from src.data_generator import generate_all_data
        generate_all_data(base_dir)

    sim = GridPowerFlowSimulator(net_path)
    base_bus, base_line, base_v_met, base_t_met = sim.run_baseline_power_flow()

    print(f"[Power Flow] Baseline Grid AC Power Flow:")
    print(f"  - Min Bus Voltage: {base_v_met['min_v_pu']} p.u.")
    print(f"  - Max Bus Voltage: {base_v_met['max_v_pu']} p.u.")
    print(f"  - Voltage Deviation Index (VDI): {base_v_met['vdi']}")
    print(f"  - Max Line Loading: {base_t_met['max_line_loading_pct']}%")

    # Load stations from pareto CSV
    if os.path.exists(stations_path):
        pareto_df = pd.read_csv(stations_path)
        # Select knee-point or median solution
        chosen_sol = pareto_df.iloc[len(pareto_df) // 2]
        print(f"[Power Flow] Testing Solution '{chosen_sol['solution_id']}' (Total Power: {chosen_sol['total_grid_power_kw']} kW)...")

        # Load candidate sites to get coordinates & sub IDs
        cand_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
        cand_gdf = gpd.read_file(cand_path)

        selected_ids = chosen_sol["selected_station_ids"].split(";")
        active_stations_df = cand_gdf[cand_gdf["candidate_id"].isin(selected_ids)].copy()
        active_stations_df["total_grid_power_kw"] = float(chosen_sol["total_grid_power_kw"]) / max(1, len(selected_ids))

        sim.inject_ev_station_loads(active_stations_df)
        ev_bus, ev_line, ev_v_met, ev_t_met = sim.run_ev_power_flow()

        print(f"[Power Flow] EV-Integrated Grid AC Power Flow:")
        print(f"  - Min Bus Voltage: {ev_v_met['min_v_pu']} p.u.")
        print(f"  - Max Bus Voltage: {ev_v_met['max_v_pu']} p.u.")
        print(f"  - Voltage Deviation Index (VDI): {ev_v_met['vdi']}")
        print(f"  - Max Line Loading: {ev_t_met['max_line_loading_pct']}%")
        print(f"  - Grid Feasible: {'YES' if ev_v_met['is_compliant'] and ev_t_met['is_thermal_compliant'] else 'NO (Requires Reinforcement)'}")
    else:
        ev_bus = base_bus

    plot_voltage_profile_comparison(base_bus, ev_bus, out_fig_path)


if __name__ == "__main__":
    main()
