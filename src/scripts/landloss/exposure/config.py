"""Run settings for running the whole exposure module end to end.

`gen_exposure.py` beside this runs every step of the module in order. The two
settings here override each step's own `config.py`, so the whole module runs
over one extent and one set of realisations. Everything else a step reads, such
as whether to reuse a cached download, still comes from that step's own
`config.py`.
"""

# Whether to run over the small Wellington pilot box rather than the four
# territorial authorities.
PILOT = True

# Which modelled earthquakes to run. The retaining wall and crossing
# populations are drawn per realisation under the shared seed stream.
REALISATION_IDS = [0]
