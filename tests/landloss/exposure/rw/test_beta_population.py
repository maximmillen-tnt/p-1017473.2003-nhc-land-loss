import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point

from landloss.exposure.rw.beta_population import (
    BETA_MAX_PREVALENCE,
    BETA_MIN_SLOPE_DEG,
    MEDIUM_MAX_HEIGHT_M,
    SIZE_CLASSES,
    SMALL_MAX_HEIGHT_M,
    beta_wall_height_m,
    beta_wall_population,
    beta_wall_prevalence,
    classify_wall_size,
    wall_lines,
)
from landloss.hazard.realisation import realisation_seed


def rng():
    return realisation_seed(1, 0, "exposure")


def properties(n=400, slope=20.0, azimuth=90.0, area=400.0):
    return gpd.GeoDataFrame(
        {
            "address_id": [f"A-{i:04d}" for i in range(n)],
            "slope_deg": np.full(n, slope),
            "downhill_azimuth_deg": np.full(n, azimuth),
            "area_m2": np.full(n, area),
        },
        geometry=[Point(1_750_000 + i, 5_424_000) for i in range(n)],
        crs="EPSG:2193",
    )


# --- prevalence and height ---------------------------------------------------


def test_flat_ground_carries_no_walls():
    assert beta_wall_prevalence(0.0) == pytest.approx(0.0)
    assert beta_wall_prevalence(BETA_MIN_SLOPE_DEG) == pytest.approx(0.0)


def test_prevalence_rises_with_slope_and_is_capped():
    assert beta_wall_prevalence(10.0) > beta_wall_prevalence(5.0)
    assert beta_wall_prevalence(80.0) == pytest.approx(BETA_MAX_PREVALENCE)


def test_a_steeper_property_gets_a_taller_wall():
    assert beta_wall_height_m(20.0) > beta_wall_height_m(5.0)


def test_height_is_bounded_however_steep_the_ground():
    assert beta_wall_height_m(89.0) == pytest.approx(beta_wall_height_m(25.0))


# --- size classes ------------------------------------------------------------


def test_the_size_classes_split_on_the_agreed_heights():
    classes = classify_wall_size(
        np.array([0.5, SMALL_MAX_HEIGHT_M, 2.0, MEDIUM_MAX_HEIGHT_M, 4.0])
    )
    assert list(classes) == ["small", "medium", "medium", "large", "large"]


def test_every_class_is_one_of_the_three():
    classes = classify_wall_size(np.linspace(0.1, 6.0, 50))
    assert set(classes) <= set(SIZE_CLASSES)


# --- geometry ----------------------------------------------------------------


def test_a_wall_lies_across_the_slope_not_down_it():
    # Downhill due east, so the wall runs north-south.
    points = gpd.GeoSeries([Point(0.0, 0.0)], crs="EPSG:2193")
    line = wall_lines(points, np.array([90.0]), np.array([10.0])).iloc[0]
    (x0, y0), (x1, y1) = line.coords
    assert x1 - x0 == pytest.approx(0.0, abs=1e-9)
    assert abs(y1 - y0) == pytest.approx(10.0)


def test_a_wall_is_the_length_it_was_given():
    points = gpd.GeoSeries([Point(0.0, 0.0)], crs="EPSG:2193")
    line = wall_lines(points, np.array([37.0]), np.array([14.0])).iloc[0]
    assert line.length == pytest.approx(14.0)


def test_a_wall_is_centred_on_its_property():
    points = gpd.GeoSeries([Point(5.0, 7.0)], crs="EPSG:2193")
    line = wall_lines(points, np.array([0.0]), np.array([8.0])).iloc[0]
    assert line.centroid.x == pytest.approx(5.0)
    assert line.centroid.y == pytest.approx(7.0)


def test_mismatched_inputs_are_refused():
    points = gpd.GeoSeries([Point(0.0, 0.0)], crs="EPSG:2193")
    with pytest.raises(ValueError, match="must match"):
        wall_lines(points, np.array([0.0, 90.0]), np.array([8.0]))


# --- the population ----------------------------------------------------------


def test_the_share_of_properties_with_a_wall_tracks_the_prevalence():
    addresses = properties(n=4000, slope=20.0)
    walls = beta_wall_population(addresses, rng())
    expected = beta_wall_prevalence(20.0)
    assert walls["address_id"].nunique() == len(walls)
    assert abs(len(walls) / len(addresses) - expected) < 0.03


def test_flat_properties_draw_no_walls_at_all():
    assert beta_wall_population(properties(slope=0.0), rng()).empty


def test_a_property_with_no_slope_sampled_draws_nothing():
    addresses = properties(n=200, slope=20.0)
    addresses.loc[:, "slope_deg"] = np.nan
    assert beta_wall_population(addresses, rng()).empty


def test_the_population_carries_the_columns_the_chain_reads():
    walls = beta_wall_population(properties(), rng())
    for column in ("address_id", "size_class", "initial_condition", "height_m"):
        assert column in walls.columns
    assert walls.geometry.geom_type.eq("LineString").all()
    assert walls.crs == "EPSG:2193"


def test_the_same_realisation_draws_the_same_population():
    first = beta_wall_population(properties(), rng())
    second = beta_wall_population(properties(), rng())
    assert first["address_id"].tolist() == second["address_id"].tolist()
    assert first["initial_condition"].tolist() == second["initial_condition"].tolist()


def test_a_missing_column_is_refused():
    addresses = properties().drop(columns=["area_m2"])
    with pytest.raises(ValueError, match="area_m2"):
        beta_wall_population(addresses, rng())
