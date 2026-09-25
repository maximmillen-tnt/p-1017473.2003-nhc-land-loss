"""Run settings for the multiscale slope step.

Everything that changes between one run of this step and the next, in one short
file. `gen_multiscale_slope.py` takes these as arguments and holds no defaults
of its own, so what a run did can be established by reading this file and the
git history of it rather than by remembering which flags were typed.
"""

# Whether to run over `SMALL_WLG_PILOT` rather than the four territorial
# authorities. The pilot fetch takes a minute or two; the full study area is
# 59 by 54 km and its 10 m fetch is a background job of tens of minutes.
PILOT = True

# The cell sizes to build a DEM and a slope at, in metres. The finest is fetched
# from LINZ and every other one is block-averaged from it, so each has to be a
# whole multiple of the finest.
RESOLUTIONS_M = (10, 30, 100)

# Whether to reuse an already-fetched elevation model for this extent. Set False
# to fetch it again.
USE_CACHED_DEM = True
