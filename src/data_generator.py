"""Generate synthetic demonstration datasets; never treat these as observations."""

import json
import os
import csv
import math
import yaml
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import pandapower as pp
import pandapower.networks as nw
from scipy.spatial.distance import cdist

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_auxiliary_data(raw_dir: Path):
    anchors_path = raw_dir / "dhaka_anchors.yaml"
    substations_path = raw_dir / "substations.yaml"
    if not anchors_path.exists() or not substations_path.exists():
        default_raw = Path(__file__).resolve().parent.parent / "data" / "raw"
        if not anchors_path.exists():
            anchors_path = default_raw / "dhaka_anchors.yaml"
        if not substations_path.exists():
            substations_path = default_raw / "substations.yaml"

    with open(anchors_path, "r") as f:
        city_anchors = yaml.safe_load(f)
    with open(substations_path, "r") as f:
        city_stations = yaml.safe_load(f)
    return city_anchors, city_stations


def _process_substations(city_stations: list, raw_dir: Path):
    sub_df = pd.DataFrame(city_stations)
    sub_df["headroom_mva"] = (sub_df["rated_mva"] - sub_df["base_load_mva"]).round(2)
    sub_df["headroom_pct"] = ((sub_df["headroom_mva"] / sub_df["rated_mva"]) * 100).round(2)
    sub_df.to_csv(raw_dir / "dpdc_desco_substations.csv", index=False)
    logger.info("Processed substation data saved.")


def _generate_road_features(city_anchors: dict, raw_dir: Path, road_edges: list):
    road_features = []
    for u, v, rtype, spd, lanes, pcu in road_edges:
        p1 = city_anchors[u]
        p2 = city_anchors[v]
        geom = LineString([(p1[0], p1[1]), (p2[0], p2[1])])
        d_lat = math.radians(p2[1] - p1[1])
        d_lon = math.radians(p2[0] - p1[0])
        a = math.sin(d_lat/2)**2 + math.cos(math.radians(p1[1])) * math.cos(math.radians(p2[1])) * math.sin(d_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        length_m = 6371000.0 * c
        road_features.append({
            "type": "Feature",
            "properties": {
                "u": u, "v": v, "highway": rtype, "maxspeed": spd, "lanes": lanes,
                "length_m": round(length_m, 1), "pcu_per_hr": pcu,
                "congestion_factor": round(1.0 + 0.15 * ((pcu / (lanes * 1000)) ** 4), 2)
            },
            "geometry": geom.__geo_interface__
        })
    with open(raw_dir / "osm_dhaka_roads.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "name": "osm_dhaka_roads", "features": road_features}, f, indent=2)
    logger.info("Road features generated and saved.")


def _generate_traffic_counts(city_anchors: dict, raw_dir: Path, road_edges: list):
    traffic_rows = []
    for idx, (u, v, rtype, spd, lanes, pcu) in enumerate(road_edges):
        p1 = city_anchors[u]; p2 = city_anchors[v]
        traffic_rows.append({
            "junction_id": f"DTCA-JUNC-{idx+1:03d}",
            "corridor_name": f"{u} to {v}",
            "lon": round((p1[0] + p2[0])/2, 5), "lat": round((p1[1] + p2[1])/2, 5),
            "peak_pcu_per_hr": pcu, "offpeak_pcu_per_hr": int(pcu * 0.45),
            "commercial_pct": round(np.random.uniform(15.0, 35.0), 1),
            "two_wheeler_pct": round(np.random.uniform(25.0, 45.0), 1),
            "three_wheeler_pct": round(np.random.uniform(15.0, 30.0), 1),
            "avg_speed_kmh": spd * (0.45 if pcu > 3500 else 0.70)
        })
    pd.DataFrame(traffic_rows).to_csv(raw_dir / "dtca_traffic_counts.csv", index=False)
    logger.info("Traffic counts generated and saved.")


def _generate_landuse_geojson(raw_dir: Path):
    landuse_polygons = [
        (Polygon([(90.400, 23.775), (90.425, 23.775), (90.425, 23.805), (90.400, 23.805)]), "Commercial", 250000.0, 0, 0),
        (Polygon([(90.410, 23.725), (90.430, 23.725), (90.430, 23.742), (90.410, 23.742)]), "Commercial", 220000.0, 0, 0),
        (Polygon([(90.390, 23.755), (90.408, 23.755), (90.408, 23.770), (90.390, 23.770)]), "Industrial", 150000.0, 0, 0),
        (Polygon([(90.365, 23.740), (90.385, 23.740), (90.385, 23.760), (90.365, 23.760)]), "Mixed", 180000.0, 0, 0),
        (Polygon([(90.345, 23.785), (90.375, 23.785), (90.375, 23.830), (90.345, 23.830)]), "Mixed", 95000.0, 0, 0),
        (Polygon([(90.380, 23.850), (90.405, 23.850), (90.405, 23.885), (90.380, 23.885)]), "Residential", 110000.0, 0, 0),
        (Polygon([(90.380, 23.700), (90.420, 23.700), (90.420, 23.725), (90.380, 23.725)]), "Mixed", 130000.0, 0, 0),
        (Polygon([(90.370, 23.695), (90.435, 23.695), (90.435, 23.705), (90.370, 23.705)]), "Waterbody", 0.0, 1, 1),
        (Polygon([(90.400, 23.768), (90.418, 23.768), (90.418, 23.774), (90.400, 23.774)]), "Waterbody", 0.0, 1, 0),
        (Polygon([(90.445, 23.750), (90.465, 23.750), (90.465, 23.830), (90.445, 23.830)]), "Flood_Hazard", 40000.0, 1, 1),
    ]
    landuse_features = [{"type": "Feature", "properties": {"zone_type": ztype, "land_price_bdt_sqm": land, "is_exclusion_zone": ex, "is_flood_hazard": fl}, "geometry": poly.__geo_interface__} for poly, ztype, land, ex, fl in landuse_polygons]
    with open(raw_dir / "rajuk_dap_landuse.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "name": "rajuk_dap_landuse", "features": landuse_features}, f, indent=2)
    logger.info("Land-use features generated and saved.")


def generate_raw_datasets(output_base_dir="/home/simp/research"):
    output_base = Path(output_base_dir)
    grid_dir = output_base / "data" / "grid_models"
    raw_dir = output_base / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    grid_dir.mkdir(parents=True, exist_ok=True)

    city_anchors, city_stations = _load_auxiliary_data(raw_dir)
    _process_substations(city_stations, raw_dir)

    road_edges = [
        ("Airport_Hub", "Uttara_Sec3", "trunk", 60.0, 4, 3800),
        ("Uttara_Sec3", "Uttara_Sec11", "primary", 50.0, 3, 2400),
        ("Airport_Hub", "Mohakhali_Terminal", "motorway", 70.0, 6, 5200),
        ("Airport_Hub", "Purbachal_300ft", "trunk", 80.0, 6, 4500),
        ("Mohakhali_Terminal", "Gulshan_1", "primary", 45.0, 4, 3200),
        ("Gulshan_1", "Gulshan_2", "primary", 40.0, 4, 2800),
        ("Gulshan_2", "Baridhara_Diplomatic", "secondary", 35.0, 2, 1900),
        ("Gulshan_2", "Banani_11", "secondary", 35.0, 2, 2200),
        ("Gulshan_1", "Badda_Pragati_Sarani", "primary", 40.0, 4, 3500),
        ("Badda_Pragati_Sarani", "Hatirjheel_North", "primary", 45.0, 4, 3000),
        ("Hatirjheel_North", "Tejgaon_Industrial", "primary", 45.0, 4, 2600),
        ("Mohakhali_Terminal", "Tejgaon_Industrial", "primary", 45.0, 4, 3400),
        ("Tejgaon_Industrial", "Kawran_Bazar_CBD", "primary", 40.0, 4, 3800),
        ("Tejgaon_Industrial", "Farmgate_Hub", "primary", 40.0, 4, 4200),
        ("Farmgate_Hub", "Shahbagh_Square", "primary", 40.0, 4, 3900),
        ("Shahbagh_Square", "Motijheel_CBD", "primary", 40.0, 4, 4600),
        ("Motijheel_CBD", "Kamalapur_Railway", "secondary", 30.0, 3, 2500),
        ("Motijheel_CBD", "Old_Dhaka_Sadarghat", "secondary", 25.0, 2, 3100),
        ("Old_Dhaka_Sadarghat", "Old_Dhaka_Lalbagh", "secondary", 25.0, 2, 2200),
        ("Motijheel_CBD", "Sayedabad_Terminal", "primary", 35.0, 4, 4100),
        ("Sayedabad_Terminal", "Jatrabari_Flyover_Hub", "motorway", 60.0, 6, 4900),
        ("Farmgate_Hub", "Dhanmondi_27", "primary", 40.0, 4, 3300),
        ("Dhanmondi_27", "Dhanmondi_8A", "secondary", 35.0, 3, 2100),
        ("Dhanmondi_27", "Shyamoli_Square", "primary", 45.0, 4, 3600),
        ("Dhanmondi_8A", "Mohammadpur_Townhall", "secondary", 30.0, 2, 2300),
        ("Shyamoli_Square", "Gabtoli_Terminal", "primary", 50.0, 4, 4200),
        ("Shyamoli_Square", "Mirpur_1", "primary", 45.0, 4, 3900),
        ("Mirpur_1", "Mirpur_10_Circle", "primary", 45.0, 4, 4300),
        ("Mirpur_10_Circle", "Mirpur_12", "primary", 45.0, 4, 3100),
        ("Mirpur_10_Circle", "Mohakhali_Terminal", "primary", 40.0, 4, 4800),
    ]
    _generate_road_features(city_anchors, raw_dir, road_edges)
    _generate_traffic_counts(city_anchors, raw_dir, road_edges)
    _generate_landuse_geojson(raw_dir)
    generate_pandapower_models(grid_dir, city_stations, city_anchors)


def generate_pandapower_models(grid_dir: Path, substations, anchors):
    net_dpdc = pp.create_empty_network(name="DPDC_33kV_Subnetwork")
    slack_bus_locs = anchors["Kamalapur_Railway"]
    b_slack = pp.create_bus(net_dpdc, vn_kv=132.0, name="Grid_132kV_Slack", geodata=(float(slack_bus_locs[0]), float(slack_bus_locs[1])))
    pp.create_ext_grid(net_dpdc, bus=b_slack, vm_pu=1.02, va_degree=0.0)

    b_main_33 = pp.create_bus(net_dpdc, vn_kv=33.0, name="Main_33kV_Intake", geodata=(90.410, 23.755))
    pp.create_transformer_from_parameters(
        net_dpdc, hv_bus=b_slack, lv_bus=b_main_33, sn_mva=250.0,
        vn_hv_kv=132.0, vn_lv_kv=33.0, vkr_percent=0.3, vk_percent=8.0,
        pfe_kw=50.0, i0_percent=0.1, name="Grid_TX_132_33kV"
    )

    dpdc_subs = [s for s in substations if s["utility"] == "DPDC"]
    for s in dpdc_subs:
        b = pp.create_bus(net_dpdc, vn_kv=33.0, name=f"{s['sub_id']}_{s['name']}", geodata=(s["lon"], s["lat"]))
        pp.create_line_from_parameters(
            net_dpdc, from_bus=b_main_33, to_bus=b, length_km=3.0,
            r_ohm_per_km=0.08, x_ohm_per_km=0.10, c_nf_per_km=150.0, max_i_ka=1.2,
            name=f"Feeder_to_{s['sub_id']}"
        )
        base_mva = min(s["base_load_mva"] * 0.40, 16.0)
        pp.create_load(net_dpdc, bus=b, p_mw=base_mva * 0.95, q_mvar=base_mva * math.sqrt(1 - 0.95**2), name=f"Load_{s['sub_id']}")
    pp.to_json(net_dpdc, grid_dir / "dpdc_33kv_subnetwork.json")
    logger.info("DPDC model saved.")

    net_desco = pp.create_empty_network(name="DESCO_11kV_Feeders")
    b_desco_slack = pp.create_bus(net_desco, vn_kv=33.0, name="DESCO_33kV_Intake", geodata=(90.415, 23.790))
    pp.create_ext_grid(net_desco, bus=b_desco_slack, vm_pu=1.02)
    desco_subs = [s for s in substations if s["utility"] == "DESCO"]
    for s in desco_subs:
        b_11 = pp.create_bus(net_desco, vn_kv=11.0, name=f"{s['sub_id']}_11kV", geodata=(s["lon"], s["lat"]))
        pp.create_transformer_from_parameters(
            net_desco, hv_bus=b_desco_slack, lv_bus=b_11, sn_mva=s["rated_mva"],
            vn_hv_kv=33.0, vn_lv_kv=11.0, vkr_percent=0.5, vk_percent=6.5,
            pfe_kw=25.0, i0_percent=0.10, name=f"TX_{s['sub_id']}"
        )
        base_mva = min(s["base_load_mva"] * 0.35, 12.0)
        pp.create_load(net_desco, bus=b_11, p_mw=base_mva * 0.95, q_mvar=base_mva * math.sqrt(1 - 0.95**2), name=f"Load_{s['sub_id']}")
    pp.to_json(net_desco, grid_dir / "desco_11kv_feeders.json")
    logger.info("DESCO model saved.")


def _generate_demand_grid(anchors: dict, processed_dir: Path):
    demand_features, demand_points, demand_ids, demand_values = [], [], [], []
    anchors_list = list(anchors.items())
    zone_idx = 0
    for name, (a_lon, a_lat, atype, zone, lprice) in anchors_list:
        for k in range(4):
            zone_idx += 1
            lon, lat = a_lon + np.random.uniform(-0.008, 0.008), a_lat + np.random.uniform(-0.008, 0.008)
            did = f"DEMAND-{zone_idx:03d}"
            base_m = 1.8 if atype in ["Commercial", "Transport_Hub"] else 1.0
            total_kwh = sum([
                np.random.uniform(150, 450),
                np.random.uniform(300, 850),
                np.random.uniform(200, 600),
                np.random.uniform(250, 750)
            ]) * base_m + (np.random.uniform(800, 2200) if atype == "Transport_Hub" else 0.0)
            demand_ids.append(did)
            demand_points.append((lon, lat))
            demand_values.append(total_kwh)
            demand_features.append({
                "type": "Feature",
                "properties": {
                    "demand_id": did,
                    "anchor_zone": name,
                    "zone_type": atype,
                    "zone_name": zone,
                    "daily_demand_kwh": round(total_kwh, 1)
                },
                "geometry": Point(lon, lat).__geo_interface__
            })

    with open(processed_dir / "demand_grid_100m.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "name": "demand_grid_100m", "features": demand_features}, f, indent=2)
    logger.info("Demand grid generated and saved.")
    return demand_points, demand_ids, demand_values


def _generate_candidate_sites(anchors: dict, substations: list, processed_dir: Path):
    candidate_features, candidate_points, candidate_ids, c_idx = [], [], [], 0
    anchors_list = list(anchors.items())
    for name, (a_lon, a_lat, atype, zone, lprice) in anchors_list:
        for k in range(2):
            c_idx += 1
            cid = f"CS-{c_idx:02d}"
            lon, lat = a_lon + np.random.uniform(-0.005, 0.005), a_lat + np.random.uniform(-0.005, 0.005)
            nearest_sub = min(substations, key=lambda s: (s["lon"]-lon)**2 + (s["lat"]-lat)**2)
            sub_dist_m = math.sqrt((nearest_sub["lon"]-lon)**2 + (nearest_sub["lat"]-lat)**2) * 111000.0
            headroom = round(float(nearest_sub["rated_mva"] - nearest_sub["base_load_mva"]), 2)
            t_score = round(float(np.random.uniform(0.80, 0.98) if atype in ["Commercial", "Transport_Hub", "Highway"] else np.random.uniform(0.50, 0.78)), 3)
            p_score = round(float(np.random.uniform(0.82, 0.99) if atype in ["Commercial", "Transport_Hub"] else np.random.uniform(0.45, 0.75)), 3)
            park_score = round(float(np.random.uniform(0.65, 0.95)), 3)
            ahp_score = round(float(0.25 * t_score + 0.20 * p_score + 0.18 * park_score + 0.15 * (1.0 - min(sub_dist_m / 5000.0, 1.0)) + 0.12 * (headroom / 20.0) + 0.10 * (1.0 - min(lprice / 250000.0, 1.0))), 3)

            candidate_features.append({
                "type": "Feature",
                "properties": {
                    "candidate_id": cid,
                    "site_name": f"{name}_Site_{k+1}",
                    "zone_name": zone,
                    "land_cost_bdt_sqm": lprice,
                    # Per-candidate demand is not used by the optimizer; demand belongs to zones.
                    "nearest_substation_id": nearest_sub["sub_id"],
                    "distance_to_substation_m": round(sub_dist_m, 1),
                    "substation_headroom_mva": headroom,
                    "traffic_density_score": t_score,
                    "poi_score": p_score,
                    "parking_score": park_score,
                    "ahp_suitability_score": ahp_score,
                    "is_flood_safe": True
                },
                "geometry": Point(lon, lat).__geo_interface__
            })
            candidate_ids.append(cid)
            candidate_points.append((lon, lat))

    with open(processed_dir / "candidate_sites_filtered.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "name": "candidate_sites_filtered", "features": candidate_features}, f, indent=2)
    logger.info("Candidate sites generated and saved.")
    return candidate_points, candidate_ids


def _generate_od_matrix(demand_points: list, candidate_points: list, demand_ids: list, candidate_ids: list, demand_values: list, processed_dir: Path):
    n_demand, n_candidate = len(demand_points), len(candidate_points)
    dist_matrix = np.zeros((n_demand, n_candidate), dtype=np.float32)
    time_matrix = np.zeros((n_demand, n_candidate), dtype=np.float32)
    for i in range(n_demand):
        d_lon, d_lat = demand_points[i]
        for j in range(n_candidate):
            c_lon, c_lat = candidate_points[j]
            d_lat_r, d_lon_r = math.radians(c_lat - d_lat), math.radians(c_lon - d_lon)
            a = math.sin(d_lat_r/2)**2 + math.cos(math.radians(d_lat)) * math.cos(math.radians(c_lat)) * math.sin(d_lon_r/2)**2
            dist_m = 6371000.0 * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))) * 1.25
            dist_matrix[i, j], time_matrix[i, j] = dist_m, (dist_m / 1000.0) / np.random.uniform(14.0, 22.0) * 60.0

    np.savez_compressed(processed_dir / "od_travel_time_matrix.npz", distances=dist_matrix, travel_times=time_matrix, demand_ids=np.array(demand_ids), candidate_ids=np.array(candidate_ids), demand_values=np.array(demand_values))
    logger.info("OD matrix generated and saved.")


def generate_processed_datasets(base_dir="/home/simp/research"):
    processed_dir = Path(base_dir) / "data" / "processed"
    raw_dir = Path(base_dir) / "data" / "raw"
    processed_dir.mkdir(parents=True, exist_ok=True)

    anchors_path = raw_dir / "dhaka_anchors.yaml"
    substations_path = raw_dir / "substations.yaml"
    if not anchors_path.exists() or not substations_path.exists():
        default_raw = Path(__file__).resolve().parent.parent / "data" / "raw"
        if not anchors_path.exists():
            anchors_path = default_raw / "dhaka_anchors.yaml"
        if not substations_path.exists():
            substations_path = default_raw / "substations.yaml"

    with open(anchors_path, "r") as f:
        anchors = yaml.safe_load(f)
    with open(substations_path, "r") as f:
        substations = yaml.safe_load(f)

    np.random.seed(42)
    demand_points, demand_ids, demand_values = _generate_demand_grid(anchors, processed_dir)
    # The demo power-flow model currently represents DPDC only; keep generated
    # candidate-to-substation links within that model rather than inventing a DESCO bus.
    grid_substations = [item for item in substations if item["utility"] == "DPDC"]
    candidate_points, candidate_ids = _generate_candidate_sites(anchors, grid_substations, processed_dir)
    _generate_od_matrix(demand_points, candidate_points, demand_ids, candidate_ids, demand_values, processed_dir)


def generate_all_data(base_dir="/home/simp/research"):
    """Explicitly generate synthetic benchmark data for demos/tests only."""
    print("WARNING: generating SYNTHETIC DEMO data; these values are not observed or official.")
    print("Generating raw and processed datasets...")
    generate_raw_datasets(base_dir)
    print("Generating processed candidate sites, demand grid, and OD matrix...")
    generate_processed_datasets(base_dir)
    print("All benchmark datasets successfully generated!")

if __name__ == "__main__":
    generate_all_data()
