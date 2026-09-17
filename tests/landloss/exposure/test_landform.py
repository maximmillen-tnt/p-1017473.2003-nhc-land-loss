"""Tests for the hill versus flat landform classification."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from landloss.domain import constants
from landloss.exposure import landform as landform_module
from landloss.exposure.landform import (
    ELEVATED_FLAT,
    FLAT,
    HILL,
    LANDFORM_CLASSES,
    LANDFORM_COLUMN,
    classify_landform,
    get_flatland,
)


def make_addresses(points: list[tuple[float, float]]):
    """Build an address frame with one point per coordinate pair."""
    return gpd.GeoDataFrame(
        {"address_id": list(range(len(points)))},
        geometry=[Point(x, y) for x, y in points],
        crs=constants.DEFAULT_CRS,
    )


def make_flatland(boxes: list[tuple[float, float, float, float]]):
    """Build a flatland frame from (minx, miny, maxx, maxy) rectangles."""
    return gpd.GeoDataFrame(
        {"nlm_id": list(range(len(boxes)))},
        geometry=[
            Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])
            for minx, miny, maxx, maxy in boxes
        ],
        crs=constants.DEFAULT_CRS,
    )


# --- classification -----------------------------------------------------------


def test_an_address_inside_flat_land_is_flat() -> None:
    """The flat classes are what the liquefaction and inundation losses hang off."""
    result = classify_landform(
        make_addresses([(5, 5)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == FLAT


def test_an_address_outside_flat_land_is_a_hill() -> None:
    """Anything the NLM does not call flat is sloping, and loses land differently."""
    result = classify_landform(
        make_addresses([(50, 50)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == HILL


def test_an_address_on_the_boundary_is_not_flat() -> None:
    """The join is ``within``, so the edge of the flat land is where the hill starts."""
    result = classify_landform(
        make_addresses([(10, 5)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == HILL


def test_with_no_flat_land_every_address_is_a_hill() -> None:
    """An extent the NLM maps no flat land over still classifies every address."""
    addresses = make_addresses([(1, 1), (2, 2), (3, 3)])

    result = classify_landform(addresses, make_flatland([]))

    assert list(result[LANDFORM_COLUMN]) == [HILL, HILL, HILL]


def test_every_class_is_one_of_the_declared_values() -> None:
    """The landform column never holds a value outside LANDFORM_CLASSES."""
    addresses = make_addresses([(5, 5), (50, 50)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert set(result[LANDFORM_COLUMN]) <= set(LANDFORM_CLASSES)


def test_elevated_flat_is_never_assigned_in_phase_one() -> None:
    """Separating raised flat land needs the DEM, which is Phase 2 work."""
    addresses = make_addresses([(5, 5), (50, 50)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert ELEVATED_FLAT not in set(result[LANDFORM_COLUMN])


# --- frame shape --------------------------------------------------------------


def test_overlapping_flatland_polygons_do_not_duplicate_an_address() -> None:
    """The NLM polygons overlap; a duplicated address would be counted twice."""
    addresses = make_addresses([(2, 2)])
    flatland = make_flatland([(0, 0, 10, 10), (0, 0, 5, 5), (1, 1, 4, 4)])

    result = classify_landform(addresses, flatland)

    assert len(result) == 1


def test_exactly_one_column_is_added() -> None:
    """Downstream code selects by name, so a stray join column would surprise it."""
    addresses = make_addresses([(5, 5)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert list(result.columns) == [*addresses.columns, LANDFORM_COLUMN]


def test_the_index_is_reset() -> None:
    """A contiguous index is what lets later steps address rows by label safely."""
    addresses = make_addresses([(5, 5), (50, 50)])
    addresses.index = [7, 9]

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert list(result.index) == [0, 1]


def test_the_input_is_not_modified() -> None:
    """Classifying returns a copy, leaving the caller's frame untouched."""
    addresses = make_addresses([(5, 5)])

    classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert LANDFORM_COLUMN not in addresses


def test_an_empty_address_frame_is_handled() -> None:
    """Clipping to a boundary can leave nothing behind, and that is not an error."""
    addresses = make_addresses([]).astype({"address_id": "int64"})

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert len(result) == 0
    assert LANDFORM_COLUMN in result.columns


# --- loading ------------------------------------------------------------------


@pytest.fixture
def fake_layer(monkeypatch: pytest.MonkeyPatch):
    """Serve a fixed two-polygon layer in place of the Koordinates read."""
    calls = {}
    source = make_flatland([(0, 0, 10, 10), (100, 100, 110, 110)])

    def fake_read(**kwargs):
        calls.update(kwargs)
        return source.copy()

    monkeypatch.setattr(landform_module, "get_koordinates_layer_extent", fake_read)
    return calls


def test_the_flatland_is_read_from_the_nlm_layer_on_the_tt_domain(fake_layer) -> None:
    """The NLM layer is mirrored on T+T's instance, not on LINZ's."""
    get_flatland()

    assert fake_layer["layer"] == constants.NLM_FLATLAND_LAYER_ID
    assert fake_layer["domain"] == constants.TTGROUP_DOMAIN


def test_without_a_clip_everything_read_is_kept(fake_layer) -> None:
    """Omitting clip_to leaves the bounding box read untouched."""
    result = get_flatland()

    assert len(result) == 2


def test_clip_to_removes_what_falls_outside_the_boundary(fake_layer) -> None:
    """A bounding box is a rectangle; clip_to cuts back to the real study area."""
    boundary = gpd.GeoDataFrame(
        geometry=[Polygon([(-5, -5), (50, -5), (50, 50), (-5, 50)])],
        crs=constants.DEFAULT_CRS,
    )

    result = get_flatland(clip_to=boundary)

    assert list(result["nlm_id"]) == [0]
