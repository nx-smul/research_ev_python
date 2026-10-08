"""Static research figures for spatial analysis, Pareto fronts, and grid profiles."""

from .map_plots import (
    plot_ahp_suitability_map,
    plot_optimal_cs_locations
)
from .pareto_front import (
    plot_pareto_front_2d,
    calculate_hypervolume_indicator,
    find_knee_point_solution
)

__all__ = [
    "plot_ahp_suitability_map",
    "plot_optimal_cs_locations",
    "plot_pareto_front_2d",
    "calculate_hypervolume_indicator",
    "find_knee_point_solution"
]
