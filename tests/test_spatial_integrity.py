"""Tests for GIS spatial multi-criteria analysis (AHP-TOPSIS), buffering, and road networks."""

import json
import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from src.spatial.ahp_mcdm import (
    calculate_ahp_weights,
    compute_consistency_ratio,
    standardize_criteria_fuzzy,
    topsis_ranking,
    compute_spatial_suitability,
    AHPInconsistencyError
)
from src.spatial.spatial_filter import SpatialFilter, filter_candidate_sites
from src.spatial.osm_network import OSMRoadNetwork, download_osm_road_network


def test_network_route_failure_can_disable_euclidean_approximation():
    network = OSMRoadNetwork()
    network.graph.add_node("demand-node", pos=(90.4, 23.7), lon=90.4, lat=23.7)
    network.graph.add_node("candidate-node", pos=(90.5, 23.8), lon=90.5, lat=23.8)
    with pytest.raises(ValueError, match="Euclidean fallback is disabled"):
        network.calculate_shortest_path_matrix(
            [(90.4, 23.7)], [(90.5, 23.8)], allow_approximate_fallback=False
        )


def test_shortest_path_matrix_uses_road_edge_lengths_not_direct_distance():
    network = OSMRoadNetwork()
    nodes = {
        "a": (90.0, 23.0),
        "b": (90.01, 23.005),
        "c": (90.02, 23.0),
    }
    for node, (lon, lat) in nodes.items():
        network.graph.add_node(node, pos=(lon, lat), lon=lon, lat=lat)
    network.graph.add_edge("a", "b", length_m=1300.0, weight=2.0)
    network.graph.add_edge("b", "c", length_m=1300.0, weight=3.0)

    distances, times = network.calculate_shortest_path_matrix(
        [(90.0, 23.0)], [(90.02, 23.0)]
    )

    assert distances[0, 0] == pytest.approx(2600.0)
    assert times[0, 0] == pytest.approx(5.0)
    assert distances[0, 0] > network._haversine_distance_m((90.0, 23.0), (90.02, 23.0))


def test_candidate_road_distances_report_shortest_paths_snap_offsets_and_unconnected_pairs():
    roads = gpd.GeoDataFrame(
        {
            "u": ["a", "b", "x"],
            "v": ["b", "c", "y"],
            "length_m": [100.0, 200.0, 50.0],
            "maxspeed": [30.0, 30.0, 30.0],
            "lanes": [1, 1, 1],
            "pcu_per_hr": [100.0, 100.0, 100.0],
        },
        geometry=[
            LineString([(90.0, 23.0), (90.01, 23.0)]),
            LineString([(90.01, 23.0), (90.02, 23.0)]),
            LineString([(91.0, 24.0), (91.01, 24.0)]),
        ],
        crs="EPSG:4326",
    )
    candidates = gpd.GeoDataFrame(
        {
            "candidate_id": ["CS-A", "CS-C", "CS-Z"],
            "site_name": ["Origin", "Destination", "Disconnected"],
        },
        geometry=[Point(90.0, 23.0), Point(90.02, 23.0), Point(91.0, 24.0)],
        crs="EPSG:4326",
    )
    network = OSMRoadNetwork()
    for idx, row in roads.iterrows():
        start, end = row.geometry.coords[0], row.geometry.coords[-1]
        for node, coordinate in ((row.u, start), (row.v, end)):
            network.graph.add_node(node, pos=coordinate, lon=coordinate[0], lat=coordinate[1])
        network.graph.add_edge(row.u, row.v, length_m=row.length_m)
        network.graph.add_edge(row.v, row.u, length_m=row.length_m)

    result = network.calculate_candidate_road_distances(candidates)

    route = result[(result.from_candidate_id == "CS-A") & (result.to_candidate_id == "CS-C")].iloc[0]
    assert route.road_distance_m == 300
    assert route.route_status == "routed"
    assert route.from_road_snap_distance_m == 0
    disconnected = result[(result.from_candidate_id == "CS-A") & (result.to_candidate_id == "CS-Z")].iloc[0]
    assert pd.isna(disconnected.road_distance_m)
    assert disconnected.route_status == "no_road_route"
    reverse = result[(result.from_candidate_id == "CS-C") & (result.to_candidate_id == "CS-A")].iloc[0]
    assert reverse.road_distance_m == 300


def test_road_loader_respects_oneway_direction(tmp_path):
    roads_path = tmp_path / "roads.geojson"
    roads_path.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":'
        '{"u":"a","v":"b","length_m":100,"maxspeed":30,"lanes":1,"pcu_per_hr":100,"oneway":"yes"},'
        '"geometry":{"type":"LineString","coordinates":[[90,23],[90.01,23]]}}]}',
        encoding="utf-8",
    )

    network = OSMRoadNetwork(str(roads_path))

    assert network.graph.has_edge("a", "b")
    assert not network.graph.has_edge("b", "a")


def test_osm_road_download_writes_topological_segments_and_provenance(tmp_path):
    elements = [{
        "type": "way",
        "id": 123,
        "nodes": [10, 11, 12],
        "geometry": [
            {"lon": 90.0, "lat": 23.0},
            {"lon": 90.01, "lat": 23.0},
            {"lon": 90.02, "lat": 23.0},
        ],
        "tags": {"highway": "primary", "name": "Test Road", "maxspeed": "30 mph", "oneway": "yes"},
    }]

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"elements": elements}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, data):
            assert 'way["highway"' in data["data"]
            return FakeResponse()

    output = tmp_path / "roads.geojson"
    result = download_osm_road_network(
        (23.0, 90.0, 23.1, 90.1), output, client_factory=FakeClient,
    )
    roads = json.loads(output.read_text(encoding="utf-8"))
    provenance = json.loads((tmp_path / "roads.geojson.provenance.json").read_text(encoding="utf-8"))

    assert len(roads["features"]) == 2
    first = roads["features"][0]["properties"]
    assert (first["u"], first["v"]) == ("osm:10", "osm:11")
    assert first["oneway"] == "yes"
    assert first["maxspeed"] == pytest.approx(48.28032)
    assert first["pcu_source"].startswith("assumed:")
    assert provenance["data_class"] == "derived_from_observed"
    assert "never observed traffic" in provenance["transformation"]
    network = OSMRoadNetwork(str(output))
    assert network.graph.has_edge("osm:10", "osm:11")
    assert not network.graph.has_edge("osm:11", "osm:10")
    assert result["feature_count"] == "2"


def test_osm_road_download_rejects_invalid_overpass_payload(tmp_path):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"elements": "not a list"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, data):
            return FakeResponse()

    with pytest.raises(RuntimeError, match="invalid road element list"):
        download_osm_road_network(
            (23.0, 90.0, 23.1, 90.1),
            tmp_path / "roads.geojson",
            client_factory=FakeClient,
        )

    assert not (tmp_path / "roads.geojson").exists()


def test_road_loader_respects_oneway_direction(tmp_path):
    roads_path = tmp_path / "roads.geojson"
    roads_path.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":'
        '{"u":"a","v":"b","length_m":100,"maxspeed":30,"lanes":1,"pcu_per_hr":100,"oneway":"yes"},'
        '"geometry":{"type":"LineString","coordinates":[[90,23],[90.01,23]]}}]}',
        encoding="utf-8",
    )

    network = OSMRoadNetwork(str(roads_path))

    assert network.graph.has_edge("a", "b")
    assert not network.graph.has_edge("b", "a")


def test_osm_road_download_writes_topological_segments_and_provenance(tmp_path):
    elements = [{
        "type": "way",
        "id": 123,
        "nodes": [10, 11, 12],
        "geometry": [
            {"lon": 90.0, "lat": 23.0},
            {"lon": 90.01, "lat": 23.0},
            {"lon": 90.02, "lat": 23.0},
        ],
        "tags": {"highway": "primary", "name": "Test Road", "maxspeed": "30 mph", "oneway": "yes"},
    }]

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"elements": elements}

    class FakeClient:
        def __init__(self, **kwargs):
            self.options = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, data):
            assert 'way["highway"' in data["data"]
            return FakeResponse()

    output = tmp_path / "roads.geojson"
    result = download_osm_road_network(
        (23.0, 90.0, 23.1, 90.1), output, client_factory=FakeClient,
    )
    roads = json.loads(output.read_text(encoding="utf-8"))
    provenance = json.loads((tmp_path / "roads.geojson.provenance.json").read_text(encoding="utf-8"))

    assert len(roads["features"]) == 2
    first = roads["features"][0]["properties"]
    assert (first["u"], first["v"]) == ("osm:10", "osm:11")
    assert first["oneway"] == "yes"
    assert first["maxspeed"] == pytest.approx(48.28032)
    assert first["pcu_source"].startswith("assumed:")
    assert provenance["data_class"] == "derived_from_observed"
    assert "never observed traffic" in provenance["transformation"]
    network = OSMRoadNetwork(str(output))
    assert network.graph.has_edge("osm:10", "osm:11")
    assert not network.graph.has_edge("osm:11", "osm:10")
    assert result["feature_count"] == "2"


def test_ahp_weights_consistent(sample_pairwise_matrix):
    weights, lambda_max, CI, CR = calculate_ahp_weights(sample_pairwise_matrix)
    assert len(weights) == 3
    assert np.isclose(np.sum(weights), 1.0)
    assert np.all(weights > 0)
    assert CR < 0.10, f"Expected CR < 0.10, got {CR}"
    assert weights[0] > weights[1] > weights[2]


def test_ahp_inconsistency_detection(inconsistent_pairwise_matrix):
    weights, lambda_max, CI, CR = calculate_ahp_weights(inconsistent_pairwise_matrix)
    assert CR >= 0.10


def test_fuzzy_standardization():
    raw_vals = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    # Benefit criterion (higher is better)
    fuzzy_max = standardize_criteria_fuzzy(raw_vals, preference="max")
    assert np.isclose(fuzzy_max[0], 0.0)
    assert np.isclose(fuzzy_max[-1], 1.0)
    assert np.all(np.diff(fuzzy_max) >= 0)

    # Cost criterion (lower is better)
    fuzzy_min = standardize_criteria_fuzzy(raw_vals, preference="min_cost")
    assert np.isclose(fuzzy_min[0], 1.0)
    assert np.isclose(fuzzy_min[-1], 0.0)
    assert np.all(np.diff(fuzzy_min) <= 0)


def test_topsis_ranking():
    # 3 alternatives, 3 criteria
    decision_mat = np.array([
        [9.0, 8.0, 100.0],  # Alt 1: High traffic, High POI, Low land cost
        [5.0, 5.0, 200.0],  # Alt 2: Medium traffic, Medium POI, Med land cost
        [2.0, 2.0, 300.0],  # Alt 3: Low traffic, Low POI, High land cost
    ])
    weights = [0.4, 0.4, 0.2]
    types = ["max", "max", "min"]

    scores, ranks = topsis_ranking(decision_mat, weights, types)
    assert len(scores) == 3
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)
    assert ranks[0] == 0, "Alt 1 should be ranked 1st"
    assert scores[0] > scores[1] > scores[2]


def test_spatial_suitability_composite():
    df = pd.DataFrame({
        "crit1": [0.8, 0.5, 0.9],
        "crit2": [0.7, 0.6, 0.8],
        "excl": [1, 1, 0]  # Point 3 is in exclusion zone
    })
    weights = {"crit1": 0.6, "crit2": 0.4}
    suitability = compute_spatial_suitability(df, weights, exclusion_cols=["excl"])

    assert suitability[0] > 0.7
    assert suitability[2] == 0.0, "Excluded point must have suitability score 0.0"


def test_spatial_filter_exclusion(mock_candidate_gdf):
    # Exclusion polygon over Motijheel point (Point(90.420, 23.730))
    poly = Polygon([(90.415, 23.725), (90.425, 23.725), (90.425, 23.735), (90.415, 23.735)])
    landuse_gdf = gpd.GeoDataFrame({
        "zone_type": ["Waterbody"],
        "is_exclusion_zone": [1]
    }, geometry=[poly], crs="EPSG:4326")

    filtered = filter_candidate_sites(mock_candidate_gdf, landuse_gdf)
    assert "CS-02" not in filtered["candidate_id"].values
    assert len(filtered) < len(mock_candidate_gdf)


def test_spatial_filter_spacing(mock_candidate_gdf):
    # Add an identical point to test minimum spacing suppression
    duplicate_pt = mock_candidate_gdf.iloc[0:1].copy()
    duplicate_pt["candidate_id"] = "CS-DUP"
    duplicate_pt["ahp_suitability_score"] = 0.50  # Lower score
    combined = pd.concat([mock_candidate_gdf, duplicate_pt], ignore_index=True)

    s_filter = SpatialFilter({"spatial": {"candidate_site_generation": {"min_spacing_m": 500.0}}})
    spaced = s_filter.apply_spatial_spacing(combined, min_distance_m=500.0)
    assert len(spaced) == len(mock_candidate_gdf)
    assert "CS-01" in spaced["candidate_id"].values
