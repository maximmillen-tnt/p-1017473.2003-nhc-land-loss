import geopandas as gpd
import pytest
from shapely.geometry import LineString, box

from landloss.exposure.culverts_bridges.crossings import (
    CULVERT_PROBABILITY,
    FROM_LINES,
    FROM_POLYGONS,
    STRUCTURES,
    describe_crossings,
    detect_crossings,
    sample_structures,
)
from landloss.hazard.realisation import realisation_seed

CRS = "EPSG:2193"


def rng():
    return realisation_seed(1, 0, "exposure")


def accessway(x=0.0, address="A-001"):
    """A driveway corridor running north-south through y = 0."""
    return gpd.GeoDataFrame(
        {"address_id": [address]}, geometry=[box(x - 1.5, -20, x + 1.5, 20)], crs=CRS
    )


def stream(y=0.0, reach=50.0):
    """A watercourse centreline running east-west.

    ``reach`` has to span every accessway a test means to cross it; a stream
    shorter than the row of driveways silently shrinks the sample.
    """
    return gpd.GeoDataFrame(
        {"name": ["Te Awa"]},
        geometry=[LineString([(-reach, y), (reach, y)])],
        crs=CRS,
    )


def river(y=0.0, half_width=5.0):
    """A wider river carried as an areal extent."""
    return gpd.GeoDataFrame(
        {"name": ["Awa Nui"]},
        geometry=[box(-50, y - half_width, 50, y + half_width)],
        crs=CRS,
    )


def nothing(geometry="line"):
    return gpd.GeoDataFrame({"name": []}, geometry=gpd.GeoSeries([], crs=CRS), crs=CRS)


# --- detection ---------------------------------------------------------------


def test_an_accessway_over_a_stream_is_a_crossing():
    found = detect_crossings(accessway(), stream(), nothing())
    assert len(found) == 1
    assert found["address_id"].iloc[0] == "A-001"
    assert found["watercourse_source"].iloc[0] == FROM_LINES


def test_an_accessway_that_crosses_nothing_finds_nothing():
    # The stream runs well north of the corridor's end.
    assert detect_crossings(accessway(), stream(y=500.0), nothing()).empty


def test_a_wide_river_is_found_on_the_polygon_layer():
    found = detect_crossings(accessway(), nothing(), river())
    assert len(found) == 1
    assert found["watercourse_source"].iloc[0] == FROM_POLYGONS


def test_reading_both_layers_finds_what_the_lines_alone_would_miss():
    # The river has an areal extent but no centreline in this fixture, which is
    # the case the second layer exists for.
    lines_only = detect_crossings(accessway(), nothing(), nothing())
    both = detect_crossings(accessway(), nothing(), river())
    assert lines_only.empty
    assert len(both) == 1


def test_the_crossing_is_the_part_on_the_water_not_the_whole_accessway():
    found = detect_crossings(accessway(), nothing(), river(half_width=5.0))
    # The corridor is 3 m wide and the river 10 m deep, so the overlap is 30 m2
    # rather than the corridor's full 120 m2.
    assert found.geometry.iloc[0].area == pytest.approx(30.0)


def test_each_property_keeps_its_own_crossing():
    ways = gpd.GeoDataFrame(
        {"address_id": ["A-001", "A-002"]},
        geometry=[box(-1.5, -20, 1.5, 20), box(8.5, -20, 11.5, 20)],
        crs=CRS,
    )
    found = detect_crossings(ways, stream(), nothing())
    assert sorted(found["address_id"]) == ["A-001", "A-002"]


def test_a_crs_mismatch_is_refused():
    with pytest.raises(ValueError, match="accessways are"):
        detect_crossings(accessway(), stream().to_crs("EPSG:4326"), nothing())


def test_accessways_without_an_identifier_are_refused():
    with pytest.raises(ValueError, match="address_id"):
        detect_crossings(accessway().drop(columns=["address_id"]), stream(), nothing())


# --- the structure draw ------------------------------------------------------


def test_every_crossing_takes_a_culvert_or_a_bridge():
    ways = gpd.GeoDataFrame(
        {"address_id": [f"A-{i:03d}" for i in range(400)]},
        geometry=[box(4 * i - 1.5, -20, 4 * i + 1.5, 20) for i in range(400)],
        crs=CRS,
    )
    found = sample_structures(
        detect_crossings(ways, stream(reach=2000.0), nothing()), rng()
    )
    assert set(found["structure"]) <= set(STRUCTURES)
    assert found["structure"].notna().all()


def test_the_split_tracks_the_culvert_probability():
    ways = gpd.GeoDataFrame(
        {"address_id": [f"A-{i:04d}" for i in range(2000)]},
        geometry=[box(4 * i - 1.5, -20, 4 * i + 1.5, 20) for i in range(2000)],
        crs=CRS,
    )
    found = sample_structures(
        detect_crossings(ways, stream(reach=9000.0), nothing()), rng()
    )
    assert len(found) == len(ways)
    share = (found["structure"] == "culvert").mean()
    assert abs(share - CULVERT_PROBABILITY) < 0.03


def test_the_same_realisation_draws_the_same_structures():
    crossings = detect_crossings(accessway(), stream(), nothing())
    first = sample_structures(crossings, rng())
    second = sample_structures(crossings, rng())
    assert first["structure"].tolist() == second["structure"].tolist()


def test_no_crossings_draws_nothing():
    empty = detect_crossings(accessway(), stream(y=500.0), nothing())
    assert sample_structures(empty, rng()).empty


# --- reporting ---------------------------------------------------------------


def test_the_summary_counts_both_structures_and_both_layers():
    crossings = sample_structures(
        detect_crossings(accessway(), stream(), river(y=12.0)), rng()
    )
    summary = describe_crossings(crossings, accessways=1)
    assert summary["crossings found"] == 2
    assert summary["found on lines"] == 1
    assert summary["found on polygons"] == 1
