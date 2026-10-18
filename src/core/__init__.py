"""Core infrastructure: shared utilities, exceptions, and run context."""

from src.core.exceptions import ConfigError, RealDataPreflightError, OptimizationError
from src.core.geo_utils import haversine_distance_m, bpr_travel_time
from src.core.run_context import RunContext
from src.core.paths import PathManager

__all__ = [
    "ConfigError",
    "RealDataPreflightError",
    "OptimizationError",
    "haversine_distance_m",
    "bpr_travel_time",
    "RunContext",
    "PathManager",
]
