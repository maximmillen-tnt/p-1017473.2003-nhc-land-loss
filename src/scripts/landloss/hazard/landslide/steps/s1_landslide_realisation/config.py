"""Run settings for the landslide realisation step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own, so what a run did can be established by reading this file and the
git history of it, rather than by remembering which flags were typed.

Both `s1_simulate_landslides.py` and `fig_landslide_realisation.py` read from
here, which is what keeps the figure drawing the realisation the simulation
actually wrote.
"""

# Whether to run over the small Wellington pilot box rather than the four
# territorial authorities. Leave this True while the model is being changed: the
# pilot is 2.9 by 1.7 km against 59 by 54 km, and assembling the elevation model
# over the full extent is a long fetch.
PILOT = True

# Which modelled earthquakes to draw. A realisation id is the whole event: the
# same id in the shaking, liquefaction and landslide layers is the same
# earthquake, which is what lets a property's causes be summed. The seed itself
# is project-wide -- landloss.domain.constants.BASE_SEED -- and this step does
# not carry one of its own, because two hazards seeded separately could not be
# paired.
REALISATION_IDS = [0]

# Whether to reuse an already-fetched elevation model for this extent. Set False
# to fetch it again.
USE_CACHED_DEM = True
