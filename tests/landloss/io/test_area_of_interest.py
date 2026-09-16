"""Tests for the named study extents."""

import pytest

from landloss.domain.constants import DEFAULT_CRS
from landloss.io.area_of_interest import SMALL_WLG_PILOT, WGS84, AreaOfInterest

# The corners the pilot extent was defined from, as (latitude, longitude).
NORTH_WEST = (-41.309796, 174.772318)
SOUTH_EAST = (-41.32486560367306, 174.80616774743507)


def test_wgs84_bbox_round_trips_the_defined_corners() -> None:
    """The extent in WGS84 is exactly what it was defined from."""
    minx, miny, maxx, maxy = SMALL_WLG_PILOT.bbox(WGS84)

    assert minx == pytest.approx(NORTH_WEST[1])
    assert maxy == pytest.approx(NORTH_WEST[0])
    assert maxx == pytest.approx(SOUTH_EAST[1])
    assert miny == pytest.approx(SOUTH_EAST[0])


def test_defaults_to_nztm() -> None:
    """Asking for the bbox without a CRS gives NZTM, as the model works in it."""
    minx, miny, maxx, maxy = SMALL_WLG_PILOT.bbox()

    # Central Wellington sits near 1_749_000E 5_424_000N in NZTM.
    assert 1_740_000 < minx < 1_760_000
    assert 5_415_000 < miny < 5_430_000
    assert maxx > minx
    assert maxy > miny


def test_the_pilot_is_a_few_square_kilometres() -> None:
    """The pilot is small enough to iterate on, which is its whole purpose."""
    area_km2 = SMALL_WLG_PILOT.polygon().area / 1e6

    assert 3 < area_km2 < 7


def test_bounds_are_ordered_min_then_max() -> None:
    """The bbox follows the (minx, miny, maxx, maxy) order readers expect."""
    minx, miny, maxx, maxy = SMALL_WLG_PILOT.bbox()

    assert minx < maxx
    assert miny < maxy


def test_geoseries_carries_the_requested_crs() -> None:
    """The GeoSeries is tagged with the CRS, so geopandas can transform it."""
    series = SMALL_WLG_PILOT.to_geoseries(DEFAULT_CRS)

    assert series.crs.to_string() == DEFAULT_CRS
    assert len(series) == 1


def test_polygon_matches_the_bbox() -> None:
    """The polygon and the bbox describe the same extent."""
    polygon_bounds = SMALL_WLG_PILOT.polygon().bounds

    assert polygon_bounds == pytest.approx(SMALL_WLG_PILOT.bbox())


def test_an_area_of_interest_is_immutable() -> None:
    """Extents are constants; accidentally reassigning one should fail."""
    aoi = AreaOfInterest(name="test", west=1.0, south=2.0, east=3.0, north=4.0)

    with pytest.raises(AttributeError):
        aoi.west = 99.0  # type: ignore[misc]


def test_the_pilot_is_named() -> None:
    """The name is used in outputs and file names, so it must not be empty."""
    assert SMALL_WLG_PILOT.name
