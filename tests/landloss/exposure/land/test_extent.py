"""Tests for the insured land extent built around the building outlines."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from landloss.domain import constants
from landloss.exposure.land.extent import (
    ADDRESS_ID_COLUMN,
    AREA_COLUMN,
    BUILDING_COUNT_COLUMN,
    DWELLING_COUNT_COLUMN,
    INSURED_LAND_BUFFER_M,
    OUTLINE_ID_COLUMN,
    attach_buildings_to_addresses,
    build_insured_land_extent,
    collapse_coincident_addresses,
)

# Two 10 m square buildings with a 10 m gap between them, so the 8 m buffers
# overlap across the middle 6 m of that gap. Small enough to work out by hand.
BUILDING_A = box(0, 0, 10, 10)
BUILDING_B = box(20, 0, 30, 10)

TOLERANCE_M2 = 1.0


def make_addresses(points, crs=constants.DEFAULT_CRS):
    """Build an address frame with one point per (address_id, x, y) triple."""
    return gpd.GeoDataFrame(
        {ADDRESS_ID_COLUMN: [address_id for address_id, _, _ in points]},
        geometry=[Point(x, y) for _, x, y in points],
        crs=crs,
    )


def make_buildings(geometries, crs=constants.DEFAULT_CRS):
    """Build a building frame from a list of polygons."""
    return gpd.GeoDataFrame(
        {"building_id": list(range(len(geometries)))},
        geometry=list(geometries),
        crs=crs,
    )


def test_one_building_gives_one_buffered_polygon():
    addresses = make_addresses([("a", 5, 5)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    assert list(extent[ADDRESS_ID_COLUMN]) == ["a"]
    assert list(extent[BUILDING_COUNT_COLUMN]) == [1]
    expected = BUILDING_A.buffer(INSURED_LAND_BUFFER_M).area
    assert extent[AREA_COLUMN].iloc[0] == pytest.approx(expected, abs=TOLERANCE_M2)


def test_two_buildings_on_one_address_dissolve_into_one_row():
    addresses = make_addresses([("a", 15, 5)])
    buildings = make_buildings([BUILDING_A, BUILDING_B])

    extent = build_insured_land_extent(addresses, buildings)

    assert len(extent) == 1
    assert extent[BUILDING_COUNT_COLUMN].iloc[0] == 2
    combined = (
        BUILDING_A.buffer(INSURED_LAND_BUFFER_M)
        .union(BUILDING_B.buffer(INSURED_LAND_BUFFER_M))
        .area
    )
    assert extent[AREA_COLUMN].iloc[0] == pytest.approx(combined, abs=TOLERANCE_M2)


def test_address_with_no_building_near_it_gets_no_extent():
    addresses = make_addresses([("a", 5, 5), ("vacant", 5000, 5000)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    assert list(extent[ADDRESS_ID_COLUMN]) == ["a"]


def test_neighbouring_extents_do_not_overlap_or_double_count():
    addresses = make_addresses([("a", 5, 5), ("b", 25, 5)])
    buildings = make_buildings([BUILDING_A, BUILDING_B])

    extent = build_insured_land_extent(addresses, buildings)

    assert len(extent) == 2

    first, second = extent.geometry.iloc[0], extent.geometry.iloc[1]
    assert first.intersection(second).area == pytest.approx(0.0, abs=1e-6)

    union = (
        BUILDING_A.buffer(INSURED_LAND_BUFFER_M)
        .union(BUILDING_B.buffer(INSURED_LAND_BUFFER_M))
        .area
    )
    assert extent[AREA_COLUMN].sum() == pytest.approx(union, abs=TOLERANCE_M2)

    # The shared strip is split by which building is nearer, and the two
    # buildings are mirror images about x = 15, so the halves match.
    assert extent[AREA_COLUMN].iloc[0] == pytest.approx(
        extent[AREA_COLUMN].iloc[1], abs=TOLERANCE_M2
    )


def test_a_row_of_properties_partitions_the_ground_between_them():
    # Nine houses on a grid, every one of them within the buffer distance of a
    # neighbour, which is the case the split is actually for.
    corners = [(x, y) for x in (0.0, 16.0, 32.0) for y in (0.0, 16.0, 32.0)]
    footprints = [box(x, y, x + 8, y + 8) for x, y in corners]
    addresses = make_addresses(
        [(f"a{index}", x + 4, y + 4) for index, (x, y) in enumerate(corners)]
    )
    buildings = make_buildings(footprints)

    extent = build_insured_land_extent(addresses, buildings)

    assert len(extent) == len(corners)

    covered = (
        gpd.GeoSeries(footprints, crs=constants.DEFAULT_CRS)
        .buffer(INSURED_LAND_BUFFER_M)
        .union_all()
    )
    assert extent[AREA_COLUMN].sum() == pytest.approx(covered.area, abs=TOLERANCE_M2)
    assert extent.geometry.union_all().area == pytest.approx(
        extent[AREA_COLUMN].sum(), abs=TOLERANCE_M2
    )


def test_each_address_keeps_the_ground_under_its_own_building():
    # A small building tucked inside its neighbour's buffer. The ground it
    # stands on is nearest to itself, so it keeps at least that much.
    small = box(11, 4, 13, 6)
    addresses = make_addresses([("a", 5, 5), ("small", 12, 5)])
    buildings = make_buildings([BUILDING_A, small])

    extent = build_insured_land_extent(addresses, buildings)

    assert set(extent[ADDRESS_ID_COLUMN]) == {"a", "small"}
    small_row = extent[extent[ADDRESS_ID_COLUMN] == "small"]
    assert small_row[AREA_COLUMN].iloc[0] >= small.area


def test_far_buildings_are_not_attached_to_an_address():
    addresses = make_addresses([("a", 5, 5)])
    buildings = make_buildings([BUILDING_A, box(5000, 5000, 5010, 5010)])

    attached = attach_buildings_to_addresses(buildings, addresses)

    assert list(attached[ADDRESS_ID_COLUMN]) == ["a"]


def test_no_buildings_gives_an_empty_extent():
    addresses = make_addresses([("a", 5, 5)])
    buildings = make_buildings([])

    extent = build_insured_land_extent(addresses, buildings)

    assert extent.empty
    assert AREA_COLUMN in extent.columns


def test_mismatched_crs_is_refused():
    addresses = make_addresses([("a", 5, 5)])
    buildings = make_buildings([BUILDING_A], crs="EPSG:2134")

    with pytest.raises(ValueError, match="Reproject"):
        build_insured_land_extent(addresses, buildings)


def test_geographic_crs_is_refused():
    addresses = make_addresses([("a", 174.8, -41.3)], crs="EPSG:4326")
    buildings = make_buildings([box(174.8, -41.3, 174.801, -41.299)], crs="EPSG:4326")

    with pytest.raises(ValueError, match="geographic"):
        build_insured_land_extent(addresses, buildings)


def test_missing_address_id_is_refused():
    addresses = gpd.GeoDataFrame(
        {"other": [1]}, geometry=[Point(5, 5)], crs=constants.DEFAULT_CRS
    )
    buildings = make_buildings([BUILDING_A])

    with pytest.raises(ValueError, match="address_id"):
        build_insured_land_extent(addresses, buildings)


def test_a_flat_on_the_same_outline_gets_its_share_of_the_ground():
    # The nearest-address pass gives the outline to one point and leaves the
    # other with nothing, which over the Wellington pilot lost 3,827 addresses
    # of 8,591. Both points stand on the building, so both are units in it.
    addresses = make_addresses([("front", 2, 5), ("back", 8, 5)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    assert sorted(extent[ADDRESS_ID_COLUMN]) == ["back", "front"]
    # The two shares are the whole buffer and nothing more: shared ground, not
    # ground invented for the second unit.
    alone = build_insured_land_extent(
        make_addresses([("front", 2, 5)]), make_buildings([BUILDING_A])
    )
    assert extent[AREA_COLUMN].sum() == pytest.approx(
        alone[AREA_COLUMN].sum(), abs=TOLERANCE_M2
    )
    assert extent.geometry.union_all().area == pytest.approx(
        extent[AREA_COLUMN].sum(), abs=TOLERANCE_M2
    )


def test_the_shares_of_one_outline_do_not_overlap():
    addresses = make_addresses([("front", 2, 5), ("back", 8, 5)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    first, second = extent.geometry.to_numpy()
    assert first.intersection(second).area == pytest.approx(0.0, abs=1e-6)


def test_a_vacant_section_beside_a_house_is_not_given_the_house_ground():
    # The point of the tight sharing tolerance. This address is well clear of
    # the outline, so it is a section rather than a unit, and attaching it would
    # hand it insured land it does not have.
    addresses = make_addresses([("house", 5, 5), ("vacant", 15, 5)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    assert list(extent[ADDRESS_ID_COLUMN]) == ["house"]


def test_addresses_at_one_point_become_one_property_with_a_dwelling_count():
    addresses = make_addresses([("unit_2", 5, 5), ("unit_1", 5, 5), ("far", 5, 5.5)])

    collapsed = collapse_coincident_addresses(addresses)

    # The lowest identifier represents the location, so which unit stands for a
    # block does not depend on the order they arrived in.
    assert sorted(collapsed[ADDRESS_ID_COLUMN]) == ["far", "unit_1"]
    counts = dict(
        zip(collapsed[ADDRESS_ID_COLUMN], collapsed[DWELLING_COUNT_COLUMN], strict=True)
    )
    assert counts == {"unit_1": 2, "far": 1}


def test_a_house_carries_one_dwelling():
    extent = build_insured_land_extent(
        make_addresses([("a", 5, 5)]), make_buildings([BUILDING_A])
    )
    assert list(extent[DWELLING_COUNT_COLUMN]) == [1]


def test_stacked_units_settle_as_one_property_carrying_both_dwellings():
    # Two addresses on the same coordinate cannot be separated by any geometry,
    # so they become one property. Left alone the second would hold nothing at
    # all, and its dwelling would vanish from the per-dwelling sub-caps.
    addresses = make_addresses([("unit_1", 5, 5), ("unit_2", 5, 5)])
    buildings = make_buildings([BUILDING_A])

    extent = build_insured_land_extent(addresses, buildings)

    assert list(extent[ADDRESS_ID_COLUMN]) == ["unit_1"]
    assert list(extent[DWELLING_COUNT_COLUMN]) == [2]


def test_the_linz_building_id_is_not_overwritten():
    # The LINZ outlines layer carries a building_id of its own, and several
    # outlines can belong to one building, so the row identity this module needs
    # has to be its own column.
    addresses = make_addresses([("a", 5, 5)])
    buildings = make_buildings([BUILDING_A])

    attached = attach_buildings_to_addresses(buildings, addresses)

    assert OUTLINE_ID_COLUMN in attached.columns
    assert list(attached["building_id"]) == list(buildings["building_id"])
