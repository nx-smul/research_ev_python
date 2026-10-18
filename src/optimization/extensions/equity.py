"""Spatial equity and accessibility analysis by zone."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_equity_accessibility(path, demand_gdf, demand, distances, solution):
    """Compute spatial access proxy by zone (not socioeconomic equity)."""
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
    return write_csv(grouped, path)
