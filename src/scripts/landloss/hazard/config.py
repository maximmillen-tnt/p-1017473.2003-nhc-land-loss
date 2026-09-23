"""Run settings for running the whole hazard module end to end.

`gen_hazard.py` beside this runs every step of the module in order. The two
settings here override each step's own `config.py`, so the whole module runs
over one extent and one set of realisations. Everything else a step reads, such
as whether to reuse a cached elevation model, still comes from that step's own
`config.py`.
"""

# Whether to run over the small Wellington pilot box rather than the four
# territorial authorities.
PILOT = True

# Which modelled earthquakes to run. The seed stream is shared across the
# hazards, so realisation 3 is the same earthquake in every module.
REALISATION_IDS = [0]
