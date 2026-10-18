"""Unmet demand and access gap analysis."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_unmet_demand_analysis(path, demand_gdf, demand_values, distances, candidate_metadata, optimizer_solution, config, time_matrix=None):
    """Identify demand zones with poor coverage and access gaps."""
    assignments = np.asarray(optimizer_solution.z_assignment, dtype=float)
    served_fraction = np.clip(assignments.sum(axis=1), 0.0, 1.0)
    served_demand = np.asarray(demand_values, dtype=float) * served_fraction
    unserved_demand = np.asarray(demand_values, dtype=float) * (1.0 - served_fraction)

    # Find which stations each demand point is served by
    assignments_binary = (assignments > 0).astype(float)

    # Calculate minimum distance to any served station for unserved demand
    selected_indices = np.flatnonzero(optimizer_solution.x)

    if len(selected_indices) == 0:
        # No stations selected
        unserved_frame = pd.DataFrame({
            "demand_id": demand_gdf.get("demand_id", [f"DEMAND-{i}" for i in range(len(demand_values))]),
            "demand_kwh_day": demand_values,
            "distance_to_nearest_station_m": np.nan,
            "travel_time_to_nearest_station_min": np.nan,
            "classification": "no stations selected in this scenario",
        })
    else:
        # Calculate min distance for each demand point
        dist_to_selected = distances[:, selected_indices]
        min_distances = np.min(dist_to_selected, axis=1)

        # Find nearest station index
        nearest_stations = selected_indices[np.argmin(dist_to_selected, axis=1)]

        # Calculate travel time if available
        if time_matrix is not None:
            time_to_selected = time_matrix[:, selected_indices]
            min_times = np.min(time_to_selected, axis=1)
        else:
            min_times = np.nan * np.ones(len(demand_values))

        # Identify unserved demand (no assignment within service radius)
        r_max = float(config.get("optimization", {}).get("service_radius_rmax_m", 5000.0))
        is_unserved = served_fraction < 0.5

        # Create gap analysis
        gap_data = []
        demand_ids = demand_gdf.get("demand_id", [f"DEMAND-{i}" for i in range(len(demand_values))])
        zone_names = demand_gdf.get("zone_name", ["Unknown"] * len(demand_values))
        zone_types = demand_gdf.get("zone_type", ["Unknown"] * len(demand_values))

        for i in range(len(demand_values)):
            if is_unserved[i]:
                gap_data.append({
                    "demand_id": str(demand_ids[i]),
                    "zone_name": str(zone_names[i]),
                    "zone_type": str(zone_types[i]),
                    "demand_kwh_day": round(demand_values[i], 1),
                    "distance_to_nearest_station_m": round(min_distances[i], 1),
                    "travel_time_to_nearest_station_min": round(min_times[i], 1) if not np.isnan(min_times[i]) else None,
                    "nearest_station_id": str(candidate_metadata[nearest_stations[i]].get("candidate_id", nearest_stations[i])),
                    "classification": "unserved demand (>50% not assigned to any station)",
                })

        unserved_frame = pd.DataFrame(gap_data)

    write_csv(unserved_frame, path)

    # Summary statistics
    total_demand = float(np.sum(demand_values))
    total_served = float(np.sum(served_demand))
    total_unserved = total_demand - total_served

    # Zone-level gaps
    if "zone_type" in demand_gdf.columns:
        zone_gaps = []
        for zone in demand_gdf["zone_type"].unique():
            zone_demand = np.sum([demand_values[i] for i, z in enumerate(zone_types) if z == zone])
            zone_served = np.sum([served_demand[i] for i, z in enumerate(zone_types) if z == zone])
            zone_unserved = zone_demand - zone_served
            zone_gaps.append({
                "zone_type": zone,
                "total_demand_kwh": round(zone_demand, 1),
                "served_kwh": round(zone_served, 1),
                "unserved_kwh": round(zone_unserved, 1),
                "coverage_pct": round(100.0 * zone_served / max(zone_demand, 1e-12), 1),
            })

    summary = pd.DataFrame([{
        "metric": "total_demand_kwh",
        "value": round(total_demand, 1),
        "unit": "kWh/day",
    }, {
        "metric": "total_served_kwh",
        "value": round(total_served, 1),
        "unit": "kWh/day",
    }, {
        "metric": "total_unserved_kwh",
        "value": round(total_unserved, 1),
        "unit": "kWh/day",
    }, {
        "metric": "overall_coverage_pct",
        "value": round(100.0 * total_served / max(total_demand, 1e-12), 1),
        "unit": "%",
    }, {
        "metric": "unserved_demand_count",
        "value": int(np.sum(is_unserved)),
        "unit": "demand points",
    }])

    write_csv(summary, str(path).replace(".csv", "_summary.csv"))

    return {
        "path": str(path),
        "total_demand_kwh": total_demand,
        "total_served_kwh": total_served,
        "total_unserved_kwh": total_unserved,
        "coverage_pct": 100.0 * total_served / total_demand if total_demand > 0 else 0.0,
        "unserved_count": int(np.sum(is_unserved)),
        "classification": "model-based access gap identification; not empirical measurement",
    }


def write_access_burden_analysis(path, demand_gdf, demand_values, distances, time_matrix, optimizer_solution, config):
    """Analyze travel time/distance burden for users accessing stations."""
    assignments = np.asarray(optimizer_solution.z_assignment, dtype=float)
    assigned_mask = assignments.sum(axis=1) > 0

    # For each assigned demand point, find actual assignment
    n_demand = len(demand_values)
    travel_burdens = []

    for i in range(n_demand):
        if assigned_mask[i]:
            # Find which station this demand is assigned to
            assigned_stations = np.where(assignments[i] > 0)[0]
            if len(assigned_stations) > 0:
                # Take first assignment (or could weight by assignment amount)
                j = assigned_stations[0]

                travel_burdens.append({
                    "demand_id": str(demand_gdf.get("demand_id", [f"DEMAND-{x}" for x in range(n_demand)])[i]),
                    "zone_name": str(demand_gdf.get("zone_name", ["Unknown"] * n_demand)[i]),
                    "distance_to_station_m": round(distances[i, j], 1),
                    "travel_time_minutes": round(time_matrix[i, j], 1),
                })

    frame = pd.DataFrame(travel_burdens)
    write_csv(frame, path)

    # Summary by zone
    zone_summary = frame.groupby("zone_name").agg({
        "distance_to_station_m": ["mean", "median", "min", "max"],
        "travel_time_minutes": ["mean", "median", "min", "max"],
    }).round(1)
    zone_summary.columns = ["_".join(col).strip() for col in zone_summary.columns.values]
    zone_summary = zone_summary.reset_index()

    # Add total demand column
    zone_demand = {}
    zones = demand_gdf.get("zone_name", ["Unknown"] * n_demand)
    for i, z in enumerate(zones):
        zone_demand[z] = zone_demand.get(z, 0) + demand_values[i]

    zone_summary["total_zone_demand_kwh"] = zone_summary["zone_name"].map(zone_demand)

    write_csv(zone_summary, str(path).replace(".csv", "_zone_summary.csv"))

    return {
        "path": str(path),
        "mean_distance_m": float(frame["distance_to_station_m"].mean()) if len(frame) > 0 else 0.0,
        "median_distance_m": float(frame["distance_to_station_m"].median()) if len(frame) > 0 else 0.0,
        "max_distance_m": float(frame["distance_to_station_m"].max()) if len(frame) > 0 else 0.0,
        "mean_travel_time_min": float(frame["travel_time_minutes"].mean()) if len(frame) > 0 else 0.0,
        "classification": "modeled travel burden under assumed demand-station assignment",
    }
