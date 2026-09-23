"""Run settings for the slope failure susceptibility step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own, so what a run did can be established by reading this file and the git
history of it rather than by remembering which flags were typed.

Both `gen_slope_susceptibility.py` and `fig_slope_susceptibility.py` read from
here, which is what keeps the figure drawing the rating the generator wrote.
"""

from landloss.hazard.landslide import susceptibility

# Whether to run over the Johnsonville and Newlands pilot rather than the whole
# extent the Wellington City earthworks records cover. Leave this True while the
# model is being changed: the pilot is 4 by 4 km against 11 by 21 km, and the
# fine elevation model is fetched over the whole extent either way.
#
# Note that this is not `SMALL_WLG_PILOT`, which the rest of the project
# develops against. That box sits over Mt Victoria and Hataitai and holds no
# earthworks polygons at all, so it cannot exercise the modification factor --
# which is half of what this step scores.
PILOT = True

# The cell size the rating is reported on, in metres. Slope is a property of the
# length it is measured over, and Kingsbury's class boundaries were calibrated
# against a terrain model built from 20 m contours at 1:25,000. Horn's kernel at
# 10 m measures gradient over about 20 to 30 m, so this is the closest available
# match to that calibration rather than a compromise for speed.
COARSE_RESOLUTION_M = 10

# The cell size the cut angle and face height are measured at, in metres. A cut
# face 10 m high at 50 degrees has a horizontal run of about 8 m: one cell at
# the coarse resolution, where it averages away to something like 20 degrees and
# the 45-60 and >60 classes become unreachable. At 1 m it is eight cells and
# resolves properly.
#
# Kingsbury did the same thing -- slope mapped at 1:25,000, cut slopes at
# 1:10,000 to 1:20,000 in urban areas -- so the two scales follow the source
# rather than departing from it.
FINE_RESOLUTION_M = 1

# The neighbourhood the height of a steep face is measured over, in metres. Wide
# enough to reach from the toe of a subdivision cut to its crest, narrow enough
# not to take in the hillside behind it. The height classes it feeds are 0-5,
# 5-10, 10-20 and over 20 m, so this has to span the top class to be able to
# report it at all.
SLOPE_HEIGHT_WINDOW_M = 50.0

# The three factors supplied as constants rather than mapped, with the class
# each is fixed at. All three are Kingsbury's own values from the Table 6 worked
# examples for moderate ground and above.
#
# Geology: the source says geology mattered least "because of the relative
# uniformity of bedrock type in the Region", with steep slopes "underlain by
# greywacke rock with a variable but generally thin (1 to 2 metre) surface layer
# of colluvium". Every worked example from moderate upwards scores it 10.
GEOLOGY_VALUE = susceptibility.GEOLOGY_COLLUVIUM_OR_ALLUVIUM

# Landslides: no inventory is held, so no cell can be told apart from any other.
# Zero is the honest value; it is not a statement that there are no landslides.
LANDSLIDE_VALUE = susceptibility.LANDSLIDES_NONE

# Groundwater: the source generalises this factor "to reflect extreme
# conditions, with maximum effects during prolonged heavy rainfall", and scores
# it 10 in all five worked examples.
GROUNDWATER_VALUE = susceptibility.GROUNDWATER_SATURATED

# Whether to reuse an already-fetched elevation model for this extent. Set False
# to fetch it again.
USE_CACHED_DEM = True
