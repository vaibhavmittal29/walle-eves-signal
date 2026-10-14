"""Tests for geometry utilities: distance, bearing, and angle wrapping."""

import math
import pytest
from walle.geometry import bearing, distance, wrap_angle


def test_distance():
    """Verify Euclidean distance calculations."""
    assert distance((0, 0), (0, 0)) == 0.0
    assert distance((0, 0), (3, 4)) == 5.0
    assert distance((2, 3), (5, 7)) == 5.0
    assert pytest.approx(distance((1.5, 2.5), (4.5, 6.5))) == 5.0


def test_bearing_cardinal_directions():
    """Verify standard compass bearings for North, East, South, West.

    Recall: y increases downward.
    - North: dy < 0, dx = 0  => 0 deg
    - East:  dy = 0, dx > 0  => 90 deg
    - South: dy > 0, dx = 0  => 180 deg
    - West:  dy = 0, dx < 0  => 270 deg
    """
    origin = (5, 5)
    north = (5, 2)
    east = (8, 5)
    south = (5, 9)
    west = (1, 5)

    assert bearing(origin, north) == pytest.approx(0.0)
    assert bearing(origin, east) == pytest.approx(90.0)
    assert bearing(origin, south) == pytest.approx(180.0)
    assert bearing(origin, west) == pytest.approx(270.0)


def test_bearing_intercardinal_diagonals():
    """Verify bearings for NE, SE, SW, NW."""
    origin = (5, 5)
    ne = (8, 2)   # dx=3, dy=-3 => 45 deg
    se = (8, 8)   # dx=3, dy=3  => 135 deg
    sw = (2, 8)   # dx=-3, dy=3 => 225 deg
    nw = (2, 2)   # dx=-3, dy=-3 => 315 deg

    assert bearing(origin, ne) == pytest.approx(45.0)
    assert bearing(origin, se) == pytest.approx(135.0)
    assert bearing(origin, sw) == pytest.approx(225.0)
    assert bearing(origin, nw) == pytest.approx(315.0)


def test_wrap_angle():
    """Verify wrap_angle wraps angular differences into (-180, 180]."""
    # Exact boundaries
    assert wrap_angle(0.0) == pytest.approx(0.0)
    assert wrap_angle(180.0) == pytest.approx(180.0)
    assert wrap_angle(-180.0) == pytest.approx(180.0)

    # Small angles
    assert wrap_angle(25.0) == pytest.approx(25.0)
    assert wrap_angle(-25.0) == pytest.approx(-25.0)

    # 359 -> 1 degree wrap-around
    # If angle A is 359 and angle B is 1, delta = 1 - 359 = -358
    assert wrap_angle(1.0 - 359.0) == pytest.approx(2.0)
    assert wrap_angle(359.0 - 1.0) == pytest.approx(-2.0)

    # Large multiples
    assert wrap_angle(365.0) == pytest.approx(5.0)
    assert wrap_angle(-365.0) == pytest.approx(-5.0)
    assert wrap_angle(540.0) == pytest.approx(180.0)
    assert wrap_angle(-540.0) == pytest.approx(180.0)
