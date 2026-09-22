"""What NHC would actually pay on a damaged-land claim.

The Act does not offer a claimant a choice between settling on the value of the
damaged land and settling on the cost of repairing it. It builds a **land cover
cap** out of the value, and then pays the lesser of that cap and the repair
cost::

    land_cover_cap = market value of the damaged insured land
                   + min(retaining wall undepreciated value, its sub-cap)
                   + min(bridge and culvert undepreciated value, its sub-cap)

    settlement     = min(repair cost, land_cover_cap) - excess

Three things about that are easy to get wrong, and are why this is a module
rather than a line in a script.

**A sub-cap limits a structure's contribution to the cap, not the settlement.**
A wall whose undepreciated value falls below the sub-cap contributes that value
and the sub-cap never binds at all. Treating the sub-cap as a ceiling on the
payout overstates what is settled on every modest wall in the study.

**The two costings of a structure are different numbers and both are needed.**
Repair cost is the real remedial solution -- demolition, enabling works, site
access, compliance with current standards. Undepreciated value is what the same
structure would have cost to build new, across the whole insured structure even
where only part failed, with no deduction for age and with none of those items
in it. Repair cost drives one side of the comparison and undepreciated value the
other, so a single "wall cost" cannot serve.

**Everything here is inclusive of GST.** That is the basis the Act compares on:
market value is assessed including GST, and the sub-caps are stated excluding it
and grossed up before use. Parameter names carry ``_incl_gst_`` so a call site
cannot quietly mix bases. The Canterbury liquefaction rates arrive excluding
GST and have to be grossed up before they reach this module.

The arithmetic is checked against the three worked examples in
``.agents/context/nhi-act-land-cover-explainer.md``; see
``tests/landloss/loss/test_settlement.py``.
"""

from dataclasses import dataclass

import numpy as np

from landloss.loss.policy import PolicySettings


def _as_amount(value: np.ndarray | float, *, name: str) -> np.ndarray:
    """Return an amount as a float array, refusing anything unusable.

    Args:
        value: The amount, scalar or array.
        name: The parameter's name, for the error message.

    Returns:
        The amount as a float array.

    Raises:
        ValueError: If any element is negative or not finite.
    """
    amounts = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(amounts)) or np.any(amounts < 0):
        msg = f"{name} must be finite and not negative"
        raise ValueError(msg)
    return amounts


def _as_dwelling_count(value: np.ndarray | float) -> np.ndarray:
    """Return a dwelling count as a float array, refusing anything unusable.

    A count below one is refused rather than allowed to mean "no cover". Cover
    exists only where there is a residential building, so a zero here is a
    missing dwelling count rather than a property with no dwellings -- and since
    no layer in the repository produces a dwelling count yet, that is the more
    likely reading by some distance.

    Args:
        value: The dwelling count, scalar or array.

    Returns:
        The count as a float array.

    Raises:
        ValueError: If any element is below one or not finite.
    """
    counts = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(counts)) or np.any(counts < 1):
        msg = "n_dwellings must be finite and at least 1"
        raise ValueError(msg)
    return counts


def structure_contribution_nzd(
    udv_incl_gst_nzd: np.ndarray | float,
    limit_nzd: np.ndarray | float,
) -> np.ndarray | float:
    """Return what a damaged land structure adds to the land cover cap.

    Args:
        udv_incl_gst_nzd: Undepreciated value of the damaged structures of one
            kind, including GST. Zero where none are damaged.
        limit_nzd: The applicable sub-cap limit, already grossed up for GST.

    Returns:
        The lesser of the two, which is the structure's contribution.
    """
    return np.minimum(
        _as_amount(udv_incl_gst_nzd, name="udv_incl_gst_nzd"),
        _as_amount(limit_nzd, name="limit_nzd"),
    )


def land_cover_cap_nzd(
    *,
    market_value_incl_gst_nzd: np.ndarray | float,
    retaining_wall_udv_incl_gst_nzd: np.ndarray | float = 0.0,
    bridge_culvert_udv_incl_gst_nzd: np.ndarray | float = 0.0,
    n_dwellings: np.ndarray | float,
    policy: PolicySettings,
) -> np.ndarray | float:
    """Return the most NHC could pay on a claim, before the excess.

    Args:
        market_value_incl_gst_nzd: Assessed market value of the damaged insured
            land areas, including GST. Zero where only structures are damaged.
        retaining_wall_udv_incl_gst_nzd: Undepreciated value of the damaged
            retaining walls, including GST.
        bridge_culvert_udv_incl_gst_nzd: Undepreciated value of the damaged
            bridges and culverts, including GST.
        n_dwellings: Dwellings in the residential building, which is what both
            sub-caps are multiplied by.
        policy: The settings this scenario runs under.

    Returns:
        The land cover cap in GST-inclusive dollars, limited by
        :attr:`~landloss.loss.policy.PolicySettings.total_cap_nzd` where the
        scenario sets one.

    Examples:
        The explainer's Example 2 -- 60 m2 of land worth $45,000 and a wall
        whose $70,000 undepreciated value exceeds the one-dwelling sub-cap of
        $57,500:

        >>> from landloss.loss.policy import PolicySettings
        >>> float(land_cover_cap_nzd(
        ...     market_value_incl_gst_nzd=45_000.0,
        ...     retaining_wall_udv_incl_gst_nzd=70_000.0,
        ...     n_dwellings=1,
        ...     policy=PolicySettings(),
        ... ))
        102500.0
    """
    dwellings = _as_dwelling_count(n_dwellings)
    cap = (
        _as_amount(market_value_incl_gst_nzd, name="market_value_incl_gst_nzd")
        + structure_contribution_nzd(
            retaining_wall_udv_incl_gst_nzd,
            policy.retaining_wall_limit_nzd(dwellings),
        )
        + structure_contribution_nzd(
            bridge_culvert_udv_incl_gst_nzd,
            policy.bridge_culvert_limit_nzd(dwellings),
        )
    )
    if policy.total_cap_nzd is not None:
        # Capping the cap and capping the entitlement give the same answer,
        # because min(repair, min(cap, total)) is min(min(repair, cap), total).
        # It goes here so that a reported cap is the one that actually applied.
        cap = np.minimum(cap, policy.total_cap_nzd)
    return cap


@dataclass(frozen=True)
class DamagedClaim:
    """What a claim brings to the settlement.

    Scalars settle one claim; arrays of equal length settle a whole portfolio
    in one call, which is how the module is meant to be used against a frame.

    Attributes:
        repair_cost_incl_gst_nzd: The cost of putting the damage right, summed
            over every cause on the claim.
        market_value_incl_gst_nzd: Assessed market value of the damaged insured
            land areas. Zero where only structures are damaged.
        n_dwellings: Dwellings in the residential building, which is what both
            sub-caps are multiplied by.
        retaining_wall_udv_incl_gst_nzd: Undepreciated value of the damaged
            retaining walls. Zero where none are damaged.
        bridge_culvert_udv_incl_gst_nzd: Undepreciated value of the damaged
            bridges and culverts. Zero where none are damaged.
    """

    repair_cost_incl_gst_nzd: np.ndarray | float
    market_value_incl_gst_nzd: np.ndarray | float
    n_dwellings: np.ndarray | float
    retaining_wall_udv_incl_gst_nzd: np.ndarray | float = 0.0
    bridge_culvert_udv_incl_gst_nzd: np.ndarray | float = 0.0


@dataclass(frozen=True)
class Settlement:
    """A settled claim, with the parts that decided it kept alongside the total.

    The components are carried rather than discarded because the study's
    questions are about them: which constraint bound, how often a sub-cap was
    reached, and what a policy change moved. They cannot be recovered from the
    total afterwards.

    Attributes:
        land_cover_cap_nzd: The most that could have been paid, before excess.
        repair_cost_nzd: The repair cost the cap was compared against.
        retaining_wall_contribution_nzd: What the walls added to the cap.
        bridge_culvert_contribution_nzd: What the bridges and culverts added.
        excess_nzd: The excess deducted.
        settlement_nzd: What is paid, never below zero.
    """

    land_cover_cap_nzd: np.ndarray | float
    repair_cost_nzd: np.ndarray | float
    retaining_wall_contribution_nzd: np.ndarray | float
    bridge_culvert_contribution_nzd: np.ndarray | float
    excess_nzd: np.ndarray | float
    settlement_nzd: np.ndarray | float

    @property
    def capped(self) -> np.ndarray | bool:
        """Whether the land cover cap bound rather than the repair cost."""
        return np.asarray(self.land_cover_cap_nzd) < np.asarray(self.repair_cost_nzd)


def settle(claim: DamagedClaim, *, policy: PolicySettings) -> Settlement:
    """Settle a claim, returning the total and the parts that decided it.

    Args:
        claim: The damage to settle.
        policy: The settings this scenario runs under.

    Returns:
        A :class:`Settlement`. Arrays in give arrays out, so a whole portfolio
        settles in one call.

    Examples:
        The explainer's Example 3 -- $45,000 of damaged land and a modest timber
        pole wall, so the sub-cap never binds and the repair cost is what is
        paid, less the excess:

        >>> from landloss.loss.policy import PolicySettings
        >>> result = settle(
        ...     DamagedClaim(
        ...         repair_cost_incl_gst_nzd=58_000.0,
        ...         market_value_incl_gst_nzd=45_000.0,
        ...         retaining_wall_udv_incl_gst_nzd=30_000.0,
        ...         n_dwellings=1,
        ...     ),
        ...     policy=PolicySettings(),
        ... )
        >>> float(result.land_cover_cap_nzd)
        75000.0
        >>> float(result.settlement_nzd)
        57500.0
    """
    dwellings = _as_dwelling_count(claim.n_dwellings)
    repair = _as_amount(claim.repair_cost_incl_gst_nzd, name="repair_cost_incl_gst_nzd")

    walls = structure_contribution_nzd(
        claim.retaining_wall_udv_incl_gst_nzd,
        policy.retaining_wall_limit_nzd(dwellings),
    )
    crossings = structure_contribution_nzd(
        claim.bridge_culvert_udv_incl_gst_nzd,
        policy.bridge_culvert_limit_nzd(dwellings),
    )
    cap = land_cover_cap_nzd(
        market_value_incl_gst_nzd=claim.market_value_incl_gst_nzd,
        retaining_wall_udv_incl_gst_nzd=claim.retaining_wall_udv_incl_gst_nzd,
        bridge_culvert_udv_incl_gst_nzd=claim.bridge_culvert_udv_incl_gst_nzd,
        n_dwellings=dwellings,
        policy=policy,
    )
    excess = policy.excess_nzd(dwellings)

    # Floored at zero: where the excess exceeds what would otherwise be paid,
    # the claim settles at nothing rather than owing NHC money.
    settlement = np.maximum(np.minimum(repair, cap) - excess, 0.0)

    return Settlement(
        land_cover_cap_nzd=cap,
        repair_cost_nzd=repair,
        retaining_wall_contribution_nzd=walls,
        bridge_culvert_contribution_nzd=crossings,
        excess_nzd=excess,
        settlement_nzd=settlement,
    )
