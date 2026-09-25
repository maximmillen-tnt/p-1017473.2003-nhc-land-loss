import numpy as np
import pytest

from landloss.hazard.realisation import realisation_seed
from landloss.vul.shaking.fragility import (
    BETA_FAILURE_PROBABILITY,
    DAMAGE_STATES,
    NO_DAMAGE,
    REPLACE,
    beta_failure_probability,
    draw_damage_states,
)


def rng(realisation_id=0):
    return realisation_seed(1, realisation_id, "vulnerability")


def test_the_beta_probability_is_flat_across_every_structure():
    assert np.all(beta_failure_probability(50) == BETA_FAILURE_PROBABILITY)


def test_a_state_is_always_one_of_the_two():
    states = draw_damage_states(beta_failure_probability(500), rng())
    assert set(states) <= set(DAMAGE_STATES)


def test_the_share_replaced_tracks_the_probability():
    states = draw_damage_states(beta_failure_probability(5000), rng())
    share = (states == REPLACE).mean()
    assert abs(share - BETA_FAILURE_PROBABILITY) < 0.02


def test_certain_failure_replaces_everything():
    assert np.all(draw_damage_states(np.ones(100), rng()) == REPLACE)


def test_certain_survival_replaces_nothing():
    assert np.all(draw_damage_states(np.zeros(100), rng()) == NO_DAMAGE)


def test_assets_differ_within_one_realisation():
    # The point of drawing rather than thresholding: every asset reads the same
    # PGA, so without the draw the portfolio would be all or nothing.
    states = draw_damage_states(beta_failure_probability(200), rng())
    assert NO_DAMAGE in states
    assert REPLACE in states


def test_the_same_realisation_draws_the_same_states():
    first = draw_damage_states(beta_failure_probability(100), rng(2))
    second = draw_damage_states(beta_failure_probability(100), rng(2))
    assert np.array_equal(first, second)


def test_two_realisations_draw_differently():
    first = draw_damage_states(beta_failure_probability(200), rng(0))
    second = draw_damage_states(beta_failure_probability(200), rng(1))
    assert not np.array_equal(first, second)


def test_no_structures_draws_nothing():
    assert draw_damage_states(beta_failure_probability(0), rng()).size == 0


def test_a_probability_outside_zero_to_one_is_refused():
    with pytest.raises(ValueError, match="between 0 and 1"):
        draw_damage_states(np.array([1.5]), rng())


def test_a_negative_count_is_refused():
    with pytest.raises(ValueError, match="must not be negative"):
        beta_failure_probability(-1)
