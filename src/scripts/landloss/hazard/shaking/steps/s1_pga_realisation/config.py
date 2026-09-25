"""Run settings for the PGA realisation step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own, so what a run did can be established by reading this file and the git
history of it, rather than by remembering which flags were typed.

The 10% coefficient of variation is not here. It is the beta's stand-in for the
ground motion model's own sigma rather than a setting of a run, so it lives with
the code that applies it, as
`landloss.hazard.shaking.pga.BETA_PGA_COV`.
"""

# Whether to clip to the small Wellington pilot box rather than the four
# territorial authorities.
PILOT = True

# Which modelled earthquakes to draw. A realisation id is the whole event: the
# same id in the shaking, liquefaction and landslide layers is the same
# earthquake.
REALISATION_IDS = [0]
