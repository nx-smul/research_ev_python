"""Time-of-day load profile generation."""

from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_HOURLY_SHARES = np.array([
    0.012, 0.009, 0.007, 0.006, 0.007, 0.012,
    0.025, 0.050, 0.070, 0.065, 0.055, 0.050,
    0.048, 0.050, 0.052, 0.055, 0.060, 0.075,
    0.095, 0.090, 0.070, 0.050, 0.030, 0.017,
], dtype=float)


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_time_profiles(path, total_served_kwh_day, settings):
    """Generate assumed hourly load profiles by day type and season."""
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
    return write_csv(pd.DataFrame(rows), path), shares
