"""Named study extents the models are run over.

An area of interest is held in WGS84, because that is how extents get quoted and
compared between people, and converted to whatever CRS the caller works in on
demand. Keeping the definition in one place means an extent is never re-typed
from a map into a script.
"""

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry import Polygon, box

from landloss.domain.constants import DEFAULT_CRS

WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class AreaOfInterest:
    """A named rectangular study extent, defined in WGS84.

    Attributes:
        name: A human readable name, used in outputs and file names.
        west: Western boundary, as a WGS84 longitude.
        south: Southern boundary, as a WGS84 latitude.
        east: Eastern boundary, as a WGS84 longitude.
        north: Northern boundary, as a WGS84 latitude.
    """

    name: str
    west: float
    south: float
    east: float
    north: float

    def bbox(self, crs: int | str = DEFAULT_CRS) -> tuple[float, float, float, float]:
        """Return the extent as (minx, miny, maxx, maxy) in the given CRS.

        Args:
            crs: The coordinate reference system to express the extent in.

        Returns:
            The bounding box, ready to pass to a reader.
        """
        bounds = self.to_geoseries(crs).total_bounds
        minx, miny, maxx, maxy = (float(value) for value in bounds)
        return (minx, miny, maxx, maxy)

    def polygon(self, crs: int | str = DEFAULT_CRS) -> Polygon:
        """Return the extent as a polygon in the given CRS."""
        return self.to_geoseries(crs).iloc[0]

    def to_geoseries(self, crs: int | str = DEFAULT_CRS) -> gpd.GeoSeries:
        """Return the extent as a single-element GeoSeries in the given CRS."""
        return gpd.GeoSeries(
            [box(self.west, self.south, self.east, self.north)], crs=WGS84
        ).to_crs(crs)


# A small pilot area in Wellington, used to exercise the workflow end to end
# before it is run over the full study area.
SMALL_WLG_PILOT = AreaOfInterest(
    name="Small Wellington pilot",
    west=174.772318,
    south=-41.32486560367306,
    east=174.80616774743507,
    north=-41.309796,
)
