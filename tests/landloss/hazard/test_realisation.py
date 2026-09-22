import numpy as np
import pytest

from landloss.hazard.realisation import realisation_seed, stream_entropy

BASE = 1017473


def draws(base, realisation_id, stream, n=8):
    return realisation_seed(base, realisation_id, stream).random(n)


def test_the_same_three_inputs_always_give_the_same_draws():
    assert np.array_equal(
        draws(BASE, 0, "liquefaction"), draws(BASE, 0, "liquefaction")
    )


def test_a_stream_name_hashes_the_same_in_every_process():
    # Not Python's salted hash(), or a run would not reproduce tomorrow.
    assert stream_entropy("liquefaction") == stream_entropy("liquefaction")
    assert stream_entropy("liquefaction") != stream_entropy("landslide")


def test_two_hazards_in_one_realisation_draw_different_numbers():
    assert not np.array_equal(draws(BASE, 0, "shaking"), draws(BASE, 0, "landslide"))


def test_two_realisations_of_one_hazard_draw_different_numbers():
    assert not np.array_equal(draws(BASE, 0, "shaking"), draws(BASE, 1, "shaking"))


def test_adding_a_stream_does_not_shift_an_existing_one():
    # The property that keeps last week's run reproducible when a fourth hazard
    # is added: a stream's name only ever feeds its own sequence.
    before = draws(BASE, 3, "shaking")
    draws(BASE, 3, "a-hazard-invented-later")
    assert np.array_equal(before, draws(BASE, 3, "shaking"))


def test_a_negative_realisation_is_refused():
    with pytest.raises(ValueError, match="zero or more"):
        realisation_seed(BASE, -1, "shaking")


def test_an_unnamed_stream_is_refused():
    with pytest.raises(ValueError, match="non-empty"):
        realisation_seed(BASE, 0, "")
