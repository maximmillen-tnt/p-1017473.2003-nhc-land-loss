"""Run settings for the liquefaction land damage step.

Everything that changes between one run of this step and the next, in one short
file. The scripts beside it take these as arguments and hold no defaults of
their own, so what a run did can be established by reading this file and the git
history of it, rather than by remembering which flags were typed.
"""

# Whether to run over the small Wellington pilot box. Must match the runs of the
# liquefaction hazard and the insured land extent this reads.
PILOT = True

# Which modelled earthquakes to price.
REALISATION_IDS = [0]

# Which percentile of the settled Canterbury costs to run at. A **scenario, not
# a distribution**: the 15th, 50th and 85th are the spread of settled costs
# between properties assessed at the same damage state, and the 85th runs two to
# four times the median. The model is run once per value and the three portfolio
# totals reported as a cost-assumption band, rather than the percentile riding
# as a column, because min(repair, cap) is non-linear -- a settlement computed
# from a median cost is not the median settlement.
COST_PERCENTILE = 50
