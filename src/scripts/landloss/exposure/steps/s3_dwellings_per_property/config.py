"""Run settings for the dwellings per property step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own.
"""

# Whether to run over the small Wellington pilot box. Must match the run of the
# land value step this reads its addresses from.
PILOT = True

# Whether to reuse already-fetched LINZ layers for this extent.
USE_CACHED_EXTENT = True
