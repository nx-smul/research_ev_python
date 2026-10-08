"""Transparent follow-on analyses for EVCS planning scenarios.

These screens use configured assumptions and modeled inputs. They are not field
measurements, socioeconomic equity estimates, utility studies, or forecasts.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_HOURLY_SHARES = np.array([
    0.012, 0.009, 0.007, 0.006, 0.007, 0.012,
    0.025, 0.050, 0.070, 0.065, 0.055, 0.050,
    0.048, 0.050, 0.052, 0.055, 0.060, 0.075,
    0.095, 0.090, 0.070, 0.050, 0.030, 0.017,
], dtype=float)


def _write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _erlang_c_wait_minutes(arrival_rate, service_rate, servers):
    if servers < 1 or service_rate <= 0:
        return None, "no_service_capacity"
    offered_load = arrival_rate / service_rate
    utilization = offered_load / servers
    if utilization >= 1:
        return None, "unstable_at_assumed_peak"
    terms = [offered_load**n / math.factorial(n) for n in range(servers)]
    tail = offered_load**servers / (math.factorial(servers) * (1.0 - utilization))
    probability_wait = tail / (sum(terms) + tail)
    wait_minutes = probability_wait / (servers * service_rate - arrival_rate) * 60.0
    return wait_minutes, "stable_mm_c_estimate"


def _write_uncertainty_screen(path, scenario_path, distances, demand, candidates, solution, config, settings):
    sample_count = int(settings.get("samples", 250))
    if sample_count < 1:
        raise ValueError("research_extensions.uncertainty.samples must be positive.")
    opt = config["optimization"]
    n_demand, n_candidates = distances.shape
    if len(candidates) != n_candidates or len(demand) != n_demand:
        raise ValueError("Uncertainty-screen inputs are not aligned.")
    station_count = int(np.count_nonzero(solution.x))
    radius = float(opt["service_radius_rmax_m"])
    impedance = float(opt.get("lambda_impedance", 0.00035))
    rng = np.random.default_rng(int(settings.get("seed", 2026)))
    frequency = np.zeros(n_candidates, dtype=int)
    score_total = np.zeros(n_candidates, dtype=float)
    scenario_rows = []
    demand_low, demand_high = settings.get("demand_multiplier_range", [0.8, 1.2])
    distance_low, distance_high = settings.get("distance_multiplier_range", [0.85, 1.15])
    cost_low, cost_high = settings.get("site_cost_multiplier_range", [0.8, 1.2])
    land_area = float(config["economic"].get("land_acquisition_base_sqm", 120.0))
    connection_rate = float(config["economic"].get("grid_distance_penalty_bdt_per_m", 1200.0))
    suitability_sd = float(settings.get("suitability_noise_sd", 0.05))
    base_demand = np.asarray(demand, dtype=float)
    matrix = np.asarray(distances, dtype=float)
    base_suitability = np.array([
        float(candidate.get("ahp_suitability_score", 0.5) or 0.5)
        for candidate in candidates
    ])
    base_site_cost = np.array([
        max(1.0, float(candidate.get("land_cost_bdt_sqm", 1.0) or 1.0) * land_area
            + float(candidate.get("distance_to_substation_m", 0.0) or 0.0) * connection_rate)
        for candidate in candidates
    ])

    for _ in range(sample_count):
        demand_draw = base_demand * rng.uniform(demand_low, demand_high) * rng.lognormal(0.0, 0.12, n_demand)
        distances_draw = matrix * rng.uniform(distance_low, distance_high)
        cost_draw = base_site_cost * rng.uniform(cost_low, cost_high)
        suitability_draw = np.clip(
            base_suitability + rng.normal(0.0, suitability_sd, n_candidates), 0.0, 1.0,
        )
        reachable = distances_draw <= radius
        decay = np.exp(-impedance * distances_draw)
        uncovered = np.ones(n_demand, dtype=bool)
        chosen = []
        for _site in range(min(station_count, n_candidates)):
            gains = np.sum(
                demand_draw[:, None] * decay * reachable * uncovered[:, None],
                axis=0,
            )
            utility = gains / cost_draw * (0.75 + 0.5 * suitability_draw)
            if chosen:
                utility[chosen] = -np.inf
            selected = int(np.argmax(utility))
            chosen.append(selected)
            uncovered &= ~reachable[:, selected]
        frequency[chosen] += 1
        score_total += np.sum(demand_draw[:, None] * decay * reachable, axis=0)
        chosen_reachable = reachable[:, chosen]
        chosen_decay = np.where(chosen_reachable, decay[:, chosen], 0.0)
        best_decay = np.max(chosen_decay, axis=1)
        has_service = chosen_reachable.any(axis=1)
        demand_total = float(np.sum(demand_draw))
        scenario_rows.append({
            "sample": len(scenario_rows) + 1,
            "selected_candidate_ids": ";".join(
                str(candidates[index].get("candidate_id", index)) for index in chosen
            ),
            "reachable_demand_pct": float(np.sum(demand_draw[has_service]) / max(demand_total, 1e-12) * 100.0),
            "distance_weighted_coverage_pct": float(np.sum(demand_draw * best_decay) / max(demand_total, 1e-12) * 100.0),
            "selected_site_cost_proxy_bdt": float(np.sum(cost_draw[chosen])),
            "classification": "Monte Carlo heuristic site-screen; not repeated NSGA-II optimization",
        })

    records = []
    for index, candidate in enumerate(candidates):
        records.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "selected_samples": int(frequency[index]),
            "selection_frequency_pct": 100.0 * frequency[index] / sample_count,
            "mean_accessible_demand_score": float(score_total[index] / sample_count),
            "in_optimizer_solution": bool(solution.x[index]),
            "classification": "Monte Carlo heuristic site-screen; not repeated NSGA-II optimization",
        })
    site_frame = _write_csv(pd.DataFrame(records).sort_values(
        ["selection_frequency_pct", "candidate_id"], ascending=[False, True],
    ), path)
    scenario_frame = _write_csv(pd.DataFrame(scenario_rows), scenario_path)
    summary = {
        "samples": sample_count,
        "reachable_demand_pct_p05": float(np.percentile([row["reachable_demand_pct"] for row in scenario_rows], 5)),
        "reachable_demand_pct_mean": float(np.mean([row["reachable_demand_pct"] for row in scenario_rows])),
        "reachable_demand_pct_p95": float(np.percentile([row["reachable_demand_pct"] for row in scenario_rows], 95)),
        "distance_weighted_coverage_pct_p05": float(np.percentile([row["distance_weighted_coverage_pct"] for row in scenario_rows], 5)),
        "distance_weighted_coverage_pct_mean": float(np.mean([row["distance_weighted_coverage_pct"] for row in scenario_rows])),
        "distance_weighted_coverage_pct_p95": float(np.percentile([row["distance_weighted_coverage_pct"] for row in scenario_rows], 95)),
    }
    return site_frame, scenario_frame, summary


def _write_equity_accessibility(path, demand_gdf, demand, distances, solution):
    assignments = np.asarray(solution.z_assignment, dtype=float)
    served_fraction = np.clip(assignments.sum(axis=1), 0.0, 1.0)
    served_demand = np.asarray(demand, dtype=float) * served_fraction
    selected_distance = np.asarray(distances, dtype=float)
    assigned_distance = np.sum(assignments * selected_distance, axis=1)
    served_mean_distance = np.divide(
        assigned_distance, served_fraction,
        out=np.full_like(assigned_distance, np.nan), where=served_fraction > 0,
    )
    if "zone_name" in demand_gdf:
        groups = demand_gdf["zone_name"].fillna("Unclassified").astype(str).to_numpy()
        group_field = "zone_name"
    elif "zone_type" in demand_gdf:
        groups = demand_gdf["zone_type"].fillna("Unclassified").astype(str).to_numpy()
        group_field = "zone_type"
    else:
        groups = np.full(len(demand), "All modeled demand zones")
        group_field = "all_zones"
    frame = pd.DataFrame({
        "group": groups,
        "demand_kwh_day": demand,
        "served_kwh_day": served_demand,
        "served_distance_m": served_mean_distance,
    })
    grouped = frame.groupby("group", dropna=False).agg(
        demand_zones=("demand_kwh_day", "size"),
        modeled_demand_kwh_day=("demand_kwh_day", "sum"),
        assigned_demand_kwh_day=("served_kwh_day", "sum"),
        mean_assigned_distance_m=("served_distance_m", "mean"),
    ).reset_index()
    grouped["modeled_access_pct"] = np.divide(
        grouped["assigned_demand_kwh_day"], grouped["modeled_demand_kwh_day"],
        out=np.zeros(len(grouped), dtype=float),
        where=grouped["modeled_demand_kwh_day"].to_numpy() > 0,
    ) * 100.0
    overall = float(served_demand.sum() / max(float(np.sum(demand)), 1e-12) * 100.0)
    grouped["gap_vs_citywide_pp"] = grouped["modeled_access_pct"] - overall
    grouped.insert(0, "group_field", group_field)
    grouped["interpretation"] = "spatial access proxy only; not socioeconomic equity; no income or demographic data supplied"
    return _write_csv(grouped, path)


def _write_time_profiles(path, total_served_kwh_day, settings):
    shares = np.asarray(settings.get("hourly_energy_shares", DEFAULT_HOURLY_SHARES), dtype=float)
    if shares.shape != (24,) or not np.isfinite(shares).all() or (shares < 0).any() or shares.sum() <= 0:
        raise ValueError("research_extensions.time_of_day.hourly_energy_shares must be 24 non-negative values.")
    shares = shares / shares.sum()
    day_factors = settings.get("day_type_multipliers", {"weekday": 1.0, "weekend": 0.9})
    season_factors = settings.get("season_multipliers", {"dry": 1.0, "monsoon": 1.05})
    rows = []
    for day_type, day_factor in day_factors.items():
        for season, season_factor in season_factors.items():
            daily_energy = total_served_kwh_day * float(day_factor) * float(season_factor)
            for hour, share in enumerate(shares):
                energy = daily_energy * share
                rows.append({
                    "day_type": day_type,
                    "season": season,
                    "hour": hour,
                    "modeled_energy_kwh": energy,
                    "average_load_kw": energy,
                    "hourly_share_pct": share * 100.0,
                    "classification": "assumed hourly profile; no measured charging sessions supplied",
                })
    return _write_csv(pd.DataFrame(rows), path), shares


def _write_queue_screen(path, candidates, solution, demand, shares, config, settings):
    assignments = np.asarray(solution.z_assignment, dtype=float)
    station_demand = assignments.T @ np.asarray(demand, dtype=float)
    peak_share = float(np.max(shares))
    session_kwh = float(settings.get("average_session_kwh", 15.0))
    plug_minutes = float(settings.get("plug_overhead_minutes", 10.0))
    if session_kwh <= 0 or plug_minutes < 0:
        raise ValueError("Queue assumptions need positive session energy and non-negative plug overhead.")
    charger_specs = list(config["chargers"].values())
    rows = []
    for index in np.flatnonzero(solution.x):
        counts = np.asarray(solution.Y[index], dtype=int)
        server_count = int(counts.sum())
        if server_count == 0:
            continue
        service_minutes = [
            session_kwh / float(spec["power_kw"]) * 60.0 + plug_minutes
            for spec in charger_specs
        ]
        mean_service_hours = float(np.average(service_minutes, weights=counts)) / 60.0
        service_rate = 1.0 / mean_service_hours if mean_service_hours > 0 else 0.0
        peak_arrivals = float(station_demand[index]) / session_kwh * peak_share
        wait, status = _erlang_c_wait_minutes(peak_arrivals, service_rate, server_count)
        candidate = candidates[index]
        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "modeled_demand_kwh_day": float(station_demand[index]),
            "assumed_session_kwh": session_kwh,
            "servers": server_count,
            "peak_arrivals_per_hour": peak_arrivals,
            "mean_service_minutes": mean_service_hours * 60.0,
            "peak_utilization_pct": min(100.0, peak_arrivals / max(server_count * service_rate, 1e-12) * 100.0),
            "estimated_peak_wait_minutes": wait,
            "queue_status": status,
            "classification": "M/M/c queueing estimate under assumed arrivals and service times",
        })
    return _write_csv(pd.DataFrame(rows), path)


def _write_grid_upgrade_screen(path, candidates, solution, config):
    power_factor = float(config.get("grid", {}).get("power_factor", 0.95))
    tx_cost = float(config.get("grid", {}).get("tx_upgrade_cost_bdt_per_mva", 0.0))
    feeder_cost_per_km = float(config.get("grid", {}).get("feeder_reconductoring_cost_bdt_per_km", 0.0))
    charger_specs = list(config["chargers"].values())
    rows = []
    for index in np.flatnonzero(solution.x):
        counts = np.asarray(solution.Y[index], dtype=int)
        power_kw = float(sum(count * spec["power_kw"] for count, spec in zip(counts, charger_specs)))
        required_mva = power_kw / (1000.0 * power_factor)
        candidate = candidates[index]
        headroom = float(candidate.get("substation_headroom_mva", 0.0) or 0.0)
        shortfall = max(0.0, required_mva - headroom)
        distance_km = float(candidate.get("distance_to_substation_m", 0.0) or 0.0) / 1000.0
        feeder_cost = distance_km * feeder_cost_per_km if shortfall > 0 else 0.0
        feeder_cost = distance_km * feeder_cost_per_km if shortfall > 0 else 0.0
        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "station_power_kw": power_kw,
            "required_mva_at_assumed_power_factor": required_mva,
            "input_substation_headroom_mva": headroom,
            "estimated_capacity_shortfall_mva": shortfall,
            "transformer_upgrade_cost_bdt": shortfall * tx_cost,
            "substation_distance_km_proxy": distance_km,
            "feeder_upgrade_cost_proxy_bdt": feeder_cost,
            "total_upgrade_cost_screen_bdt": shortfall * tx_cost + feeder_cost,
            "classification": "screening estimate; headroom and distance are input proxies, not utility validation",
        })
    return _write_csv(pd.DataFrame(rows), path)


def _write_field_template(path, demand_gdf, candidates, solution):
    selected = set(np.flatnonzero(solution.x).tolist())
    rows = []
    for index in sorted(selected):
        candidate = candidates[index]
        geometry = candidate.get("geometry")
        point = geometry if hasattr(geometry, "x") else None
        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "longitude": point.x if point is not None else candidate.get("lon", ""),
            "latitude": point.y if point is not None else candidate.get("lat", ""),
            "visit_date": "",
            "observer": "",
            "public_access_confirmed": "",
            "parking_bays_observed": "",
            "landowner_permission_status": "",
            "utility_connection_contact": "",
            "transformer_rating_mva_observed": "",
            "existing_chargers_observed": "",
            "peak_queue_observed": "",
            "photos_or_evidence_reference": "",
            "field_notes": "",
            "record_status": "not_visited",
        })
    columns = [
        "candidate_id", "site_name", "longitude", "latitude", "visit_date", "observer",
        "public_access_confirmed", "parking_bays_observed", "landowner_permission_status",
        "utility_connection_contact", "transformer_rating_mva_observed",
        "existing_chargers_observed", "peak_queue_observed", "photos_or_evidence_reference",
        "field_notes", "record_status",
    ]
    return _write_csv(pd.DataFrame(rows, columns=columns), path)


def _write_investment_scenarios(path, pareto, solutions, config, settings):
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
    return _write_csv(pd.DataFrame(rows), path)


def generate_research_extensions(
    output_dir, demand_gdf, demand_values, distances, candidate_metadata,
    optimizer_solution, pareto_df, pareto_solutions, config,
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
    assumptions = {
        "classification": "assumption-based research screens; not observations or forecasts",
        "uncertainty_screen": settings.get("uncertainty", {}),
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
        "assumptions": str(root / "assumptions.json"),
        "uncertainty_summary": uncertainty_summary,
        "most_frequently_selected_sites": (
            pd.read_csv(uncertainty).head(5)["candidate_id"].astype(str).tolist()
        ),
    }
