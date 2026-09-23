import geopandas as gpd
import pytest
from shapely.geometry import GeometryCollection, LineString, Point, box

from landloss.vul.landslide.flags import landslide_flags
from landloss.vul.landslide.land.damaged_area import EVACUATED, INUNDATED

CRS = "EPSG:2193"


def assets(*ids_and_geoms, crs=CRS):
    ids = [asset_id for asset_id, _ in ids_and_geoms]
    geoms = [geom for _, geom in ids_and_geoms]
    return gpd.GeoDataFrame({"rw_id": ids}, geometry=geoms, crs=crs)


def slides(*classes_and_geoms, crs=CRS):
    classes = [land_class for land_class, _ in classes_and_geoms]
    geoms = [geom for _, geom in classes_and_geoms]
    return gpd.GeoDataFrame({"land_class": classes}, geometry=geoms, crs=crs)


EVACUATED_CIRCLE = (EVACUATED, Point(0, 0).buffer(10))
INUNDATED_CIRCLE = (INUNDATED, Point(100, 0).buffer(10))


def test_a_line_crossing_evacuated_ground_is_evacuated():
    walls = assets(("A-RW01", LineString([(-20, 0), (20, 0)])))
    flags = landslide_flags(walls, slides(EVACUATED_CIRCLE), id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [True]
    assert flags["is_inundated"].tolist() == [False]


def test_a_line_crossing_inundated_ground_is_inundated():
    walls = assets(("A-RW01", LineString([(80, 0), (120, 0)])))
    flags = landslide_flags(walls, slides(INUNDATED_CIRCLE), id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [False]
    assert flags["is_inundated"].tolist() == [True]


def test_a_line_through_both_kinds_of_ground_carries_both_flags():
    walls = assets(("A-RW01", LineString([(-20, 0), (120, 0)])))
    hazard = slides(EVACUATED_CIRCLE, INUNDATED_CIRCLE)
    flags = landslide_flags(walls, hazard, id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [True]
    assert flags["is_inundated"].tolist() == [True]


def test_an_asset_clear_of_every_landslide_carries_neither_flag():
    walls = assets(("A-RW01", LineString([(40, 50), (60, 50)])))
    hazard = slides(EVACUATED_CIRCLE, INUNDATED_CIRCLE)
    flags = landslide_flags(walls, hazard, id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [False]
    assert flags["is_inundated"].tolist() == [False]


def test_polygon_and_collection_assets_are_flagged():
    crossings = assets(
        ("A-X01", box(-5, -5, 5, 5)),
        (
            "B-X01",
            GeometryCollection([LineString([(90, 0), (110, 0)]), box(0, 50, 1, 51)]),
        ),
    )
    hazard = slides(EVACUATED_CIRCLE, INUNDATED_CIRCLE)
    flags = landslide_flags(crossings, hazard, id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [True, False]
    assert flags["is_inundated"].tolist() == [False, True]


def test_no_landslides_leaves_every_asset_unflagged():
    walls = assets(("A-RW01", LineString([(-20, 0), (20, 0)])))
    flags = landslide_flags(walls, slides(), id_column="rw_id")
    assert flags["is_evacuated"].tolist() == [False]
    assert flags["is_inundated"].tolist() == [False]


def test_no_assets_gives_an_empty_frame_with_boolean_flags():
    flags = landslide_flags(assets(), slides(EVACUATED_CIRCLE), id_column="rw_id")
    assert flags.empty
    assert list(flags.columns) == ["rw_id", "is_evacuated", "is_inundated"]
    assert flags["is_evacuated"].dtype == bool
    assert flags["is_inundated"].dtype == bool


def test_a_crs_mismatch_is_refused():
    walls = assets(("A-RW01", LineString([(-20, 0), (20, 0)])))
    with pytest.raises(ValueError, match="landslides are"):
        landslide_flags(
            walls, slides(EVACUATED_CIRCLE, crs="EPSG:3857"), id_column="rw_id"
        )


def test_repeated_ids_are_refused():
    walls = assets(
        ("A-RW01", LineString([(-20, 0), (20, 0)])),
        ("A-RW01", LineString([(40, 50), (60, 50)])),
    )
    with pytest.raises(ValueError, match="repeat"):
        landslide_flags(walls, slides(EVACUATED_CIRCLE), id_column="rw_id")


def test_landslides_without_a_land_class_are_refused():
    walls = assets(("A-RW01", LineString([(-20, 0), (20, 0)])))
    hazard = slides(EVACUATED_CIRCLE).drop(columns="land_class")
    with pytest.raises(ValueError, match="land_class"):
        landslide_flags(walls, hazard, id_column="rw_id")


def test_the_output_follows_the_input_order():
    walls = assets(
        ("C-RW01", LineString([(40, 50), (60, 50)])),
        ("A-RW01", LineString([(80, 0), (120, 0)])),
        ("B-RW01", LineString([(-20, 0), (20, 0)])),
    )
    hazard = slides(EVACUATED_CIRCLE, INUNDATED_CIRCLE)
    flags = landslide_flags(walls, hazard, id_column="rw_id")
    assert flags["rw_id"].tolist() == ["C-RW01", "A-RW01", "B-RW01"]
    assert flags["is_evacuated"].tolist() == [False, False, True]
    assert flags["is_inundated"].tolist() == [False, True, False]
