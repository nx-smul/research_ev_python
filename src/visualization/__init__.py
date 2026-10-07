"""Visualization suite for spatial maps, interactive GIS, Pareto frontiers, and grid profiles."""

from .map_plots import (
    generate_interactive_folium_map,
    plot_ahp_suitability_map,
    plot_optimal_cs_locations
)
from .pareto_front import (
    plot_pareto_front_2d,
    calculate_hypervolume_indicator,
    find_knee_point_solution
)

__all__ = [
    "generate_interactive_folium_map",
    "plot_ahp_suitability_map",
    "plot_optimal_cs_locations",
    "plot_pareto_front_2d",
    "calculate_hypervolume_indicator",
    "find_knee_point_solution"
]
