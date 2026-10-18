"""Shared geospatial utility functions."""

import math


def haversine_distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculate the great-circle distance between two points on Earth (in meters).

    Args:
        p1: (longitude, latitude) in decimal degrees
        p2: (longitude, latitude) in decimal degrees

    Returns:
        Distance in meters
    """
    lon1, lat1 = p1
    lon2, lat2 = p2
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000.0 * c


def bpr_travel_time(
    free_flow_time: float,
    volume: float,
    capacity: float,
    alpha: float = 0.15,
    beta: float = 4.0,
) -> float:
    """Calculate travel time using the Bureau of Public Roads (BPR) function.

    Args:
        free_flow_time: Travel time at zero congestion (minutes)
        volume: Current traffic volume (PCU/hr)
        capacity: Road capacity (PCU/hr)
        alpha: BPR alpha parameter (default 0.15)
        beta: BPR beta parameter (default 4.0)

    Returns:
        Congested travel time (minutes)
    """
    if capacity <= 0:
        raise ValueError("Capacity must be positive")
    return free_flow_time * (1.0 + alpha * ((volume / capacity) ** beta))
