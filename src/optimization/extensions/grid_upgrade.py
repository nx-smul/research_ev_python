"""Grid upgrade cost screening estimates."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_grid_upgrade_screen(path, candidates, solution, config):
    """Screen grid upgrade costs based on substation headroom and distance."""
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
    return write_csv(pd.DataFrame(rows), path)
