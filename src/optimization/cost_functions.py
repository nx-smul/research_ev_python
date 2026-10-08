"""Mathematical cost functions and multi-objective fitness evaluation for EVCS placement."""

import math
import numpy as np


def calculate_pv_factor(discount_rate=0.08, lifetime_years=10):
    """Calculate the Present Value (PV) annuity factor for operational expenses.

    PV_factor = (1 - (1 + r)^(-N)) / r
    """
    if discount_rate <= 0:
        return float(lifetime_years)
    return (1.0 - (1.0 + discount_rate) ** (-lifetime_years)) / discount_rate


def calculate_station_capex(y_j, land_cost_per_sqm, charger_specs, base_land_sqm=120.0, land_sqm_per_charger=25.0):
    """Calculate capital expenditure for station j including land acquisition and equipment.

    Args:
        y_j (np.ndarray or list): Integer vector of charger counts by type [y_j1, y_j2, ...].
        land_cost_per_sqm (float): Land price in BDT/m^2 for the station's zone.
        charger_specs (dict): Dictionary of charger type attributes.
        base_land_sqm (float): Fixed land footprint for station amenities & driveways.
        land_sqm_per_charger (float): Incremental land area per charging bay.

    Returns:
        tuple: (total_capex, land_cost, equip_capex, inst_cost)
    """
    total_chargers = sum(y_j)
    if total_chargers == 0:
        return 0.0, 0.0, 0.0, 0.0

    # Land Cost
    total_land_area = base_land_sqm + land_sqm_per_charger * total_chargers
    land_cost = total_land_area * land_cost_per_sqm

    # Equipment Capex & Installation
    equip_capex = 0.0
    inst_cost = 0.0
    for count, (c_key, spec) in zip(y_j, charger_specs.items()):
        if count > 0:
            equip_capex += count * spec["cap_cost_bdt"]
            inst_cost += count * spec["inst_cost_bdt"]

    total_capex = land_cost + equip_capex + inst_cost
    return total_capex, land_cost, equip_capex, inst_cost


def calculate_station_opex_pv(y_j, charger_specs, discount_rate=0.08, lifetime_years=10):
    """Calculate Present Value of lifetime operational and maintenance costs.

    Args:
        y_j (np.ndarray or list): Charger count vector.
        charger_specs (dict): Charger specs including annual_om_bdt.
        discount_rate (float): Discount rate.
        lifetime_years (int): Project lifespan.

    Returns:
        float: Present value of lifetime O&M cost in BDT.
    """
    pv_factor = calculate_pv_factor(discount_rate, lifetime_years)
    annual_om = 0.0
    for count, (c_key, spec) in zip(y_j, charger_specs.items()):
        if count > 0:
            annual_om += count * spec["annual_om_bdt"]

    return annual_om * pv_factor


def calculate_grid_connection_cost(station_power_kw, distance_to_substation_m, cost_per_kw=4500.0, dist_penalty_per_m=1200.0):
    """Calculate grid interconnection and feeder line extension costs."""
    if station_power_kw <= 0:
        return 0.0
    capacity_cost = station_power_kw * cost_per_kw
    line_extension_cost = (distance_to_substation_m / 1000.0) * dist_penalty_per_m * 1000.0
    return capacity_cost + line_extension_cost


def calculate_user_travel_delay_cost(demand_served_matrix, travel_time_matrix, vot_bdt_per_hr=250.0, alpha=0.60):
    """Calculate total monetary value of user travel delay.

    C_travel = alpha * sum_i sum_j (D_i * z_ij * (t_ij / 60) * VOT)
    """
    # travel_time_matrix is in minutes -> convert to hours
    travel_hours = travel_time_matrix / 60.0
    weighted_delay = demand_served_matrix * travel_hours
    total_travel_cost = alpha * np.sum(weighted_delay) * vot_bdt_per_hr
    return total_travel_cost


def evaluate_objectives(x, Y, dist_matrix, time_matrix, demand_values, candidate_metadata, config):
    """Evaluate Objective 1 (F1: Total System Cost min) and Objective 2 (F2: Coverage max).

    Args:
        x (np.ndarray): Binary station selection vector of length M.
        Y (np.ndarray): Integer charger matrix M x K (M stations, K charger types).
        dist_matrix (np.ndarray): N_demand x M_candidate distance matrix in meters.
        time_matrix (np.ndarray): N_demand x M_candidate travel time matrix in minutes.
        demand_values (np.ndarray): Daily energy demand array D_i of length N_demand.
        candidate_metadata (list of dict): Metadata for each candidate site.
        config (dict): Configuration dictionary.

    Returns:
        tuple: (F1_cost_bdt, F2_coverage_score, z_assignment_matrix, penalties)
    """
    M, K = Y.shape
    N = len(demand_values)

    charger_specs = config["chargers"]
    econ = config["economic"]
    opt_params = config["optimization"]

    discount_rate = econ.get("discount_rate", 0.08)
    lifetime_years = econ.get("project_lifetime_years", 10)
    vot = econ.get("vot_bdt_per_hour", 250.0)
    alpha = econ.get("alpha_delay_weight", 0.60)
    base_land_sqm = econ.get("land_acquisition_base_sqm", 120.0)
    land_sqm_per_charger = econ.get("land_sqm_per_charger", 25.0)
    kw_conn_cost = econ.get("grid_connection_cost_per_kw", 4500.0)
    dist_pen_per_m = econ.get("grid_distance_penalty_bdt_per_m", 1200.0)

    lambda_impedance = opt_params.get("lambda_impedance", 0.00035)
    r_max_m = opt_params.get("service_radius_rmax_m", 5000.0)

    # 1. Calculate Daily Energy Capacity and Total Power for each candidate site
    station_daily_kwh = np.zeros(M, dtype=np.float64)
    station_power_kw = np.zeros(M, dtype=np.float64)

    for j in range(M):
        if x[j] == 1:
            for k_idx, (c_key, spec) in enumerate(charger_specs.items()):
                count = Y[j, k_idx]
                if count > 0:
                    station_daily_kwh[j] += count * spec["daily_energy_kwh"] * spec["efficiency"]
                    station_power_kw[j] += count * spec["power_kw"]

    # 2. Demand Allocation z_ij (Greedy Nearest Station within Catchment R_max with capacity check)
    z_ij = np.zeros((N, M), dtype=np.float64)
    remaining_capacity = station_daily_kwh.copy()
    unserved_demand = 0.0

    for i in range(N):
        d_val = demand_values[i]
        # Find open stations within R_max sorted by distance
        open_stations = [j for j in range(M) if x[j] == 1 and dist_matrix[i, j] <= r_max_m]
        open_stations.sort(key=lambda j: dist_matrix[i, j])

        allocated = False
        for j in open_stations:
            if remaining_capacity[j] >= d_val:
                z_ij[i, j] = 1.0
                remaining_capacity[j] -= d_val
                allocated = True
                break
            elif remaining_capacity[j] > 0:
                # Partial allocation
                frac = remaining_capacity[j] / d_val
                z_ij[i, j] = frac
                d_val -= remaining_capacity[j]
                remaining_capacity[j] = 0.0

        if not allocated and np.sum(z_ij[i, :]) < 0.99:
            unserved_demand += (1.0 - np.sum(z_ij[i, :])) * demand_values[i]

    # 3. Calculate Infrastructure Costs (Capex, Opex PV, Land, Grid)
    total_infra_cost = 0.0
    total_penalties = 0.0

    for j in range(M):
        if x[j] == 1:
            meta = candidate_metadata[j]
            land_cost_sqm = meta.get("land_cost_bdt_sqm")
            sub_dist_m = meta.get("distance_to_substation_m")
            sub_headroom_mva = meta.get("substation_headroom_mva")
            candidate_id = meta.get("candidate_id", j)
            if land_cost_sqm is None or not np.isfinite(float(land_cost_sqm)):
                raise ValueError(f"Candidate '{candidate_id}' is missing a finite land_cost_bdt_sqm value.")
            if sub_dist_m is None or not np.isfinite(float(sub_dist_m)):
                raise ValueError(f"Candidate '{candidate_id}' is missing a finite distance_to_substation_m value.")
            if sub_headroom_mva is None or not np.isfinite(float(sub_headroom_mva)):
                raise ValueError(f"Candidate '{candidate_id}' is missing a finite substation_headroom_mva value.")

            # Capex & Land
            capex, land_c, eq_c, inst_c = calculate_station_capex(
                Y[j, :], land_cost_sqm, charger_specs, base_land_sqm, land_sqm_per_charger
            )

            # Opex PV
            opex_pv = calculate_station_opex_pv(
                Y[j, :], charger_specs, discount_rate, lifetime_years
            )

            # Grid Interconnection
            grid_c = calculate_grid_connection_cost(
                station_power_kw[j], sub_dist_m, kw_conn_cost, dist_pen_per_m
            )

            # Substation Headroom Overload Penalty
            station_mva = (station_power_kw[j] / 1000.0) / 0.95
            if station_mva > sub_headroom_mva:
                # Grid reinforcement penalty: BDT 3.5M per excess MVA
                excess_mva = station_mva - sub_headroom_mva
                total_penalties += excess_mva * 3500000.0

            total_infra_cost += (capex + opex_pv + grid_c)

    # 4. User Travel Delay Cost
    demand_served_matrix = z_ij * demand_values[:, np.newaxis]
    user_travel_cost = calculate_user_travel_delay_cost(
        demand_served_matrix, time_matrix, vot, alpha
    )

    # Penalty for unserved demand (social penalty of lost electrification benefit)
    unserved_penalty = unserved_demand * 150.0 * 365.0 * calculate_pv_factor(discount_rate, lifetime_years)

    # Objective 1: Minimize Total Social Cost F1
    F1_cost = total_infra_cost + user_travel_cost + total_penalties + unserved_penalty

    # Objective 2: Maximize Spatial & Demand Coverage F2: sum_i sum_j (D_i * z_ij * exp(-lambda * d_ij))
    decay_matrix = np.exp(-lambda_impedance * dist_matrix)
    F2_coverage = np.sum(demand_served_matrix * decay_matrix)

    return F1_cost, F2_coverage, z_ij, total_penalties
