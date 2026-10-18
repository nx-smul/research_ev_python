"""Pipeline stage modules — thin wrappers around domain logic."""

from src.stages.preflight import (
    REAL_DATA_REQUIRED_INPUTS,
    generate_all_data,
    generate_demo_inputs,
    sha256_file,
    validate_real_data_inputs,
)
from src.stages.spatial_ranking import run_spatial_ranking
from src.stages.road_network import compute_road_network
from src.stages.optimization import run_optimization
from src.stages.grid_analysis import run_grid_analysis
from src.stages.visualization import generate_visualizations
from src.stages.reporting import generate_report, write_run_manifest

__all__ = [
    "REAL_DATA_REQUIRED_INPUTS",
    "generate_demo_inputs",
    "sha256_file",
    "validate_real_data_inputs",
    "run_spatial_ranking",
    "compute_road_network",
    "run_optimization",
    "run_grid_analysis",
    "generate_visualizations",
    "generate_report",
    "write_run_manifest",
]

