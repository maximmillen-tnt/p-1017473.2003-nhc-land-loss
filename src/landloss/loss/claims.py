"""Reading what upstream wrote onto the claims this module settles.

:mod:`landloss.loss.settlement` is arithmetic over arrays and knows nothing
about files. This module is the thin layer that fills those arrays from what
`exposure` writes, keeping the file and column names in one place instead of
spread across call sites.

**The dwelling count is the piece that has to come from here.** Both land
structure sub-caps and the excess are multiplied by the number of dwellings in
the residential building, and nothing in the `vul` contract carries one --
`vul` sends assets and their damage, not the property's occupancy. The count
comes instead from the module-level exposure step
``s3_dwellings_per_property``, which counts the address points standing inside
each claim property and writes one row per claim.

Two things about that count are worth carrying to the point of use, because
both bias a settlement and neither is visible in the number itself:

- **A dwelling is an address point, not a self-contained dwelling.** LINZ gives
  a unit of a block its own address, which is what makes the count work for
  flats, but it also gives one to a commercial tenancy and gives none to a
  minor dwelling that was never separately addressed. The count is a floor on a
  block and an over-count on a mixed-use building.
- **It scales three figures at once** -- the retaining wall sub-cap, the bridge
  and culvert sub-cap, and the excess. The first two raise a settlement and the
  third lowers it, so an error does not announce itself in the total; it has to
  be caught here.

The column names below are the contract with
:mod:`landloss.exposure.land.extent`, not an import from it: the four top-level
modules exchange data files rather than symbols, so the names are written out
in both places and a test holds them to each other.
"""

import numpy as np
import pandas as pd

# The claim key, and the count written against it by the dwellings-per-property
# step. These must match what `landloss.exposure.land.extent` writes; see the
# module docstring for why they are not imported.
CLAIM_ID_COLUMN = "claim_id"
DWELLING_COUNT_COLUMN = "dwelling_count"

# How many identifiers an error message names before it stops. Enough to start
# looking with, short enough to read.
MAX_REPORTED_IDS = 5


def _report(values: pd.Index | pd.Series) -> str:
    """Return a short, stable list of identifiers for an error message.

    Args:
        values: The identifiers to name.

    Returns:
        Up to :data:`MAX_REPORTED_IDS` of them, sorted, with a count of the
        rest where there are more.
    """
    listed = sorted(pd.unique(pd.Series(values)))
    shown = ", ".join(repr(value) for value in listed[:MAX_REPORTED_IDS])
    if len(listed) > MAX_REPORTED_IDS:
        return f"{shown} and {len(listed) - MAX_REPORTED_IDS:,} more"
    return shown


def dwelling_counts(
    claim_ids: np.ndarray | pd.Series,
    dwellings_per_property: pd.DataFrame,
    *,
    id_column: str = CLAIM_ID_COLUMN,
    count_column: str = DWELLING_COUNT_COLUMN,
) -> np.ndarray:
    """Return the dwelling count for each claim, in the order asked for.

    The result is what :class:`~landloss.loss.settlement.DamagedClaim` takes as
    ``n_dwellings``, aligned to the claims the caller is settling.

    A claim with no row in the property table is **refused rather than
    defaulted to one**. Defaulting would halve the cap on a pair of flats and
    halve the excess with it, which changes a settlement without changing
    anything visible about it; the same reasoning
    :func:`~landloss.loss.settlement.settle` applies to a count below one.

    Args:
        claim_ids: The claims to settle, in the order their other arrays are in.
        dwellings_per_property: One row per claim property, as
            ``s3_dwellings_per_property`` writes it.
        id_column: The claim identifier both are keyed on.
        count_column: The dwelling count column.

    Returns:
        The counts as a float array, one per entry in ``claim_ids``.

    Raises:
        ValueError: If the table lacks either column, carries a claim twice, or
            is missing a claim that was asked for; or if any count is below one
            or not finite.
    """
    for column in (id_column, count_column):
        if column not in dwellings_per_property.columns:
            msg = f"the property table carries no {column!r} column"
            raise ValueError(msg)

    counts = dwellings_per_property.set_index(id_column)[count_column]
    if counts.index.has_duplicates:
        duplicated = counts.index[counts.index.duplicated()]
        msg = (
            "the property table carries a claim more than once, so the count "
            f"to use is ambiguous: {_report(duplicated)}"
        )
        raise ValueError(msg)

    asked = pd.Series(np.asarray(claim_ids))
    found = asked.map(counts)
    if found.isna().any():
        msg = (
            "no dwelling count for "
            f"{_report(asked[found.isna()])}. A claim with no count is refused "
            "rather than settled as one dwelling, because that would halve the "
            "sub-caps without halving what is claimed against them."
        )
        raise ValueError(msg)

    values = found.to_numpy(dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values < 1):
        below = asked[(~np.isfinite(values)) | (values < 1)]
        msg = (
            f"dwelling count below one, or not finite, for {_report(below)}. "
            "Cover exists only where there is a residential building, so this "
            "is a missing count rather than a property with no dwellings."
        )
        raise ValueError(msg)
    return values
