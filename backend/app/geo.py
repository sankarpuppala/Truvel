"""Geometry helpers. Pure functions, metres and kilometres, no state.

Used by the deck (SPEC §9.4), check-in verification (§8.7), dedupe (§9.6),
impossible-travel detection (§9.8) and the fog map (§8.4).
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088
BIKE_SPEED_KMH = 20.0
ROAD_WINDING_FACTOR = 1.3


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Same distance in metres, for the check-in radius test."""
    return haversine_km(lat1, lng1, lat2, lng2) * 1000.0


def bbox_around(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """A (min_lat, min_lng, max_lat, max_lng) box that contains the radius.

    The deck prefilters candidates with this cheap SQL box before computing
    haversine on what is left (SPEC §15: 10k places under 200 ms).
    """
    d_lat = radius_km / 111.32
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    d_lng = radius_km / (111.32 * cos_lat)
    return (lat - d_lat, lng - d_lng, lat + d_lat, lng + d_lng)


def in_bbox(lat: float, lng: float, bbox: tuple[float, float, float, float]) -> bool:
    min_lat, min_lng, max_lat, max_lng = bbox
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def travel_minutes(distance_km: float) -> int:
    """Rough door-to-door minutes by bike: haversine x 1.3 / 20 km/h (SPEC §8.2)."""
    minutes = distance_km * ROAD_WINDING_FACTOR / BIKE_SPEED_KMH * 60.0
    return int(round(minutes))


def speed_kmh(distance_km: float, hours: float) -> float:
    """Implied speed; used for the impossible-travel flag (SPEC §9.8).

    Two visits at the same instant are not evidence of travel at all, so a
    zero or negative gap gives infinite speed only when the places differ.
    """
    if hours <= 0:
        return math.inf if distance_km > 0 else 0.0
    return distance_km / hours
