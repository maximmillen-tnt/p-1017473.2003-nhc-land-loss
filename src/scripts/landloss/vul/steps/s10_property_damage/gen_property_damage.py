"""Join every hazard's damage onto one row per property.

The vulnerability module ends in four separate files keyed on ``claim_id`` --
liquefaction land damage, landslide areas, retaining wall states and crossing
states -- and nothing brings them together. This step does:

    uv run --frozen python src/scripts/landloss/vul/steps/s10_property_damage/gen_property_damage.py

It adds **no modelling**. Every number it writes was decided by the step it came
from; what it contributes is the join, and the two things the join makes visible
that four separate files hide:

- **A property damaged by more than one cause.** Separate files cannot say how
  many properties carry both a liquefaction state and a landslide, and that
  overlap is what decides whether the caps bind.
- **Whether the causes are counting the same damage twice.** The Canterbury
  land damage rates may already include retaining wall, culvert and bridge
  damage, in which case a property's wall is priced twice over -- once inside
  its liquefaction cost and once as a written-off wall. That is **T-27**, and
  this run prints how many properties it would apply to.

**Nothing is settled and nothing is converted.** Costs stay in the units their
own step recorded, which for the liquefaction component is 2011 dollars
excluding GST; `cost_year` and `rate_basis` ride on the row so the loss module
can reconcile them. Caps, excesses, GST and the market value of the damaged land
belong to the loss module, which this step does not touch.

The key is the property, which is **not the same as the address**: units sharing
a coordinate were collapsed into one property carrying a ``dwelling_count`` by
the insured land step, because NHC's sub-caps and excess are per dwelling.

What it runs over comes from ``config.py`` beside it.
"""

import sys

import geopandas as gpd
import pandas as pd

from landloss.vul.shaking.fragility import DAMAGE_STATE_COLUMN, REPLACE
from scripts.landloss.exposure.land.steps.s5_insured_land_extent.gen_insured_land import (
    insured_land_path,
)
from scripts.landloss.paths import TEMP_DIR
from scripts.landloss.vul.landslide.land.steps.s3_landslide_land_damage.gen_landslide_land_damage import (
    landslide_land_damage_path,
)
from scripts.landloss.vul.liquefaction.land.steps.s2_liq_land_damage.gen_liq_land_damage import (
    liq_land_damage_path,
)
from scripts.landloss.vul.shaking.culverts_bridges.steps.s9_structure_damage_state.gen_structure_damage_state import (
    structure_damage_state_path,
)
from scripts.landloss.vul.shaking.rw.steps.s9_wall_damage_state.gen_wall_damage_state import (
    wall_damage_state_path,
)
from scripts.landloss.vul.steps.s10_property_damage import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "vul"
OUT_STEM = "property-damage"

ID_COLUMN = "claim_id"

# What the landslide step contributes, and what a property it did not reach
# carries instead. An area is zero because untouched ground is undamaged ground;
# a depth is left missing, because there is no depth to report rather than a
# depth of none. The same distinction applies to the liquefaction state and to
# the structure counts, which are filled in beside their own joins.
LANDSLIDE_COLUMNS = {
    "evacuated_area_m2": 0.0,
    "inundated_area_m2": 0.0,
    "evacuated_depth_m": None,
    "inundated_depth_m": None,
}
# The kinds of structure counted per property, as the damage state files name
# them, against the column prefix each is written under.
STRUCTURE_ASSETS = {
    "retaining_walls": "retaining wall",
    "culverts": "culvert",
    "bridges": "bridge",
}

RULE = "-" * 72


def property_damage_path(realisation_id, *, pilot):
    """Return the file a run writes one realisation's joined damage to."""
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.parquet"


def count_structures(states, asset):
    """Return how many of one kind of structure each property has, and loses.

    Args:
        states: The damage states of one asset class, carrying ``ID_COLUMN``,
            an ``asset`` column and a damage state.
        asset: The asset to count, as the damage state file names it.

    Returns:
        A frame indexed by property with a total and a replace count, empty when
        no structure of that kind exists.
    """
    if states.empty:
        return pd.DataFrame(columns=[ID_COLUMN]).set_index(ID_COLUMN)

    of_kind = states[states["asset"] == asset]
    if of_kind.empty:
        return pd.DataFrame(columns=[ID_COLUMN]).set_index(ID_COLUMN)

    return pd.DataFrame(
        {
            "total": of_kind.groupby(ID_COLUMN).size(),
            "replace": of_kind[of_kind[DAMAGE_STATE_COLUMN] == REPLACE]
            .groupby(ID_COLUMN)
            .size(),
        }
    ).fillna(0)


def join_damage(insured, liquefaction, landslide, walls, structures):
    """Return one row per property, carrying every hazard's damage.

    Args:
        insured: The insured land extent, one row per property.
        liquefaction: The liquefaction land damage rows.
        landslide: The landslide damaged area rows.
        walls: The retaining wall damage states.
        structures: The culvert and bridge damage states.

    Returns:
        One row per property in ``insured``, in its order.
    """
    joined = insured.drop(columns=insured.geometry.name).copy()

    liq = liquefaction.set_index(ID_COLUMN)
    joined["ld_state"] = joined[ID_COLUMN].map(liq["ld_state"])
    joined["ld_state_name"] = joined[ID_COLUMN].map(liq["state_name"])
    joined["liq_cost_nzd"] = joined[ID_COLUMN].map(liq["cost_nzd"]).fillna(0.0)
    for column in ("cost_year", "rate_basis", "cost_percentile"):
        joined[column] = joined[ID_COLUMN].map(liq[column])

    slides = landslide.set_index(ID_COLUMN)
    for column, default in LANDSLIDE_COLUMNS.items():
        values = joined[ID_COLUMN].map(slides[column]) if column in slides else None
        joined[column] = values if values is not None else default
        if default is not None:
            joined[column] = joined[column].fillna(default)

    for prefix, asset in STRUCTURE_ASSETS.items():
        frame = walls if prefix == "retaining_walls" else structures
        counts = count_structures(frame, asset)
        joined[prefix] = (
            joined[ID_COLUMN].map(counts["total"]).fillna(0).astype(int)
            if not counts.empty
            else 0
        )
        joined[f"{prefix}_to_replace"] = (
            joined[ID_COLUMN].map(counts["replace"]).fillna(0).astype(int)
            if not counts.empty
            else 0
        )

    return joined


def describe_join(joined):
    """Print what the join makes visible that the separate files cannot."""
    causes = pd.DataFrame(
        {
            "liquefaction": joined["ld_state"].notna(),
            "landslide": (joined["evacuated_area_m2"] > 0)
            | (joined["inundated_area_m2"] > 0),
            "retaining wall": joined["retaining_walls_to_replace"] > 0,
            "culvert or bridge": (joined["culverts_to_replace"] > 0)
            | (joined["bridges_to_replace"] > 0),
        }
    )
    count = causes.sum(axis=1)

    print(RULE)
    print(
        f"Properties: {len(joined):,}, {int(joined['dwelling_count'].sum()):,} dwellings"
    )
    print(f"  {int((count > 0).sum()):,} carry damage from at least one cause")
    for cause in causes.columns:
        print(f"    {cause}: {int(causes[cause].sum()):,}")

    print(RULE)
    print("Causes per property:")
    for causes_on_property, properties in count.value_counts().sort_index().items():
        print(f"  {causes_on_property}: {properties:,}")

    # The double count T-27 would create, sized. The Canterbury rates may
    # already include retaining wall damage, in which case every property in
    # this line is being charged for its wall twice.
    both = int((causes["liquefaction"] & causes["retaining wall"]).sum())
    print(
        f"  {both:,} carry both a liquefaction land damage state and a wall to "
        "replace, which is the double count T-27 would create"
    )


def describe_totals(joined):
    """Print the repair cost this run puts on the portfolio, with its basis."""
    print(RULE)
    priced = joined[joined["liq_cost_nzd"] > 0]
    if priced.empty:
        print("No priced damage.")
    else:
        year = int(priced["cost_year"].dropna().iloc[0])
        percentile = int(priced["cost_percentile"].dropna().iloc[0])
        print(
            f"Liquefaction land repair cost: "
            f"{priced['liq_cost_nzd'].sum():,.0f} NZD, {year} dollars excluding "
            f"GST, at the {percentile}th percentile of settled cost"
        )

    damaged_ground = (
        joined["evacuated_area_m2"].sum() + joined["inundated_area_m2"].sum()
    )
    print(f"Landslide damaged ground: {damaged_ground:,.0f} m2, unpriced")
    print(
        f"Structures to replace: "
        f"{int(joined['retaining_walls_to_replace'].sum()):,} retaining walls, "
        f"{int(joined['culverts_to_replace'].sum()):,} culverts, "
        f"{int(joined['bridges_to_replace'].sum()):,} bridges, all unpriced"
    )
    print(
        "Nothing here is settled. Caps, excesses, GST and the market value of "
        "the damaged land belong to the loss module."
    )


def main(*, pilot, realisation_ids):
    """Write one joined damage row per property, per realisation."""
    insured = gpd.read_parquet(insured_land_path(pilot=pilot))

    for realisation_id in realisation_ids:
        print(f"Joining realisation {realisation_id} ...", flush=True)
        joined = join_damage(
            insured,
            pd.read_parquet(liq_land_damage_path(realisation_id, pilot=pilot)),
            pd.read_parquet(landslide_land_damage_path(realisation_id, pilot=pilot)),
            pd.read_parquet(wall_damage_state_path(realisation_id, pilot=pilot)),
            pd.read_parquet(structure_damage_state_path(realisation_id, pilot=pilot)),
        )
        joined.insert(0, "realisation_id", realisation_id)

        describe_join(joined)
        describe_totals(joined)

        out_path = property_damage_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        joined.to_parquet(out_path)
        print(f"Wrote {len(joined):,} rows to {out_path}")


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
