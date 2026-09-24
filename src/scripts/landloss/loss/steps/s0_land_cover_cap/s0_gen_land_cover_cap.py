"""Build the land cover cap on each claim, from the four tables vul hands over.

The Act settles the lesser of the repair cost and a **land cover cap** built out
of the value of what was damaged::

    land cover cap = market value of the damaged insured land
                   + min(retaining wall undepreciated value, its sub-cap)
                   + min(bridge and culvert undepreciated value, its sub-cap)

This step builds that cap on real data, per realisation:

    uv run --frozen python src/scripts/landloss/loss/steps/s0_land_cover_cap/s0_gen_land_cover_cap.py

**It stops short of a settlement, and that is not an omission.** A settlement is
``min(repair cost, cap)`` less the excess, and no repair cost exists yet: a
wall's needs the three site ratings, of which only earthworks can be derived
(**Q-10**), and damaged land has no Land SOW behind it at all. The cap is the
half of the comparison that *can* be built, and it is the half most of the
study's questions are about -- how often each constraint binds, and what the
sub-caps are worth.

The arithmetic is all in :mod:`landloss.loss.settlement` and
:mod:`landloss.loss.pricing`, and the aggregation onto ``claim_id`` is in
:mod:`landloss.loss.claims`. This script adds **no modelling**. What it runs
over comes from ``config.py`` beside it, and the policy it runs under is
:class:`~landloss.loss.policy.PolicySettings` as the Act stands.

Two things it reports rather than hides. Culverts and bridges contribute
**nothing** to the cap, because nothing prices a crossing yet, so a claim whose
only damaged structure is a culvert caps on its land alone. And every wall is
priced at the beta flat rate, an average of four timber pole rates standing in
for a construction type nothing supplies.
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from landloss.domain.loss_contract import (
    CLAIM_ID_COLUMN,
    IS_DAMAGED_COLUMN,
    REALISATION_ID_COLUMN,
    RW_LENGTH_COLUMN,
    RW_SIZE_COLUMN,
)
from landloss.loss import claims as loss_claims
from landloss.loss.policy import PolicySettings
from landloss.loss.pricing import beta_wall_face_area_m2, beta_wall_udv_incl_gst_nzd
from landloss.loss.settlement import (
    area_cap_bound,
    damaged_land_value_nzd,
    land_cover_cap_nzd,
    structure_contribution_nzd,
    structure_sub_cap_bound,
)
from scripts.landloss.loss.steps.s0_land_cover_cap import config
from scripts.landloss.paths import TEMP_DIR
from scripts.landloss.vul.steps.s10_property_damage.gen_property_damage import (
    loss_input_path,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "loss"
OUT_STEM = "land-cover-cap"

RULE = "-" * 72

# The four tables this reads, in the order the contract lists them.
LOSS_TABLES = ("land", "rw", "culverts", "bridges")

# What the step writes, beyond the claim key and what `land_by_claim` carries.
# Each is kept because none can be recovered from the cap afterwards: the two
# components say which side of the cap the money is on, and the two flags say
# which constraint was reached.
LAND_VALUE_COLUMN = "land_value_incl_gst_nzd"
RW_UDV_COLUMN = "retaining_wall_udv_incl_gst_nzd"
RW_CONTRIBUTION_COLUMN = "retaining_wall_contribution_incl_gst_nzd"
CAP_COLUMN = "land_cover_cap_incl_gst_nzd"
AREA_CAP_BOUND_COLUMN = "area_cap_bound"
RW_SUB_CAP_BOUND_COLUMN = "retaining_wall_sub_cap_bound"


def land_cover_cap_path(realisation_id: int, *, pilot: bool) -> Path:
    """Return the file a run writes one realisation's caps to.

    Args:
        realisation_id: The modelled earthquake.
        pilot: Whether the run is over the small Wellington pilot box.

    Returns:
        The path, under ``temp/loss``.
    """
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.parquet"


def wall_udv_by_claim(rw: pd.DataFrame, *, policy: PolicySettings) -> pd.Series:
    """Return each claim's damaged retaining wall undepreciated value.

    Undepreciated value, not repair cost: the cap is built from what the wall
    was worth, and only the repair side needs the site ratings nothing supplies.
    Walls are summed over the claim, because the sub-cap applies to a claim's
    walls together rather than to each wall on its own.

    Args:
        rw: The contract's retaining wall table.
        policy: The settings this scenario runs under.

    Returns:
        The value per claim, indexed by ``claim_id``. A claim with no damaged
        wall does not appear.
    """
    damaged = loss_claims.damaged_walls(rw)
    if damaged.empty:
        return pd.Series(dtype=float)
    face_area = beta_wall_face_area_m2(
        damaged[RW_SIZE_COLUMN].to_numpy(), damaged[RW_LENGTH_COLUMN].to_numpy()
    )
    walls = pd.DataFrame(
        {
            CLAIM_ID_COLUMN: damaged[CLAIM_ID_COLUMN].to_numpy(),
            "udv": beta_wall_udv_incl_gst_nzd(face_area, policy=policy),
        }
    )
    return walls.groupby(CLAIM_ID_COLUMN)["udv"].sum()


def describe_land(caps):
    """Print how much damaged ground there is and what it is worth."""
    print(RULE)
    area_column = loss_claims.DAMAGED_AREA_COLUMN
    damaged = caps[caps[area_column] > 0]
    print(
        f"Land: {len(caps):,} claims, {len(damaged):,} with damaged ground, "
        f"{caps[area_column].sum():,.0f} m2 in total"
    )
    if damaged.empty:
        return
    print(
        f"  Valued at {caps[LAND_VALUE_COLUMN].sum():,.0f} NZD including GST, "
        f"median {damaged[LAND_VALUE_COLUMN].median():,.0f} NZD on a damaged claim"
    )
    bound = int(caps[AREA_CAP_BOUND_COLUMN].sum())
    print(
        f"  The area cap bound on {bound:,} claims, whose damage runs past it and "
        "is valued as though it stopped there"
    )


def describe_walls(caps, rw):
    """Print what the walls add to the cap, and what the sub-cap holds back."""
    print(RULE)
    damaged = loss_claims.damaged_walls(rw)
    with_wall = caps[caps[RW_UDV_COLUMN] > 0]
    print(
        f"Retaining walls: {len(damaged):,} damaged of {len(rw):,}, on "
        f"{len(with_wall):,} claims"
    )
    if with_wall.empty:
        return
    udv = caps[RW_UDV_COLUMN].sum()
    contributed = caps[RW_CONTRIBUTION_COLUMN].sum()
    bound = int(caps[RW_SUB_CAP_BOUND_COLUMN].sum())
    print(
        f"  {udv:,.0f} NZD of undepreciated value, of which {contributed:,.0f} NZD "
        "reaches the cap"
    )
    print(
        f"  The sub-cap bound on {bound:,} claims, holding back "
        f"{udv - contributed:,.0f} NZD"
    )


def describe_crossings(culverts, bridges):
    """Print the damaged crossings the cap cannot yet count."""
    print(RULE)
    damaged = int(culverts[IS_DAMAGED_COLUMN].sum()) if not culverts.empty else 0
    print(
        f"Culverts and bridges: {len(culverts):,} culverts and {len(bridges):,} "
        f"bridges, {damaged:,} culverts damaged"
    )
    print(
        "  None of them reach the cap: nothing prices a crossing yet, so a claim "
        "whose only damaged structure is one caps on its land alone."
    )


def describe_caps(caps):
    """Print the caps themselves, and what is still missing from a settlement."""
    print(RULE)
    with_cap = caps[caps[CAP_COLUMN] > 0]
    print(
        f"Land cover cap: {caps[CAP_COLUMN].sum():,.0f} NZD over {len(with_cap):,} "
        "claims that have one"
    )
    if not with_cap.empty:
        print(f"  Median cap on those claims, {with_cap[CAP_COLUMN].median():,.0f} NZD")
    print(
        "Nothing here is settled. A settlement is min(repair cost, cap) less the "
        "excess, and no repair cost exists: a wall's needs the site ratings "
        "(Q-10), and damaged land has no Land SOW behind it."
    )


def main(*, pilot, realisation_ids):
    """Build and write the land cover cap per claim, per realisation.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to cap.
    """
    policy = PolicySettings()

    for realisation_id in realisation_ids:
        print(f"\nCapping realisation {realisation_id} ...", flush=True)
        tables = {
            name: gpd.read_parquet(loss_input_path(name, realisation_id, pilot=pilot))
            for name in LOSS_TABLES
        }

        caps = loss_claims.land_by_claim(tables["land"])
        caps[RW_UDV_COLUMN] = (
            wall_udv_by_claim(tables["rw"], policy=policy).reindex(caps.index).fillna(0)
        )

        # The dwelling count is validated against the same table it is read
        # from, so a claim missing one is refused here rather than quietly
        # halving its sub-cap.
        n_dwellings = loss_claims.dwelling_counts(
            caps.index.to_numpy(), caps.reset_index()
        )
        area = caps[loss_claims.DAMAGED_AREA_COLUMN].to_numpy()
        rate = caps[loss_claims.LAND_RATE_COLUMN].to_numpy()
        udv = caps[RW_UDV_COLUMN].to_numpy()
        limit = policy.retaining_wall_limit_nzd(n_dwellings)

        caps[LAND_VALUE_COLUMN] = damaged_land_value_nzd(area, rate, policy=policy)
        caps[AREA_CAP_BOUND_COLUMN] = area_cap_bound(area, policy=policy)
        caps[RW_CONTRIBUTION_COLUMN] = structure_contribution_nzd(udv, limit)
        caps[RW_SUB_CAP_BOUND_COLUMN] = structure_sub_cap_bound(udv, limit)
        caps[CAP_COLUMN] = land_cover_cap_nzd(
            land_value_incl_gst_nzd=caps[LAND_VALUE_COLUMN].to_numpy(),
            retaining_wall_udv_incl_gst_nzd=udv,
            n_dwellings=n_dwellings,
            policy=policy,
        )

        describe_land(caps)
        describe_walls(caps, tables["rw"])
        describe_crossings(tables["culverts"], tables["bridges"])
        describe_caps(caps)

        out = caps.reset_index()
        out.insert(0, REALISATION_ID_COLUMN, realisation_id)
        out_path = land_cover_cap_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(out_path)
        print(RULE)
        print(f"Wrote {len(out):,} claims to {out_path}")


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
