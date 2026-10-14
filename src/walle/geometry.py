"""Geometry utilities for 2D grid coordinates and compass angles."""

from __future__ import annotations

import math
from typing import Sequence, Tuple, Union

Point = Union[Tuple[float, float], Tuple[int, int], Sequence[float]]


def distance(a: Point, b: Point) -> float:
    """Calculate Euclidean distance between two points (x, y).

    Args:
        a: First coordinate (x, y).
        b: Second coordinate (x, y).

    Returns:
        Euclidean distance.
    """
    return math.hypot(b[0] - a[0], b[1] - a[1])


def bearing(a: Point, b: Point) -> float:
    """Calculate standard compass bearing in degrees from point a to point b.

    Convention:
        - 0 degrees = North (up, decreasing y)
        - 90 degrees = East (right, increasing x)
        - 180 degrees = South (down, increasing y)
        - 270 degrees = West (left, decreasing x)
        - Coordinate system: y increases downward.
        - Formula: atan2(dx, -dy) mod 360.

    Args:
        a: Origin coordinate (x, y).
        b: Target coordinate (x, y).

    Returns:
        Bearing in degrees in the half-open interval [0, 360).
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    deg = math.degrees(math.atan2(dx, -dy))
    return deg % 360.0


def wrap_angle(delta: float) -> float:
    """Wrap an angular difference in degrees into the half-open interval (-180, 180].

    Args:
        delta: Angle difference in degrees.

    Returns:
        Equivalent angle in (-180, 180].
    """
    wrapped = (delta + 180.0) % 360.0 - 180.0
    if wrapped <= -180.0:
        wrapped += 360.0
    return wrapped
