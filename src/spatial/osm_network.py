"""Road network graph construction, congestion indexing, and Origin-Destination (OD) matrix generation."""

import argparse
import os
import math
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
import httpx
from shapely.geometry import Point


class OSMRoadNetwork:
    """Represents the Dhaka metropolitan road graph with congestion travel time modeling."""

    def __init__(self, roads_geojson_path=None):
        self.graph = nx.DiGraph()
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

            edge_data = dict(
                length_m=length_m,
                free_flow_time_min=t0_minutes,
                weight=t_congested_minutes,  # Travel time in minutes
                lanes=lanes,
                pcu=pcu,
                congestion_mult=congestion_mult
            )
            oneway = str(row.get("oneway", "")).strip().lower()
            if oneway in {"-1", "reverse"}:
                self.graph.add_edge(v, u, **edge_data)
            else:
                self.graph.add_edge(u, v, **edge_data)
                if oneway not in {"yes", "true", "1"}:
                    self.graph.add_edge(v, u, **edge_data)

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

    def calculate_candidate_road_distances(self, candidate_gdf):
        """Return one shortest directed road-distance record per ordered site pair."""
        required = {"candidate_id", "geometry"}
        missing = required - set(candidate_gdf.columns)
        if missing:
            raise ValueError(f"Candidate input is missing required fields: {', '.join(sorted(missing))}.")
        if candidate_gdf["candidate_id"].isna().any() or candidate_gdf["candidate_id"].astype(str).duplicated().any():
            raise ValueError("Candidate IDs must be non-empty and unique for pairwise road distances.")

        candidates = []
        for _, row in candidate_gdf.iterrows():
            geometry = row.geometry
            if geometry is None or geometry.is_empty or geometry.geom_type != "Point":
                raise ValueError(f"Candidate '{row['candidate_id']}' must have a non-empty Point geometry.")
            node = self.find_nearest_node(geometry.x, geometry.y)
            if node is None:
                raise ValueError("Cannot calculate candidate road distances because the road graph has no nodes.")
            node_data = self.graph.nodes[node]
            snap_distance = self._haversine_distance_m(
                (geometry.x, geometry.y), (node_data["lon"], node_data["lat"])
            )
            candidates.append({
                "candidate_id": str(row["candidate_id"]),
                "site_name": row.get("site_name", ""),
                "from_node": node,
                "snap_distance_m": snap_distance,
            })

        records = []
        for i, origin in enumerate(candidates):
            distances = nx.single_source_dijkstra_path_length(
                self.graph, origin["from_node"], weight="length_m"
            )
            for destination_index, destination in enumerate(candidates):
                if i == destination_index:
                    continue
                road_distance = distances.get(destination["from_node"])
                if road_distance is None:
                    status = "no_road_route"
                elif origin["from_node"] == destination["from_node"]:
                    status = "same_road_node"
                else:
                    status = "routed"
                records.append({
                    "from_candidate_id": origin["candidate_id"],
                    "from_site_name": origin["site_name"],
                    "to_candidate_id": destination["candidate_id"],
                    "to_site_name": destination["site_name"],
                    "road_distance_m": road_distance,
                    "from_road_snap_distance_m": origin["snap_distance_m"],
                    "to_road_snap_distance_m": destination["snap_distance_m"],
                    "from_road_node": origin["from_node"],
                    "to_road_node": destination["from_node"],
                    "route_status": status,
                })
        return pd.DataFrame.from_records(records)

    def calculate_shortest_path_matrix(self, demand_points, candidate_points, weight="weight", allow_approximate_fallback=False):
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
        dist_m = self._haversine_distance_m(p1, p2) * 1.30  # Network circuity multiplier
        time_min = (dist_m / 1000.0) / 18.0 * 60.0  # 18 km/h urban speed in Dhaka
        return time_min, dist_m

    @staticmethod
    def _haversine_distance_m(p1, p2):
        d_lat = math.radians(p2[1] - p1[1])
        d_lon = math.radians(p2[0] - p1[0])
        a = math.sin(d_lat/2)**2 + math.cos(math.radians(p1[1])) * math.cos(math.radians(p2[1])) * math.sin(d_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return 6371000.0 * c


def _parse_osm_speed(tags, road_class):
    value = str(tags.get("maxspeed", "")).strip().lower()
    match = re.search(r"\d+(?:\.\d+)?", value)
    if match:
        speed = float(match.group())
        return (speed * 1.609344 if "mph" in value else speed), "osm:maxspeed"
    defaults = {
        "motorway": 80, "trunk": 60, "primary": 45, "secondary": 35,
        "tertiary": 30, "residential": 25, "unclassified": 20, "service": 15,
    }
    return float(defaults.get(road_class, 20)), f"assumed:default_for_{road_class}"


def _parse_osm_lanes(tags, road_class):
    value = str(tags.get("lanes", "")).strip()
    match = re.search(r"\d+", value)
    if match and int(match.group()) > 0:
        return int(match.group()), "osm:lanes"
    defaults = {"motorway": 3, "trunk": 2, "primary": 2}
    return defaults.get(road_class, 1), f"assumed:default_for_{road_class}"


def download_osm_road_network(
    bbox,
    output_path,
    *,
    overpass_url="https://overpass-api.de/api/interpreter",
    timeout_seconds=90,
    client_factory=None,
):
    """Download routable OSM ways and save a directed, provenance-tagged edge graph.

    OSM geometry and way/node identifiers are sourced; absent traffic flow, speed,
    and lane values are estimated and explicitly labeled as assumptions.
    """
    south, west, north, east = map(float, bbox)
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("bbox must be (south, west, north, east) in valid geographic bounds.")
    bounds = f"{south},{west},{north},{east}"
    query = (
        "[out:json][timeout:60];"
        f'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|road|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]'
        f'({bounds})["access"!~"^(no|private)$"];out body geom;'
    )
    factory = client_factory or httpx.Client
    try:
        with factory(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": "DhakaEVCSResearch/1.0 (+https://github.com/nx-smul/research_ev_python)"},
        ) as client:
            response = client.post(overpass_url, data={"data": query})
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError("OpenStreetMap Overpass road download timed out; retry later.") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"OpenStreetMap Overpass returned HTTP {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("OpenStreetMap Overpass road service is unavailable.") from exc

    try:
        elements = response.json()["elements"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("OpenStreetMap Overpass returned an invalid road response.") from exc
    if not isinstance(elements, list):
        raise RuntimeError("OpenStreetMap Overpass returned an invalid road element list.")

    excluded = {"footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "construction"}
    features = []
    skipped = 0
    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "way":
            skipped += 1
            continue
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        highway = str(tags.get("highway", ""))
        nodes = element.get("nodes")
        geometry = element.get("geometry")
        if highway in excluded or not isinstance(nodes, list) or not isinstance(geometry, list) or len(nodes) != len(geometry):
            skipped += 1
            continue
        try:
            osm_id = int(element["id"])
            node_ids = [int(node_id) for node_id in nodes]
            points = [(float(point["lon"]), float(point["lat"])) for point in geometry]
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        if len(points) < 2 or any(
            not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in points
        ):
            skipped += 1
            continue
        speed, speed_source = _parse_osm_speed(tags, highway)
        lanes, lanes_source = _parse_osm_lanes(tags, highway)
        # OSM has no citywide flow observation here; keep this capacity-scaled proxy explicit.
        pcu_per_lane = {
            "motorway": 650, "motorway_link": 450, "trunk": 550, "trunk_link": 400,
            "primary": 400, "primary_link": 300, "secondary": 300,
            "secondary_link": 250, "tertiary": 220, "tertiary_link": 180,
            "residential": 140, "living_street": 80, "service": 60,
        }.get(highway, 100)
        traffic = tags.get("pcu_per_hr")
        try:
            pcu_per_hr = float(traffic) if traffic is not None else float(lanes * pcu_per_lane)
            traffic_source = "osm:pcu_per_hr" if traffic is not None else f"assumed:road_class_proxy_{highway}"
        except (TypeError, ValueError):
            pcu_per_hr = float(lanes * pcu_per_lane)
            traffic_source = f"assumed:road_class_proxy_{highway}"
        oneway = str(tags.get("oneway", "")).strip().lower()
        if oneway not in {"yes", "true", "1", "-1", "no", "false", "0"}:
            oneway = "no"

        for segment_index, (start, end) in enumerate(zip(points, points[1:])):
            segment_length = OSMRoadNetwork._haversine_distance_m(start, end)
            if segment_length <= 0:
                continue
            start_node = f"osm:{node_ids[segment_index]}"
            end_node = f"osm:{node_ids[segment_index + 1]}"
            features.append({
                "type": "Feature",
                "id": f"way/{osm_id}/{segment_index}",
                "properties": {
                    "u": start_node,
                    "v": end_node,
                    "osm_way_id": osm_id,
                    "highway": highway,
                    "name": str(tags.get("name", "")),
                    "oneway": oneway,
                    "length_m": round(segment_length, 2),
                    "maxspeed": speed,
                    "maxspeed_source": speed_source,
                    "lanes": lanes,
                    "lanes_source": lanes_source,
                    "pcu_per_hr": pcu_per_hr,
                    "pcu_source": traffic_source,
                    "data_class": "OSM geometry; traffic/speed/lane assumptions explicitly labeled",
                },
                "geometry": {"type": "LineString", "coordinates": [start, end]},
            })
    if not features:
        raise RuntimeError("OpenStreetMap Overpass returned no usable routable road segments.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    collection = {
        "type": "FeatureCollection",
        "name": "openstreetmap_dhaka_routable_roads",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.write_text(json.dumps(collection, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary_path.replace(output_path)
    provenance = {
        "source_url": overpass_url,
        "license": "OpenStreetMap ODbL 1.0; attribution required",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "coverage": f"Bounding box south={south}, west={west}, north={north}, east={east}",
        "units": "WGS84 coordinates; segment length meters; speed km/h; traffic PCU/hour",
        "transformation": (
            "OSM highway ways split at OSM node IDs; oneway direction retained. "
            "Missing speed and lanes use tagged road-class assumptions; missing traffic "
            "flow uses a road-class/lane proxy, never observed traffic."
        ),
        "data_class": "derived_from_observed",
        "feature_count": str(len(features)),
        "skipped_way_count": str(skipped),
    }
    provenance_path = output_path.with_suffix(output_path.suffix + ".provenance.json")
    temporary_provenance = provenance_path.with_name(f".{provenance_path.name}.tmp")
    temporary_provenance.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    temporary_provenance.replace(provenance_path)
    return {"output_path": str(output_path), "provenance_path": str(provenance_path), **provenance}


def compute_od_matrices(demand_geojson_path, candidate_geojson_path, roads_geojson_path, output_npz_path, allow_approximate_fallback=False):
    """Compute OD matrices from shortest road routes; approximation is explicit opt-in."""
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
        demand_values=np.array(demand_values),
        routing_method=np.array(
            "directed_road_network_dijkstra"
            if not allow_approximate_fallback
            else "road_network_with_euclidean_fallback"
        ),
    )

    print(f"[OSM Network] Computed OD matrices ({len(demand_ids)} demand zones x {len(candidate_ids)} candidate sites).")
    print(f"[OSM Network] Output saved to: {output_npz_path}")

    return dist_mat, time_mat


def main():
    parser = argparse.ArgumentParser(description="Extract road network and calculate OD travel time matrix for Dhaka.")
    parser.add_argument("--city", type=str, default="Dhaka, Bangladesh", help="City name (input files are local; this flag does not download data).")
    parser.add_argument("--matrix-output", type=str, default="data/processed/od_travel_time_matrix.npz", help="Output path for OD matrix NPZ file.")
    parser.add_argument("--download-roads", action="store_true", help="Download OSM driveable roads and provenance metadata, then exit.")
    parser.add_argument("--bbox", type=str, default=None, help="Road-download bounds: south,west,north,east (overrides spatial.bounding_box in default_config.yaml).")
    parser.add_argument("--overpass-url", type=str, default="https://overpass-api.de/api/interpreter", help="Overpass API endpoint for --download-roads.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing road GeoJSON/provenance files when downloading.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    roads_path = os.path.join(base_dir, "data", "raw", "osm_dhaka_roads.geojson")
    if args.download_roads:
        provenance_path = roads_path + ".provenance.json"
        if (os.path.exists(roads_path) or os.path.exists(provenance_path)) and not args.overwrite:
            parser.error(
                f"Refusing to replace existing road or provenance files at {roads_path}; "
                "pass --overwrite explicitly."
            )
        if args.bbox:
            try:
                bbox = tuple(float(part.strip()) for part in args.bbox.split(","))
                if len(bbox) != 4:
                    raise ValueError
            except ValueError:
                parser.error("--bbox must contain four comma-separated numbers: south,west,north,east.")
        else:
            from src.config import load_config

            config = load_config(os.path.join(base_dir, "configs", "default_config.yaml"))
            box = config["spatial"]["bounding_box"]
            bbox = (box["min_lat"], box["min_lon"], box["max_lat"], box["max_lon"])
        try:
            result = download_osm_road_network(bbox, roads_path, overpass_url=args.overpass_url)
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Downloaded {result['feature_count']} OSM road segments to {result['output_path']}.")
        print(f"Provenance: {result['provenance_path']}. Traffic/speed/lane proxies are explicitly tagged as assumptions.")
        return
    demand_path = os.path.join(base_dir, "data", "processed", "demand_grid_100m.geojson")
    candidate_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")

    if not (os.path.exists(demand_path) and os.path.exists(candidate_path) and os.path.exists(roads_path)):
        parser.error("Required data files are missing; obtain public inputs or generate demo data explicitly with `python main.py --mode data`. No data was generated automatically.")

    output_path = os.path.join(base_dir, args.matrix_output) if not os.path.isabs(args.matrix_output) else args.matrix_output
    compute_od_matrices(demand_path, candidate_path, roads_path, output_path)


if __name__ == "__main__":
    main()
