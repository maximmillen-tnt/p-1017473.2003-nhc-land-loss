"""Loss: damage turned into what NHC would actually pay.

The last of the four modules, and the only one where money and policy wording
enter. That is deliberate: keeping the Act in one place is what makes the policy
settings a parameter of a run rather than something threaded through the model,
so comparing two sets of settings re-runs `loss` alone.

:mod:`landloss.loss.policy` holds a scenario's settings as a value, defaulting
to the Act as it stands. :mod:`landloss.loss.settlement` applies them, building
the land cover cap and settling each claim against it.

The module also owns more costing than its name suggests. `vul` emits a damage
state for retaining walls, culverts and bridges rather than a price, so every
dollar attached to a land structure is worked out here. See
``.agents/plans/asset-pricing-approach.md`` for how each asset is priced against
each hazard, and ``.agents/context/nhi-act-land-cover-explainer.md`` for the
settlement mechanics the arithmetic follows.
"""
