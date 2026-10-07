"""Spatial filtering, buffer analysis, and constraint exclusion for candidate EVCS site selection."""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPolygon, Polygon


class SpatialFilter:
    """Handles spatial constraint evaluation and buffer operations for Dhaka."""

    def __init__(self, config=None):
        self.config = config or {}
        self.waterbody_buffer_m = self.config.get("spatial", {}).get("exclusion_buffers", {}).get("waterbodies_m", 30.0)
        self.heritage_buffer_m = self.config.get("spatial", {}).get("exclusion_buffers", {}).get("heritage_sites_m", 50.0)
        self.min_spacing_m = self.config.get("spatial", {}).get("candidate_site_generation", {}).get("min_spacing_m", 300.0)
        self.min_suitability = self.config.get("spatial", {}).get("candidate_site_generation", {}).get("min_suitability_score", 0.40)

    def apply_exclusion_masks(self, candidate_gdf, landuse_gdf=None):
        """Apply boolean exclusion constraints C_m(x, y) in {0, 1}.

        Args:
            candidate_gdf (gpd.GeoDataFrame): Candidate site points.
            landuse_gdf (gpd.GeoDataFrame, optional): RAJUK land use zoning layer.

        Returns:
            gpd.GeoDataFrame: Filtered candidate sites passing all exclusion constraints.
        """
        if candidate_gdf.empty:
            return candidate_gdf

        gdf = candidate_gdf.copy()

        # Ensure spatial CRS is set
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

        # 1. Attribute-based exclusion filtering
        if "is_flood_safe" in gdf.columns:
            gdf = gdf[gdf["is_flood_safe"] == True]

        if "ahp_suitability_score" in gdf.columns:
            gdf = gdf[gdf["ahp_suitability_score"] >= self.min_suitability]

        # 2. Geometric overlay with landuse polygons if provided
        if landuse_gdf is not None and not landuse_gdf.empty:
            if landuse_gdf.crs is None:
                landuse_gdf = landuse_gdf.set_crs("EPSG:4326")

            # Identify exclusion polygons (Waterbodies, Protected heritage, Flood hazard)
            excl_poly = landuse_gdf[
                (landuse_gdf["is_exclusion_zone"] == 1) |
                (landuse_gdf["zone_type"].isin(["Waterbody", "Flood_Hazard", "Heritage"]))
            ]

            if not excl_poly.empty:
                # Spatial join to find intersecting candidate points
                disallowed_indices = []
                for _, poly_row in excl_poly.iterrows():
                    intersecting = gdf[gdf.geometry.intersects(poly_row.geometry)]
                    disallowed_indices.extend(intersecting.index.tolist())

                disallowed_set = set(disallowed_indices)
                gdf = gdf[~gdf.index.isin(disallowed_set)]

        # 3. Minimum spatial spacing suppression (Spatial Non-Maximum Suppression)
        gdf = self.apply_spatial_spacing(gdf, min_distance_m=self.min_spacing_m)

        return gdf.reset_index(drop=True)

    def apply_spatial_spacing(self, gdf, min_distance_m=300.0):
        """Ensure candidate EVCS sites are spaced at least min_distance_m apart.
        Prefers sites with higher AHP suitability scores.
        """
        if len(gdf) <= 1:
            return gdf

        # Sort by suitability score descending
        sort_col = "ahp_suitability_score" if "ahp_suitability_score" in gdf.columns else "traffic_density_score"
        if sort_col in gdf.columns:
            sorted_gdf = gdf.sort_values(by=sort_col, ascending=False).copy()
        else:
            sorted_gdf = gdf.copy()

        # Convert to projected coordinates for accurate metric distance calculation
        gdf_proj = sorted_gdf.to_crs("EPSG:32646") if sorted_gdf.crs != "EPSG:32646" else sorted_gdf

        selected_indices = []
        selected_points = []

        for idx, row in gdf_proj.iterrows():
            pt = row.geometry
            if not selected_points:
                selected_points.append(pt)
                selected_indices.append(idx)
            else:
                # Check distance to all already selected points
                min_dist = min(pt.distance(p) for p in selected_points)
                if min_dist >= min_distance_m:
                    selected_points.append(pt)
                    selected_indices.append(idx)

        return sorted_gdf.loc[selected_indices]


def filter_candidate_sites(raw_sites_gdf, landuse_gdf=None, config=None):
    """Filter raw candidate sites according to exclusion criteria and spatial spacing."""
    s_filter = SpatialFilter(config)
    return s_filter.apply_exclusion_masks(raw_sites_gdf, landuse_gdf)
