"""Run settings for the retaining wall landslide damage step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own.
"""

# Whether to run over the small Wellington pilot box. Must match the runs of
# every step this reads: the landslide hazard and the wall population.
PILOT = True

# Which modelled earthquakes to flag walls for.
REALISATION_IDS = [0]
