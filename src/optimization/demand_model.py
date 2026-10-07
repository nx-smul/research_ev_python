"""Heterogeneous vehicle fleet demand estimation and spatial distribution across Dhaka."""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


class DhakaEVDemandModel:
    """Models multi-modal EV charging demand across Dhaka City Corporation zones."""

    def __init__(self, config):
        self.config = config
        self.fleet_config = config.get("fleet", {})

    def calculate_vehicle_daily_energy(self, v_type):
        """Calculate daily energy demand per vehicle in kWh."""
        spec = self.fleet_config.get(v_type, {})
        daily_km = spec.get("daily_km", 40.0)
        kwh_per_km = spec.get("kwh_per_km", 0.15)
        return daily_km * kwh_per_km

    def calculate_total_city_demand(self):
        """Calculate aggregated daily city-wide energy demand by vehicle category in kWh/day."""
        summary = {}
        total_kwh = 0.0

        for v_type, spec in self.fleet_config.items():
            count = spec.get("count", 1000)
            energy_per_veh = self.calculate_vehicle_daily_energy(v_type)
            cat_total = count * energy_per_veh
            summary[v_type] = {
                "count": count,
                "daily_kwh_per_veh": round(energy_per_veh, 2),
                "total_daily_mwh": round(cat_total / 1000.0, 2),
                "fast_charge_mwh": round((cat_total * spec.get("fast_charge_share", 0.5)) / 1000.0, 2),
                "swap_mwh": round((cat_total * spec.get("swap_share", 0.0)) / 1000.0, 2),
                "ac_mwh": round((cat_total * spec.get("ac_share", 0.5)) / 1000.0, 2)
            }
            total_kwh += cat_total

        summary["total_city_daily_mwh"] = round(total_kwh / 1000.0, 2)
        return summary

    def distribute_demand_spatially(self, demand_centroids_gdf):
        """Disaggregate city-wide fleet demand onto spatial 100m grid centroids based on zone weights."""
        gdf = demand_centroids_gdf.copy()
        n_zones = len(gdf)

        # Spatial weighting based on land use and commercial intensity
        weights = []
        for _, row in gdf.iterrows():
            ztype = row.get("zone_type", "Residential")
            if ztype in ["Commercial", "CBD"]:
                w = 2.4
            elif ztype in ["Transport_Hub", "Highway"]:
                w = 3.0
            elif ztype in ["Industrial", "Mixed"]:
                w = 1.6
            else:
                w = 1.0
            weights.append(w)

        weights = np.array(weights)
        norm_weights = weights / np.sum(weights)

        city_totals = self.calculate_total_city_demand()
        total_mwh = city_totals["total_city_daily_mwh"]

        gdf["spatial_weight"] = norm_weights.round(5)
        gdf["daily_demand_kwh"] = (norm_weights * total_mwh * 1000.0).round(1)

        return gdf
