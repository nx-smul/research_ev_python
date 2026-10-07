"""Substation transformer augmentation, feeder reconductoring, and BESS peak shaving calculator."""

import numpy as np


def calculate_substation_upgrade_cost(station_power_kw, available_headroom_mva, upgrade_cost_per_mva=3500000.0, power_factor=0.95):
    """Calculate transformer substation upgrading cost if EV load exceeds available headroom.

    Args:
        station_power_kw (float): Total EVCS active power in kW.
        available_headroom_mva (float): Substation spare headroom in MVA.
        upgrade_cost_per_mva (float): Cost to upgrade transformer capacity in BDT/MVA.
        power_factor (float): Grid operational power factor (default 0.95).

    Returns:
        tuple: (upgrade_cost_bdt, excess_mva)
    """
    station_mva = (station_power_kw / 1000.0) / power_factor
    excess_mva = max(0.0, station_mva - available_headroom_mva)

    if excess_mva > 0:
        # Standard transformer sizing steps (e.g. 5, 10, 15, 20 MVA)
        upgraded_mva = np.ceil(excess_mva / 5.0) * 5.0
        cost = upgraded_mva * upgrade_cost_per_mva
        return cost, excess_mva

    return 0.0, 0.0


def calculate_bess_peak_shaving(station_power_kw, available_headroom_mva, peak_hours=4.0, power_factor=0.95):
    """Calculate required Battery Energy Storage System (BESS) capacity to avoid grid overload.

    Args:
        station_power_kw (float): EVCS peak power.
        available_headroom_mva (float): Available grid capacity.
        peak_hours (float): Duration of evening grid peak in Dhaka (e.g. 6 PM - 10 PM = 4 hrs).
        power_factor (float): Power factor.

    Returns:
        dict: Required BESS power (kW), storage capacity (kWh), and estimated Capex.
    """
    headroom_kw = available_headroom_mva * 1000.0 * power_factor
    excess_kw = max(0.0, station_power_kw - headroom_kw)

    if excess_kw <= 0:
        return {
            "needs_bess": False,
            "bess_power_kw": 0.0,
            "bess_energy_kwh": 0.0,
            "bess_capex_bdt": 0.0
        }

    bess_energy_kwh = excess_kw * peak_hours / 0.85  # 85% depth of discharge
    # BESS cost approx $180/kWh -> BDT 20,700/kWh
    bess_capex = bess_energy_kwh * 20700.0

    return {
        "needs_bess": True,
        "bess_power_kw": round(excess_kw, 1),
        "bess_energy_kwh": round(bess_energy_kwh, 1),
        "bess_capex_bdt": round(bess_capex, 2)
    }


class GridReinforcementCalculator:
    """Calculates overall distribution grid reinforcement needs across all candidate stations."""

    def __init__(self, config):
        grid_cfg = config.get("grid", {})
        self.tx_upgrade_cost_per_mva = grid_cfg.get("tx_upgrade_cost_bdt_per_mva", 3500000.0)
        self.reconductor_cost_per_km = grid_cfg.get("feeder_reconductoring_cost_bdt_per_km", 2200000.0)
        self.power_factor = grid_cfg.get("power_factor", 0.95)

    def evaluate_solution_reinforcement(self, selected_stations_df):
        """Calculate total grid reinforcement required for a set of deployed stations."""
        total_upgrade_cost = 0.0
        total_excess_mva = 0.0
        bess_recommendations = []

        for _, row in selected_stations_df.iterrows():
            power_kw = float(row.get("total_power_kw", 0.0))
            headroom_mva = float(row.get("substation_headroom_mva", 5.0))

            cost, excess = calculate_substation_upgrade_cost(
                power_kw, headroom_mva, self.tx_upgrade_cost_per_mva, self.power_factor
            )
            total_upgrade_cost += cost
            total_excess_mva += excess

            bess = calculate_bess_peak_shaving(power_kw, headroom_mva, power_factor=self.power_factor)
            if bess["needs_bess"]:
                bess["site_id"] = row.get("candidate_id", "Unknown")
                bess_recommendations.append(bess)

        return {
            "total_reinforcement_cost_bdt": total_upgrade_cost,
            "total_excess_mva": round(total_excess_mva, 2),
            "bess_required_sites_count": len(bess_recommendations),
            "bess_details": bess_recommendations
        }
