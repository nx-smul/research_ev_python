"""Path management for pipeline artifacts."""

from pathlib import Path


class PathManager:
    """Centralized path resolution for all pipeline inputs and outputs."""

    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir)

    # Raw inputs
    def roads(self) -> Path:
        return self.base / "data" / "raw" / "osm_dhaka_roads.geojson"

    def landuse(self) -> Path:
        return self.base / "data" / "raw" / "rajuk_dap_landuse.geojson"

    def substations(self) -> Path:
        return self.base / "data" / "raw" / "dpdc_desco_substations.csv"

    # Processed inputs
    def candidates(self) -> Path:
        return self.base / "data" / "processed" / "candidate_sites_filtered.geojson"

    def demand_grid(self) -> Path:
        return self.base / "data" / "processed" / "demand_grid_100m.geojson"

    def od_matrices(self) -> Path:
        return self.base / "data" / "processed" / "od_travel_time_matrix.npz"

    # Grid models
    def grid_model(self) -> Path:
        return self.base / "data" / "grid_models" / "dpdc_33kv_subnetwork.json"

    # Results
    def results_dir(self) -> Path:
        return self.base / "results"

    def tables_dir(self) -> Path:
        return self.results_dir() / "tables"

    def figures_dir(self) -> Path:
        return self.results_dir() / "figures"

    def reports_dir(self) -> Path:
        return self.results_dir() / "reports"

    def research_dir(self, run_id: str) -> Path:
        return self.results_dir() / "research" / run_id

    def manifest(self) -> Path:
        return self.results_dir() / "run_manifest.json"

    # Config
    def default_config(self) -> Path:
        return self.base / "configs" / "default_config.yaml"

    def user_settings(self) -> Path:
        return self.base / "configs" / "user_settings.yaml"

    # Output files
    def candidate_sites_csv(self) -> Path:
        return self.tables_dir() / "candidate_sites.csv"

    def pareto_solutions(self) -> Path:
        return self.tables_dir() / "optimal_solutions_pareto.csv"

    def road_distances(self) -> Path:
        return self.tables_dir() / "road_distances.csv"

    def baseline_comparison(self) -> Path:
        return self.tables_dir() / "baseline_comparison.csv"

    def voltage_profile_fig(self) -> Path:
        return self.figures_dir() / "voltage_profile_comparison.png"

    def ahp_suitability_fig(self) -> Path:
        return self.figures_dir() / "ahp_suitability_map.png"

    def optimal_locations_fig(self) -> Path:
        return self.figures_dir() / "optimal_cs_locations.png"

    def pareto_front_fig(self) -> Path:
        return self.figures_dir() / "pareto_frontier.png"

    def run_report(self, run_id: str) -> Path:
        return self.reports_dir() / f"run_{run_id}.md"
