"""Run settings for the property damage join.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own.

Nothing here selects a cost or a fragility. This step joins what the hazard
steps already decided and adds no modelling of its own, so the only settings are
which run to join.
"""

# Whether to run over the small Wellington pilot box. Must match the runs of
# every step this reads.
PILOT = True

# Which modelled earthquakes to join.
REALISATION_IDS = [0]
