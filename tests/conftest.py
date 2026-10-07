"""Shared pytest fixtures for spatial, optimization, and grid tests."""

import os
import pytest
import yaml
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import pandapower as pp


@pytest.fixture(scope="session")
def base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def sample_config(base_dir):
    config_path = os.path.join(base_dir, "configs", "default_config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_pairwise_matrix():
    # 3x3 consistent comparison matrix: A > B by 2, B > C by 3 => A > C by 6
    return [
        [1.0, 2.0, 6.0],
        [0.5, 1.0, 3.0],
        [1.0/6.0, 1.0/3.0, 1.0]
    ]


@pytest.fixture
def inconsistent_pairwise_matrix():
    # Highly inconsistent comparison matrix
    return [
        [1.0, 9.0, 1.0/9.0],
        [1.0/9.0, 1.0, 9.0],
        [9.0, 1.0/9.0, 1.0]
    ]


@pytest.fixture
def mock_candidate_gdf():
    points = [
        Point(90.410, 23.780),  # Gulshan
        Point(90.420, 23.730),  # Motijheel
        Point(90.370, 23.750),  # Dhanmondi
        Point(90.390, 23.860),  # Uttara
        Point(90.360, 23.800),  # Mirpur
    ]
    df = pd.DataFrame({
        "candidate_id": [f"CS-{i+1:02d}" for i in range(5)],
        "site_name": ["Gulshan_S1", "Motijheel_S1", "Dhanmondi_S1", "Uttara_S1", "Mirpur_S1"],
        "zone_name": ["Gulshan_Banani", "Motijheel_Dilkusha", "Dhanmondi", "Uttara", "Mirpur"],
        "land_cost_bdt_sqm": [250000.0, 220000.0, 180000.0, 110000.0, 95000.0],
        "distance_to_substation_m": [800.0, 600.0, 1200.0, 1500.0, 900.0],
        "substation_headroom_mva": [11.5, 8.5, 8.0, 12.0, 9.0],
        "traffic_density_score": [0.92, 0.95, 0.85, 0.78, 0.88],
        "poi_score": [0.96, 0.98, 0.89, 0.75, 0.82],
        "parking_score": [0.85, 0.70, 0.75, 0.90, 0.80],
        "ahp_suitability_score": [0.88, 0.86, 0.81, 0.76, 0.83],
        "is_flood_safe": [True, True, True, True, True]
    })
    return gpd.GeoDataFrame(df, geometry=points, crs="EPSG:4326")


@pytest.fixture
def mock_od_matrices():
    np.random.seed(42)
    n_demand, n_candidate = 20, 5
    dist_mat = np.random.uniform(500, 6000, (n_demand, n_candidate)).astype(np.float32)
    time_mat = (dist_mat / 1000.0) / 20.0 * 60.0  # 20 km/h
    demand_values = np.random.uniform(200, 1200, n_demand).astype(np.float32)
    return dist_mat, time_mat, demand_values


@pytest.fixture
def mock_pandapower_network():
    net = pp.create_empty_network(name="Mock_Net")
    b0 = pp.create_bus(net, vn_kv=132.0, name="Slack")
    pp.create_ext_grid(net, bus=b0, vm_pu=1.02)
    b1 = pp.create_bus(net, vn_kv=33.0, name="Main_33kV")
    pp.create_transformer_from_parameters(
        net, hv_bus=b0, lv_bus=b1, sn_mva=100.0, vn_hv_kv=132.0, vn_lv_kv=33.0,
        vkr_percent=0.4, vk_percent=8.0, pfe_kw=30.0, i0_percent=0.1
    )
    b2 = pp.create_bus(net, vn_kv=33.0, name="Sub_1")
    pp.create_line_from_parameters(
        net, from_bus=b1, to_bus=b2, length_km=2.0, r_ohm_per_km=0.08, x_ohm_per_km=0.10,
        c_nf_per_km=100.0, max_i_ka=1.0
    )
    pp.create_load(net, bus=b2, p_mw=10.0, q_mvar=3.0)
    return net
