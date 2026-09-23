"""Whether a land structure survives the shaking, or is written off.

Retaining walls, culverts and bridges carry **two damage states: no damage, and
replace**. Repair is not modelled, because very few damaged walls are repaired
in practice, so a third state would carry almost nothing.

A fragility is therefore a **curve returning the probability of failure at a
given ground motion**, and a damage state is a draw against that probability.
The probability is what a fragility is: nominally identical structures differ in
capacity, and any one of them responds variably to the same intensity, so the
curve is the distribution of that difference rather than a capacity to compare
against. It stays a probability however well the hazard is resolved.

(Separately, the shaking field is currently flat -- a realisation scales one
coarse PGA grid by a single factor, so every asset reads the same acceleration
until the Vs30 model drives the site class. That is a limitation of the hazard
input, not a reason for anything here.)

:func:`draw_damage_states` takes probabilities rather than computing them, so
the published fragility curves drop in without it changing.
:data:`BETA_FAILURE_PROBABILITY` is the beta's stand-in until they do: one flat
probability for every structure, whatever its size, condition or the ground
motion it saw -- a fragility curve flattened to a constant, not a different kind
of thing.
"""

import numpy as np

NO_DAMAGE = "no damage"
REPLACE = "replace"
DAMAGE_STATES = (NO_DAMAGE, REPLACE)

DAMAGE_STATE_COLUMN = "damage_state"

# The beta's stand-in for a fragility curve: every structure fails with this
# probability, regardless of what it is, what condition it is in or how hard the
# ground shook. Replaced by the published curves, at which point the probability
# becomes a function of the asset and its PGA rather than a constant.
BETA_FAILURE_PROBABILITY = 0.7


def beta_failure_probability(count: int) -> np.ndarray:
    """Return the beta's flat failure probability for a set of structures.

    Args:
        count: How many structures to return a probability for.

    Returns:
        An array of :data:`BETA_FAILURE_PROBABILITY`.

    Raises:
        ValueError: If the count is negative.
    """
    if count < 0:
        msg = f"count must not be negative, got {count}"
        raise ValueError(msg)
    return np.full(count, BETA_FAILURE_PROBABILITY)


def draw_damage_states(
    failure_probability: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw a damage state per structure against its failure probability.

    Args:
        failure_probability: The probability each structure fails, 0 to 1.
        rng: The generator for this realisation's vulnerability stream.

    Returns:
        :data:`NO_DAMAGE` or :data:`REPLACE` per structure.

    Raises:
        ValueError: If a probability falls outside 0 to 1.
    """
    probability = np.asarray(failure_probability, dtype=float)
    if probability.size and (np.nanmin(probability) < 0 or np.nanmax(probability) > 1):
        msg = "failure probabilities must lie between 0 and 1"
        raise ValueError(msg)
    fails = rng.random(probability.shape) < probability
    return np.where(fails, REPLACE, NO_DAMAGE)
