"""M/M/c queueing analysis for station operations screening."""

import math
from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
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


def write_queue_screen(path, candidates, solution, demand, shares, config, settings):
    """Estimate peak wait times using M/M/c queueing model."""
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
    return write_csv(pd.DataFrame(rows), path)
