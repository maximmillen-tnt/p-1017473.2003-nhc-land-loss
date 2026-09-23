"""What it costs to rebuild a damaged land structure.

`vul` emits a damage state for a retaining wall rather than a price, so the
money is worked out here. This module holds the repair cost half of that: the
rates NHC's own costing tool assesses a claim on, and the site multiplier it
applies to them, so this study's pricing reproduces the tool's answer rather
than arriving at one of its own.

A wall's repair cost is::

    repair cost = m2 rate x wall face area x (1 + site multiplier)

**The rates are per square metre of wall face and exclude GST.** The settlement
arithmetic in :mod:`landloss.loss.settlement` works GST-inclusive, because that
is the basis the Act compares on, so the gross-up happens here at the point of
use and every amount leaving this module is named ``_incl_gst_``.

**The site multiplier is three ratings, not two.** The costing tool rates
construction access, earthworks required, and constructability and
reinstatement, each easy, moderate or difficult, and the combination is a
markup on the wall cost. The tool carries all 27 combinations as a lookup
table; every row of it is the sum of a per-rating markup of 0%, 5% and 10%, so
:class:`SiteRatings` computes the figure rather than storing the table, and
``tests/landloss/loss/test_pricing.py`` checks the formula against all 27 rows.
An all-difficult site attracts 30%, which is also the ceiling the tool's own
line items cap at.

What this module does **not** yet do, each because a figure has not been
obtained rather than because it was decided against:

- **Undepreciated value.** The Act compares repair cost against undepreciated
  value, and the two are different numbers: UDV is the cost to build the same
  wall new *without* the additional items the square metre rates carry, and it
  comes from its own sheet of set fees rather than from these rates. Until
  those arrive, nothing here can produce the
  ``retaining_wall_udv_incl_gst_nzd`` that
  :func:`landloss.loss.settlement.settle` takes.
- **Which wall type a modelled wall is.** The rates are keyed on construction
  type, and :mod:`landloss.exposure.rw.beta_population` emits a size class and
  an initial condition instead. Until the study settles that mapping, every
  wall is priced at :data:`BETA_WALL_RATE_EXCL_GST_NZD_PER_M2`, a flat rate
  standing in for the whole population -- see the note on it below, because the
  choice of type moves the answer further than anything else in this module.
- **Enabling works, and the compliance items.** Chris Ewens was explicit that
  the wall rates carry no enabling works allowance. Whether enabling works is a
  separate line on the scope of works, or is what the constructability and
  reinstatement rating already prices, is unresolved -- as is what the council
  stormwater connection and the fall-from-height barrier add.

The rates and the multiplier table came from the costing tool itself; the
meeting they were walked through at is ``.agents/context/nhc-costing-tool.md``.
"""

from dataclasses import dataclass

import numpy as np

from landloss.loss.policy import PolicySettings

# Retaining wall rates in dollars per square metre of wall face, **excluding
# GST**, from the costing tool's `lists` sheet. These are the QS-derived rates
# Chris Ewens revises every four months, so they are a snapshot rather than a
# constant of nature; see :data:`WALL_RATES_AS_AT`.
WALL_RATE_EXCL_GST_NZD_PER_M2 = {
    "Timber Pole: 175mm SED": 643.19,
    "Timber Pole: 250mm SED": 744.69,
    "Timber Pole: 300mm SED": 798.80,
    "Timber Pole: 350mm SED": 879.87,
    "Concrete Block": 1_010.58,
    "Concrete Crib": 834.08,
    "Gabion Basket": 958.78,
    "Rock: Mortar Bed": 1_130.08,
    "Reinforced Concrete": 1_224.08,
    "Keystone": 930.54,
    "Sleepers": 1_232.41,
    "UC: 200mm x 60mm": 2_286.93,
    "UC: 250mm x 90mm": 3_063.43,
    "UC: 310mm x 158mm": 4_736.23,
    "PFC: 230mm x 90mm": 1_586.69,
    "PFC: 250mm x 90mm": 1_645.73,
    "PFC: 380mm x 100mm": 2_130.35,
    "Sheet Piling: SP3W / STU1800": 1_328.33,
    "Sheet Piling: SP4W / STU2700": 1_538.33,
    "Driven Timber Pole: 175mm SED": 535.39,
    "Driven Timber Pole: 250mm SED": 575.50,
    "Driven Timber Pole: 300mm SED": 622.81,
    "Driven Timber Pole: 350mm SED": 767.38,
    "Mechanically Stabilised Earth (MSE)": 1_034.95,
    "Shotcrete": 226.67,
    "Soil Nail": 775.00,
    "Palisade: Driven Timber Pole": 900.00,
    "Palisade: Concrete Encased Timber Pole": 896.40,
    "Palisade: Steel Cages and Concrete": 1_632.00,
}

# When the rates above were taken from the tool. They are revised every four
# months, so a run made long after this date is pricing on stale figures.
WALL_RATES_AS_AT = "2026-09-23"

EASY = "E"
MODERATE = "M"
DIFFICULT = "D"

# What each rating adds, as a fraction of the wall cost. The tool enumerates all
# 27 combinations of the three; every row is exactly the sum of these, which is
# why the table itself is not reproduced here.
RATING_MARKUP = {EASY: 0.00, MODERATE: 0.05, DIFFICULT: 0.10}

# What an all-difficult site attracts, and the ceiling the tool's individual
# line items cap at. Named so a test can assert the formula never exceeds it.
MAX_SITE_MULTIPLIER = 3 * RATING_MARKUP[DIFFICULT]

# The wall types the beta rate averages: the four non-driven timber pole walls,
# which differ only in pile diameter. The driven timber pole rates are a
# separate and cheaper family in the tool and are deliberately left out.
BETA_WALL_TYPES = (
    "Timber Pole: 175mm SED",
    "Timber Pole: 250mm SED",
    "Timber Pole: 300mm SED",
    "Timber Pole: 350mm SED",
)

# One rate for every wall in the study, standing in for a mapping from the wall
# population's size class and initial condition onto a construction type. That
# mapping is not settled, and pricing every wall as a mid-range timber pole is
# the agreed first cut rather than a modelling result.
#
# What it costs: the tool's rates span a factor of 21, so a population that is
# really part concrete and part steel is priced well below what it would settle
# at. Size still moves the cost, but through face area rather than through the
# rate, and initial condition does not move it at all -- condition belongs to
# whether the wall fails, which is `vul`'s question, not to what replacing it
# costs. Derived from the rates rather than written out, so a rate revision
# carries through.
BETA_WALL_RATE_EXCL_GST_NZD_PER_M2 = sum(
    WALL_RATE_EXCL_GST_NZD_PER_M2[wall_type] for wall_type in BETA_WALL_TYPES
) / len(BETA_WALL_TYPES)

# The retained height each size class is priced at. `vul` sends a size class and
# a length, and the rate is charged on wall face, so a band has to become a
# height before anything can be priced.
#
# Each is the midpoint of what its class can actually contain. The class bands
# in `landloss.exposure.rw.beta_population` are small below 1 m, medium 1 to
# 2.5 m and large 2.5 m and above, and that module draws heights over 0.4 to
# 3.0 m, so the realised bands are 0.4 to 1.0, 1.0 to 2.5 and 2.5 to 3.0 -- and
# their midpoints land a clean metre apart. Every height here classifies back to
# its own size class, which is what keeps this mapping and those bands from
# drifting apart unnoticed.
#
# These are **set values, not draws**: every medium wall in the study is priced
# at 1.75 m. So a size class carries no variation of its own, and the spread in
# wall cost across the portfolio comes from length and from the site ratings
# alone. Drawing within the band, or setting the height off the slope the wall
# sits on, are both better and both deferred (**I-14**).
BETA_SIZE_CLASS_HEIGHT_M = {
    "small": 0.75,
    "medium": 1.75,
    "large": 2.75,
}


def _as_markup(rating: np.ndarray | str, *, name: str) -> np.ndarray:
    """Return the markup a rating attracts, refusing anything else.

    Args:
        rating: The rating, ``"E"``, ``"M"`` or ``"D"``, scalar or array. Case
            is not significant.
        name: The parameter's name, for the error message.

    Returns:
        The markup as a float array, shaped like ``rating``.

    Raises:
        ValueError: If any element is not one of the three ratings.
    """
    ratings = np.char.upper(np.asarray(rating, dtype=str))
    flat = ratings.ravel().tolist()
    unknown = sorted(set(flat) - set(RATING_MARKUP))
    if unknown:
        msg = (
            f"{name} must be one of {EASY}, {MODERATE} or {DIFFICULT}; "
            f"got {', '.join(repr(value) for value in unknown)}"
        )
        raise ValueError(msg)
    markups = np.array([RATING_MARKUP[value] for value in flat], dtype=float)
    return markups.reshape(ratings.shape)


@dataclass(frozen=True)
class SiteRatings:
    """How hard a site is to work on, as the costing tool rates it.

    The three are rated independently, each easy, moderate or difficult. T+T
    already supply all three in the duty geotechnical report, so this study can
    generate them rather than having to source them.

    Scalars rate one wall; arrays of equal length rate a population, which is
    how a portfolio is priced in one call.

    Attributes:
        construction_access: Getting people and machinery to the wall.
        earthworks_required: The earthworks the remedial solution needs.
        constructability_reinstatement: Building the wall, and tidying the site
            up on the way out.
    """

    construction_access: np.ndarray | str
    earthworks_required: np.ndarray | str
    constructability_reinstatement: np.ndarray | str

    @property
    def multiplier(self) -> np.ndarray:
        """Return the markup on the wall cost, from 0 to 0.30.

        Returns:
            The sum of the three ratings' markups.
        """
        return (
            _as_markup(self.construction_access, name="construction_access")
            + _as_markup(self.earthworks_required, name="earthworks_required")
            + _as_markup(
                self.constructability_reinstatement,
                name="constructability_reinstatement",
            )
        )


def wall_rate_excl_gst_nzd_per_m2(wall_type: np.ndarray | str) -> np.ndarray:
    """Return the square metre rate for a wall type, excluding GST.

    Args:
        wall_type: The construction type, named as
            :data:`WALL_RATE_EXCL_GST_NZD_PER_M2` keys it. Scalar or array.

    Returns:
        The rate in GST-exclusive dollars per square metre of wall face.

    Raises:
        ValueError: If any wall type is not one the costing tool carries. The
            rates are a closed list, so an unrecognised type is a mapping error
            upstream rather than a wall the tool would price some other way.
    """
    types = np.asarray(wall_type, dtype=str)
    flat = types.ravel().tolist()
    unknown = sorted(set(flat) - set(WALL_RATE_EXCL_GST_NZD_PER_M2))
    if unknown:
        msg = f"unknown wall type(s): {', '.join(repr(value) for value in unknown)}"
        raise ValueError(msg)
    rates = np.array(
        [WALL_RATE_EXCL_GST_NZD_PER_M2[value] for value in flat], dtype=float
    )
    return rates.reshape(types.shape)


def beta_wall_height_m(rw_size: np.ndarray | str) -> np.ndarray:
    """Return the retained height a size class is priced at.

    Args:
        rw_size: The size class, ``"small"``, ``"medium"`` or ``"large"``, as
            `vul` sends it. Scalar or array. Case is not significant.

    Returns:
        The height in metres, shaped like ``rw_size``.

    Raises:
        ValueError: If any element is not one of the three size classes.
    """
    sizes = np.char.lower(np.asarray(rw_size, dtype=str))
    flat = sizes.ravel().tolist()
    unknown = sorted(set(flat) - set(BETA_SIZE_CLASS_HEIGHT_M))
    if unknown:
        msg = (
            "rw_size must be one of "
            f"{', '.join(BETA_SIZE_CLASS_HEIGHT_M)}; "
            f"got {', '.join(repr(value) for value in unknown)}"
        )
        raise ValueError(msg)
    heights = np.array(
        [BETA_SIZE_CLASS_HEIGHT_M[value] for value in flat], dtype=float
    )
    return heights.reshape(sizes.shape)


def wall_face_area_m2(
    height_m: np.ndarray | float,
    length_m: np.ndarray | float,
) -> np.ndarray:
    """Return the area of wall face the rate is charged against.

    Retained height rather than built height, since that is what the wall
    population carries and what a geotechnical report records.

    Args:
        height_m: Retained height of the wall.
        length_m: Length of the wall along its run.

    Returns:
        The face area in square metres.

    Raises:
        ValueError: If either is negative or not finite.
    """
    height = np.asarray(height_m, dtype=float)
    length = np.asarray(length_m, dtype=float)
    for name, values in (("height_m", height), ("length_m", length)):
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            msg = f"{name} must be finite and not negative"
            raise ValueError(msg)
    return height * length


def beta_wall_face_area_m2(
    rw_size: np.ndarray | str,
    length_m: np.ndarray | float,
) -> np.ndarray:
    """Return the wall face area from the size class and length `vul` sends.

    The height is the set value :data:`BETA_SIZE_CLASS_HEIGHT_M` gives the
    class, so two walls of the same class and length price identically.

    Args:
        rw_size: The size class, scalar or array.
        length_m: Length of the wall along its run.

    Returns:
        The face area in square metres.

    Raises:
        ValueError: If the length is negative or not finite, or the size class
            is not one of the three.
    """
    return wall_face_area_m2(beta_wall_height_m(rw_size), length_m)


def _repair_cost_incl_gst_nzd(
    rate_excl_gst_nzd_per_m2: np.ndarray | float,
    face_area_m2: np.ndarray | float,
    *,
    ratings: SiteRatings,
    policy: PolicySettings,
) -> np.ndarray:
    """Return a wall's replacement cost from a rate, including GST.

    Args:
        rate_excl_gst_nzd_per_m2: The square metre rate, excluding GST.
        face_area_m2: Area of wall face.
        ratings: How hard the site is to work on.
        policy: The settings this scenario runs under.

    Returns:
        The cost in GST-inclusive dollars.

    Raises:
        ValueError: If the area is negative or not finite.
    """
    area = np.asarray(face_area_m2, dtype=float)
    if not np.all(np.isfinite(area)) or np.any(area < 0):
        msg = "face_area_m2 must be finite and not negative"
        raise ValueError(msg)
    excl_gst = rate_excl_gst_nzd_per_m2 * area * (1.0 + ratings.multiplier)
    return excl_gst * (1.0 + policy.gst_rate)


def wall_repair_cost_incl_gst_nzd(
    wall_type: np.ndarray | str,
    face_area_m2: np.ndarray | float,
    *,
    ratings: SiteRatings,
    policy: PolicySettings,
) -> np.ndarray:
    """Return what it costs to replace a wall of a known type, including GST.

    A tilted or failed wall is replaced rather than repaired: partial repair is
    about 1% of cases and is not modelled, so this is the only wall cost the
    study produces.

    Args:
        wall_type: The construction type, scalar or array.
        face_area_m2: Area of wall face, from :func:`wall_face_area_m2`.
        ratings: How hard the site is to work on.
        policy: The settings this scenario runs under, which carry the rate the
            GST-exclusive figures are grossed up at.

    Returns:
        The repair cost in GST-inclusive dollars. It excludes enabling works
        and the compliance items, neither of which the rates carry.

    Raises:
        ValueError: If the area is negative or not finite, or if the wall type
            or any rating is not one the costing tool carries.
    """
    return _repair_cost_incl_gst_nzd(
        wall_rate_excl_gst_nzd_per_m2(wall_type),
        face_area_m2,
        ratings=ratings,
        policy=policy,
    )


def beta_wall_repair_cost_incl_gst_nzd(
    face_area_m2: np.ndarray | float,
    *,
    ratings: SiteRatings,
    policy: PolicySettings,
) -> np.ndarray:
    """Return what it costs to replace a wall of unknown type, including GST.

    Prices every wall at :data:`BETA_WALL_RATE_EXCL_GST_NZD_PER_M2`, because
    nothing yet says which of the tool's 29 construction types a modelled wall
    is. The ``beta`` prefix is the same one
    :mod:`landloss.exposure.rw.beta_population` carries and means the same
    thing: this is deleted once the study settles the mapping, and no result
    from it is evidence about Wellington.

    Args:
        face_area_m2: Area of wall face, from :func:`wall_face_area_m2`.
        ratings: How hard the site is to work on.
        policy: The settings this scenario runs under.

    Returns:
        The repair cost in GST-inclusive dollars, on the same exclusions as
        :func:`wall_repair_cost_incl_gst_nzd`.

    Raises:
        ValueError: If the area is negative or not finite, or any rating is not
            one the costing tool carries.
    """
    return _repair_cost_incl_gst_nzd(
        BETA_WALL_RATE_EXCL_GST_NZD_PER_M2,
        face_area_m2,
        ratings=ratings,
        policy=policy,
    )
