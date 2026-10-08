"""Road network graph construction, congestion indexing, and Origin-Destination (OD) matrix generation."""

import argparse
import os
import math
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point


class OSMRoadNetwork:
    """Represents the Dhaka metropolitan road graph with congestion travel time modeling."""

    def __init__(self, roads_geojson_path=None):
        self.graph = nx.Graph()
        self.roads_gdf = None
        if roads_geojson_path and os.path.exists(roads_geojson_path):
            self.load_from_geojson(roads_geojson_path)

    def load_from_geojson(self, geojson_path):
        """Build NetworkX graph from road network GeoJSON."""
        self.roads_gdf = gpd.read_file(geojson_path)
        if self.roads_gdf.empty:
            raise ValueError("Road network input is empty.")
        if self.roads_gdf.crs is None or self.roads_gdf.crs.to_epsg() != 4326:
            raise ValueError("Road network geometry must declare CRS EPSG:4326 (longitude/latitude).")

        for idx, row in self.roads_gdf.iterrows():
            u = row.get("u", f"node_{idx}_u")
            v = row.get("v", f"node_{idx}_v")
            required = ("length_m", "maxspeed", "lanes", "pcu_per_hr")
            missing = [field for field in required if field not in self.roads_gdf.columns or pd.isna(row.get(field))]
            if missing:
                raise ValueError(
                    f"Road feature {idx} is missing required sourced attributes: {', '.join(missing)}."
                )
            length_m = float(row["length_m"])
            speed_kmh = float(row["maxspeed"])
            lanes = int(row["lanes"])
            pcu = float(row["pcu_per_hr"])
            if length_m <= 0 or speed_kmh <= 0 or lanes <= 0 or pcu < 0:
                raise ValueError(f"Road feature {idx} contains invalid routing attributes.")

            # Bureau of Public Roads (BPR) congestion formula: t = t0 * (1 + alpha * (V/C)^beta)
            capacity = lanes * 1200.0  # PCU/hr per lane
            t0_minutes = (length_m / 1000.0) / speed_kmh * 60.0
            vc_ratio = pcu / capacity
            congestion_mult = 1.0 + 0.15 * (vc_ratio ** 4.0)
            t_congested_minutes = t0_minutes * congestion_mult

            # Extract coordinates from LineString geometry
            if row.geometry is None or row.geometry.is_empty or not hasattr(row.geometry, "coords"):
                raise ValueError(f"Road feature {idx} must have a non-empty LineString geometry.")
            coords = list(row.geometry.coords)
            u_coord = coords[0]
            v_coord = coords[-1]

            if not self.graph.has_node(u):
                self.graph.add_node(u, pos=u_coord, lon=u_coord[0], lat=u_coord[1])
            if not self.graph.has_node(v):
                self.graph.add_node(v, pos=v_coord, lon=v_coord[0], lat=v_coord[1])

            self.graph.add_edge(
                u, v,
                length_m=length_m,
                free_flow_time_min=t0_minutes,
                weight=t_congested_minutes,  # Travel time in minutes
                lanes=lanes,
                pcu=pcu,
                congestion_mult=congestion_mult
            )

    def find_nearest_node(self, lon, lat):
        """Find the closest road graph node to given coordinate."""
        best_node = None
        min_dist_sq = float("inf")

        for node, data in self.graph.nodes(data=True):
            n_lon = data.get("lon", 90.40)
            n_lat = data.get("lat", 23.75)
            dist_sq = (n_lon - lon)**2 + (n_lat - lat)**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                best_node = node

        return best_node

    def calculate_shortest_path_matrix(self, demand_points, candidate_points, weight="weight", allow_approximate_fallback=True):
        """Calculate OD travel time and network distance matrices using Dijkstra's algorithm.

        Args:
            demand_points (list of (lon, lat)): Coordinates of demand zones.
            candidate_points (list of (lon, lat)): Coordinates of candidate EVCS.
            weight (str): Edge attribute for routing ('weight' for time, 'length_m' for distance).

        Returns:
            tuple: (distance_matrix_m, travel_time_matrix_min)
        """
        n_demand = len(demand_points)
        n_candidate = len(candidate_points)

        dist_matrix = np.zeros((n_demand, n_candidate), dtype=np.float32)
        time_matrix = np.zeros((n_demand, n_candidate), dtype=np.float32)

        # Map points to nearest graph nodes
        demand_nodes = [self.find_nearest_node(p[0], p[1]) for p in demand_points]
        candidate_nodes = [self.find_nearest_node(p[0], p[1]) for p in candidate_points]

        for i, (d_pt, d_node) in enumerate(zip(demand_points, demand_nodes)):
            for j, (c_pt, c_node) in enumerate(zip(candidate_points, candidate_nodes)):
                if d_node is not None and c_node is not None and nx.has_path(self.graph, d_node, c_node):
                    try:
                        t_min = nx.shortest_path_length(self.graph, d_node, c_node, weight="weight")
                        d_m = nx.shortest_path_length(self.graph, d_node, c_node, weight="length_m")
                    except nx.NetworkXNoPath:
                        if not allow_approximate_fallback:
                            raise ValueError(
                                "Road-network route unavailable for demand/candidate pair "
                                f"({i}, {j}); Euclidean fallback is disabled for verified-data runs."
                            )
                        t_min, d_m = self._euclidean_fallback(d_pt, c_pt)
                else:
                    if not allow_approximate_fallback:
                        raise ValueError(
                            "Road-network route unavailable for demand/candidate pair "
                            f"({i}, {j}); Euclidean fallback is disabled for verified-data runs."
                        )
                    t_min, d_m = self._euclidean_fallback(d_pt, c_pt)

                dist_matrix[i, j] = d_m
                time_matrix[i, j] = t_min

        return dist_matrix, time_matrix

    def _euclidean_fallback(self, p1, p2):
        """Haversine distance and travel time approximation."""
        d_lat = math.radians(p2[1] - p1[1])
        d_lon = math.radians(p2[0] - p1[0])
        a = math.sin(d_lat/2)**2 + math.cos(math.radians(p1[1])) * math.cos(math.radians(p2[1])) * math.sin(d_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        dist_m = 6371000.0 * c * 1.30  # Network circuity multiplier
        time_min = (dist_m / 1000.0) / 18.0 * 60.0  # 18 km/h urban speed in Dhaka
        return time_min, dist_m


def compute_od_matrices(demand_geojson_path, candidate_geojson_path, roads_geojson_path, output_npz_path, allow_approximate_fallback=True):
    """Compute and save OD distance and travel time matrices to .npz file."""
    demand_gdf = gpd.read_file(demand_geojson_path)
    candidate_gdf = gpd.read_file(candidate_geojson_path)

    demand_points = [(geom.x, geom.y) for geom in demand_gdf.geometry]
    candidate_points = [(geom.x, geom.y) for geom in candidate_gdf.geometry]

    demand_ids = demand_gdf["demand_id"].tolist() if "demand_id" in demand_gdf.columns else [f"D_{i}" for i in range(len(demand_gdf))]
    candidate_ids = candidate_gdf["candidate_id"].tolist() if "candidate_id" in candidate_gdf.columns else [f"CS_{j}" for j in range(len(candidate_gdf))]
    if "daily_demand_kwh" not in demand_gdf.columns:
        raise ValueError("Demand input must contain measured or explicitly sourced 'daily_demand_kwh'; no default demand is substituted.")
    demand_values = demand_gdf["daily_demand_kwh"].to_numpy()

    network = OSMRoadNetwork(roads_geojson_path)
    if not network.graph:
        raise ValueError("Road network is empty; provide a valid road GeoJSON with routable edges.")
    dist_mat, time_mat = network.calculate_shortest_path_matrix(
        demand_points, candidate_points,
        allow_approximate_fallback=allow_approximate_fallback,
    )

    os.makedirs(os.path.dirname(output_npz_path), exist_ok=True)
    np.savez_compressed(
        output_npz_path,
        distances=dist_mat,
        travel_times=time_mat,
        demand_ids=np.array(demand_ids),
        candidate_ids=np.array(candidate_ids),
        demand_values=np.array(demand_values)
    )

    print(f"[OSM Network] Computed OD matrices ({len(demand_ids)} demand zones x {len(candidate_ids)} candidate sites).")
    print(f"[OSM Network] Output saved to: {output_npz_path}")

    return dist_mat, time_mat


def main():
    parser = argparse.ArgumentParser(description="Extract road network and calculate OD travel time matrix for Dhaka.")
    parser.add_argument("--city", type=str, default="Dhaka, Bangladesh", help="City name (input files are local; this flag does not download data).")
    parser.add_argument("--matrix-output", type=str, default="data/processed/od_travel_time_matrix.npz", help="Output path for OD matrix NPZ file.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    demand_path = os.path.join(base_dir, "data", "processed", "demand_grid_100m.geojson")
    candidate_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")
    roads_path = os.path.join(base_dir, "data", "raw", "osm_dhaka_roads.geojson")

    if not (os.path.exists(demand_path) and os.path.exists(candidate_path) and os.path.exists(roads_path)):
        parser.error("Required data files are missing; obtain public inputs or generate demo data explicitly with `python main.py --mode data`. No data was generated automatically.")

    output_path = os.path.join(base_dir, args.matrix_output) if not os.path.isabs(args.matrix_output) else args.matrix_output
    compute_od_matrices(demand_path, candidate_path, roads_path, output_path, allow_approximate_fallback=False)


if __name__ == "__main__":
    main()
