"""Tests for reading the National Liquefaction Model's scenario release rasters.

Every raster here is written to ``tmp_path`` by the test that reads it, and the
resolver that would go to the T: drive is replaced. Nothing touches the network
or the network drive.
"""

import numpy as np
import pytest
import rioxarray  # noqa: F401  # registers the .rio accessor
import xarray as xr

from landloss.io import nlm

pytestmark = pytest.mark.filterwarnings(
    "ignore:Use `@` matmul:PendingDeprecationWarning"
)


def write_raster(path, values, nodata=None):
    """Write an array to a GeoTIFF, and return its path."""
    values = np.asarray(values, dtype=float)
    rows, columns = values.shape
    raster = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={
            "y": np.arange(rows)[::-1].astype(float),
            "x": np.arange(columns).astype(float),
        },
    ).rio.write_crs("EPSG:2193")

    if nodata is not None:
        raster = raster.rio.write_nodata(nodata)

    raster.rio.to_raster(path)
    return path


@pytest.fixture
def released(monkeypatch):
    """Return a function that stands a written raster in for one on the T: drive."""

    def use(path):
        monkeypatch.setattr(nlm, "nlm_release_path", lambda *_, **__: path)
        return path

    return use


def test_a_scenario_raster_comes_back_on_its_own_grid(tmp_path, released) -> None:
    """The plain case, so every failure below is about the handling, not the read."""
    values = np.arange(12, dtype=float).reshape(3, 4)
    released(write_raster(tmp_path / "grid.tif", values))

    raster = nlm.get_nlm_scenario_raster("whatever.tif")

    assert tuple(raster.dims) == ("y", "x")
    assert raster.to_numpy() == pytest.approx(values)


def test_the_nodata_marker_arrives_as_nan_rather_than_as_a_number(
    tmp_path, released
) -> None:
    """A -9999 left in place is the commonest way a raster quietly poisons a model."""
    values = np.full((3, 4), 0.25)
    values[1, 1] = -9999.0
    released(write_raster(tmp_path / "grid.tif", values, nodata=-9999.0))

    raster = nlm.get_nlm_scenario_raster("whatever.tif")

    assert np.isnan(raster.to_numpy()[1, 1])
    assert raster.to_numpy()[0, 0] == pytest.approx(0.25)


def test_the_rp2500y_helper_reads_its_hardcoded_path(tmp_path, monkeypatch) -> None:
    """The path is a constant precisely so that nobody retypes it into a script."""
    path = write_raster(tmp_path / "rp2500y.tif", np.full((4, 4), 0.01))
    asked_for = []

    def record(relative_path, **_):
        asked_for.append(relative_path)
        return path

    monkeypatch.setattr(nlm, "nlm_release_path", record)

    raster = nlm.get_nlm_scenario_rp2500y_gwd_med_p_ld_moderate_fu()

    assert asked_for == [
        (
            f"core/{nlm.CORE_NLM_VERSION}/scenario/return_period/"
            "rp2500y_lsn_pl50_gwd-med_p_ld_moderate_fu.tif"
        )
    ]
    assert raster.to_numpy() == pytest.approx(0.01)


def test_nlm_release_path_appends_the_relative_path_and_caches(
    tmp_path, monkeypatch
) -> None:
    """nlm_release_path builds NLM_RELEASES_DIR / relative_path and caches it."""
    asked_for = []

    def record(path, **_):
        asked_for.append(path)
        return tmp_path / "cached.tif"

    monkeypatch.setattr("tdrive_sync.get_cached", record)

    result = nlm.nlm_release_path("core/v1/scenario/grid.tif")

    assert asked_for == [nlm.NLM_RELEASES_DIR / "core/v1/scenario/grid.tif"]
    assert result == tmp_path / "cached.tif"
