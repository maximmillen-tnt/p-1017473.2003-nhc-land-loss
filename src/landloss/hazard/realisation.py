"""Random number streams for a realisation, shared across the hazards.

A realisation is **one modelled earthquake**. The same event shakes a property,
liquefies the ground under it and drops a hillside onto it, so a claim's causes
can only be summed if every hazard layer carrying a realisation's id belongs to
that one event.

That means the seeding cannot be per script. If each step seeded itself, two
steps would either share a stream -- and so draw correlated numbers for no
reason -- or drift apart the moment one of them was re-run. Instead every stream
is derived from one project seed, the realisation id, and a name for the stream:

    rng = realisation_seed(BASE_SEED, realisation_id=0, stream="liquefaction")

The three properties that buys are the ones an ensemble needs:

- **Reproducible.** The same three inputs always give the same draws, whatever
  order the steps are run in and whatever else has been run first.
- **Independent.** ``SeedSequence`` spreads its entropy, so two streams from the
  same realisation are uncorrelated rather than merely different.
- **Stable under addition.** Adding a fourth hazard does not shift the numbers
  the other three draw, because a stream's name only ever feeds its own
  sequence. A run from last week stays reproducible.

Use one stream name per hazard, not per script: a hazard's steps belong to the
same draw.
"""

import hashlib

import numpy as np

# The stream name is hashed to an integer rather than passed through Python's
# hash(), which is salted per process and so would break reproducibility between
# runs. Truncated to 8 bytes, which is far more room than a handful of names
# needs and keeps the entropy tuple readable when it is printed.
_STREAM_DIGEST_BYTES = 8


def stream_entropy(stream: str) -> int:
    """Return a stable integer for a stream name.

    Args:
        stream: The name of the stream, e.g. ``"liquefaction"``.

    Returns:
        A non-negative integer, the same in every process and every run.

    Raises:
        ValueError: If the stream name is empty.
    """
    if not stream:
        msg = "stream must be a non-empty name, e.g. 'liquefaction'"
        raise ValueError(msg)
    digest = hashlib.sha256(stream.encode("utf-8")).digest()
    return int.from_bytes(digest[:_STREAM_DIGEST_BYTES], "big")


def realisation_seed(
    base_seed: int,
    realisation_id: int,
    stream: str,
) -> np.random.Generator:
    """Return the generator for one stream of one realisation.

    Args:
        base_seed: The project seed, :data:`landloss.domain.constants.BASE_SEED`.
        realisation_id: Which modelled earthquake this is, counting from zero.
        stream: The name of the stream drawing from it, one per hazard.

    Returns:
        A ``numpy`` generator, independent of every other stream.

    Raises:
        ValueError: If the realisation id is negative, or the stream is empty.
    """
    if realisation_id < 0:
        msg = f"realisation_id must be zero or more, got {realisation_id}"
        raise ValueError(msg)
    sequence = np.random.SeedSequence(
        [base_seed, realisation_id, stream_entropy(stream)]
    )
    return np.random.default_rng(sequence)
