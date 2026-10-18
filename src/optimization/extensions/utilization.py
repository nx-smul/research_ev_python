"""Charger utilization and efficiency analysis."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_utilization_analysis(path, config, optimizer_solution, demand_values, candidates, hourly_shares):
    """Estimate charger utilization and efficiency metrics."""
    # Get charger specs
    charger_specs = list(config["chargers"].values())
    charger_keys = list(config["chargers"].keys())

    # Station-level demand
    assignments = np.asarray(optimizer_solution.z_assignment, dtype=float)
    station_demand = assignments.T @ np.asarray(demand_values, dtype=float)

    # Peak hour fraction
    peak_hour = int(np.argmax(hourly_shares))
    peak_share = hourly_shares[peak_hour]

    rows = []
    for index in np.flatnonzero(optimizer_solution.x):
        candidate = candidates[index]
        station_kwh_day = station_demand[index]
        station_peak_kwh = station_kwh_day * peak_share

        counts = np.asarray(optimizer_solution.Y[index], dtype=int)
        total_chargers = counts.sum()

        # Calculate total power capacity
        total_power_kw = sum(
            counts[k] * charger_specs[k]["power_kw"]
            for k in range(len(charger_keys))
        )

        # Station utilization
        # Assume 8-hour service window for public charging
        service_hours = 8.0
        total_kwh_day = station_kwh_day
        avg_power_kw = total_kwh_day / service_hours

        # Utilization rate (average power / capacity)
        utilization_avg_pct = 100.0 * avg_power_kw / max(total_power_kw, 1e-12)

        # Capacity factor (daily energy / max possible daily energy)
        # Max possible = 24h * capacity
        max_possible_kwh = total_power_kw * 24.0
        capacity_factor_pct = 100.0 * total_kwh_day / max(max_possible_kwh, 1e-12)

        # Per-charger type analysis
        charger_stats = []
        for k, (charger_key, spec) in enumerate(config["chargers"].items()):
            count = counts[k]
            if count > 0:
                charger_power_kw = spec["power_kw"]
                charger_capacity_kwh = charger_power_kw * 24.0

                # Allocate station demand proportionally
                charger_share = counts[k] * charger_power_kw / max(total_power_kw, 1e-12)
                charger_kwh = total_kwh_day * charger_share

                stats = {
                    "charger_type": charger_key,
                    "count": int(count),
                    "total_power_kw": round(charger_power_kw * count, 1),
                    "daily_energy_kwh": round(charger_kwh, 1),
                    "utilization_pct": round(100.0 * charger_kwh / max(charger_capacity_kwh, 1e-12), 1),
                }
                charger_stats.append(stats)

        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "total_chargers": int(total_chargers),
            "total_power_kw": round(total_power_kw, 1),
            "daily_energy_kwh": round(total_kwh_day, 1),
            "peak_hour_kwh": round(station_peak_kwh, 1),
            "average_power_kw": round(avg_power_kw, 1),
            "utilization_avg_pct": round(utilization_avg_pct, 1),
            "capacity_factor_pct": round(capacity_factor_pct, 1),
            "charger_breakdown_json": str(charger_stats),
        })

    # System-level summary
    total_stations = int(np.count_nonzero(optimizer_solution.x))
    total_chargers = int(np.sum(optimizer_solution.Y))
    total_power_kw = float(sum(
        np.sum(optimizer_solution.Y[:, k]) * charger_specs[k]["power_kw"]
        for k in range(len(charger_keys))
    ))
    total_daily_kwh = float(np.sum(station_demand))

    summary = pd.DataFrame([{
        "metric": "total_stations",
        "value": total_stations,
        "unit": "stations",
    }, {
        "metric": "total_chargers",
        "value": total_chargers,
        "unit": "chargers",
    }, {
        "metric": "total_power_capacity_kw",
        "value": round(total_power_kw, 1),
        "unit": "kW",
    }, {
        "metric": "total_daily_energy_kwh",
        "value": round(total_daily_kwh, 1),
        "unit": "kWh",
    }, {
        "metric": "system_capacity_factor_pct",
        "value": round(100.0 * total_daily_kwh / (total_power_kw * 24.0), 1),
        "unit": "%",
    }])

    frame = pd.DataFrame(rows)
    write_csv(frame, path)
    write_csv(summary, str(path).replace(".csv", "_summary.csv"))

    return path, {
        "total_stations": total_stations,
        "total_chargers": total_chargers,
        "total_power_kw": total_power_kw,
        "daily_energy_kwh": total_daily_kwh,
        "capacity_factor_pct": 100.0 * total_daily_kwh / (total_power_kw * 24.0),
        "peak_hour": peak_hour,
        "peak_share_pct": 100.0 * peak_share,
        "classification": "utilization estimates under assumed service window; not observed data",
    }
