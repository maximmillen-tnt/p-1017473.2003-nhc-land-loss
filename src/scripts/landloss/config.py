"""Run settings for running the whole pipeline end to end.

`gen_all.py` beside this runs exposure, hazard and vul in that order, each
through its own `gen_<module>.py`. The two settings here override every
module's own, so the whole pipeline runs over one extent and one set of
realisations and ends at the tables the loss module reads.
"""

# Whether to run over the small Wellington pilot box rather than the four
# territorial authorities.
PILOT = True

# Which modelled earthquakes to run. The seed stream is shared across the
# hazards, so realisation 3 is the same earthquake in every module.
REALISATION_IDS = [0]
