"""Stage 3 — OSM road graph and OD travel-time matrix."""

import os

import geopandas as gpd
import numpy as np

from src.spatial.osm_network import OSMRoadNetwork, compute_od_matrices


def compute_road_network(base_dir, candidate_gdf):
    """Build OD matrices and candidate-pair road distances."""
    demand_geojson_path = os.path.join(base_dir, "data", "processed", "demand_grid_100m.geojson")
    candidate_geojson_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
    roads_geojson_path = os.path.join(base_dir, "data", "raw", "osm_dhaka_roads.geojson")
    od_npz_path = os.path.join(base_dir, "data", "processed", "od_travel_time_matrix.npz")
    candidate_road_distances_path = os.path.join(base_dir, "results", "tables", "candidate_road_distances.csv")

    compute_od_matrices(
        demand_geojson_path, candidate_geojson_path, roads_geojson_path, od_npz_path,
        allow_approximate_fallback=False,
    )
    road_network = OSMRoadNetwork(roads_geojson_path)
    candidate_road_distances = road_network.calculate_candidate_road_distances(candidate_gdf)
    candidate_road_distances.to_csv(candidate_road_distances_path, index=False)

    data = np.load(od_npz_path)
    dist_matrix = data["distances"]
    time_matrix = data["travel_times"]
    demand_values = data["demand_values"]
    routing_method = str(data["routing_method"].item()) if "routing_method" in data else "legacy_unspecified"
    if routing_method != "directed_road_network_dijkstra":
        raise ValueError(
            "The optimization OD matrix must use directed road-network routes; "
            f"found routing method '{routing_method}'. Rebuild it from the current road graph."
        )

    demand_gdf = gpd.read_file(demand_geojson_path)
    candidate_ids = candidate_gdf["candidate_id"].astype(str).tolist()
    demand_ids = demand_gdf["demand_id"].astype(str).tolist()
    if "candidate_ids" in data and data["candidate_ids"].astype(str).tolist() != candidate_ids:
        raise ValueError("OD matrix candidate_ids do not match candidate-site input order.")
    if "demand_ids" in data and data["demand_ids"].astype(str).tolist() != demand_ids:
        raise ValueError("OD matrix demand_ids do not match demand input order.")
    if dist_matrix.shape != (len(demand_ids), len(candidate_ids)) or time_matrix.shape != dist_matrix.shape:
        raise ValueError("OD matrix dimensions do not match demand and candidate inputs.")
    if not np.isfinite(dist_matrix).all() or not np.isfinite(time_matrix).all() or (dist_matrix < 0).any() or (time_matrix < 0).any():
        raise ValueError("OD matrices must contain finite non-negative distance and travel-time values.")
    if len(demand_values) != len(demand_ids) or not np.isfinite(demand_values).all() or (demand_values <= 0).any():
        raise ValueError("OD demand values must be finite, positive, and aligned with demand input rows.")

    candidate_metadata = candidate_gdf.to_dict(orient="records")

    return {
        "dist_matrix": dist_matrix,
        "time_matrix": time_matrix,
        "demand_values": demand_values,
        "demand_gdf": demand_gdf,
        "candidate_ids": candidate_ids,
        "demand_ids": demand_ids,
        "candidate_metadata": candidate_metadata,
        "routing_method": routing_method,
        "road_network": road_network,
        "candidate_road_distances": candidate_road_distances,
        "od_npz_path": od_npz_path,
        "candidate_road_distances_path": candidate_road_distances_path,
    }

