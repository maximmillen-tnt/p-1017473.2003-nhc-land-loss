"""Flag which culverts and bridges a landslide reached.

Intersects the landslide realisation against the crossing population and writes,
for every crossing, whether it sits on evacuated ground, under inundated ground,
or both.

    uv run --frozen python src/scripts/landloss/vul/landslide/culverts_bridges/steps/s11_crossing_landslide_damage/gen_crossing_landslide_damage.py

The damage measure here is **a flag, not an area**. A culvert or a bridge is
not settled by how much ground a landslide took from it, as land is, but by
whether a landslide reached it at all, so the question per crossing is yes or
no. The two kinds of ground stay apart because the policy settles them
differently: evacuated ground is loss of support, inundated ground is debris
arriving from upslope.

Every crossing is written, one row each, with both flags False where no
landslide reached it. The flags are computed for culverts and bridges alike;
the split by structure kind happens at the loss handover.

What it runs over comes from ``config.py`` beside it.
"""

import sys

import geopandas as gpd

from landloss.domain.loss_contract import (
    CLAIM_ID_COLUMN,
    CROSSING_ID_COLUMN,
    IS_EVACUATED_COLUMN,
    IS_INUNDATED_COLUMN,
    REALISATION_ID_COLUMN,
)
from landloss.vul.landslide.flags import landslide_flags
from scripts.landloss.exposure.culverts_bridges.steps.s7_crossing_population.gen_crossing_population import (
    crossing_population_path,
)
from scripts.landloss.hazard.landslide.steps.s1_landslide_realisation.s1_simulate_landslides import (
    realisation_path,
)
from scripts.landloss.paths import TEMP_DIR
from scripts.landloss.vul.landslide.culverts_bridges.steps.s11_crossing_landslide_damage import (
    config,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "vul"
OUT_STEM = "crossing-landslide-damage"
RULE = "-" * 72


def crossing_landslide_damage_path(realisation_id, *, pilot):
    """Return the file a run writes one realisation's crossing flags to."""
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.parquet"


def describe_damage(damaged, landslides):
    """Print how many crossings each kind of damaged ground reached."""
    print(RULE)
    print(f"Landslide polygons: {len(landslides):,}")
    if damaged.empty:
        print("  no crossings over this extent")
        return
    print(f"Crossings: {len(damaged):,}")
    for column in (IS_EVACUATED_COLUMN, IS_INUNDATED_COLUMN):
        print(f"  {column}: {int(damaged[column].sum()):,}")
    both = damaged[IS_EVACUATED_COLUMN] & damaged[IS_INUNDATED_COLUMN]
    print(f"  both: {int(both.sum()):,}")


def main(*, pilot, realisation_ids):
    """Write the landslide flags per crossing, per realisation."""
    for realisation_id in realisation_ids:
        crossings_path = crossing_population_path(realisation_id, pilot=pilot)
        print(f"Reading the crossings from {crossings_path} ...", flush=True)
        crossings = gpd.read_parquet(crossings_path)
        if CROSSING_ID_COLUMN not in crossings.columns:
            msg = (
                f"{crossings_path} carries no {CROSSING_ID_COLUMN!r}; rerun "
                "exposure step 5 and then step 7"
            )
            raise ValueError(msg)

        slides_path = realisation_path(pilot=pilot, realisation_id=realisation_id)
        print(f"Reading the landslides from {slides_path} ...", flush=True)
        landslides = gpd.read_parquet(slides_path)

        damaged = landslide_flags(crossings, landslides, id_column=CROSSING_ID_COLUMN)
        damaged.insert(1, CLAIM_ID_COLUMN, crossings[CLAIM_ID_COLUMN].to_numpy())
        damaged.insert(0, REALISATION_ID_COLUMN, realisation_id)
        describe_damage(damaged, landslides)

        out_path = crossing_landslide_damage_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        damaged.to_parquet(out_path)
        print(f"Wrote {len(damaged):,} rows to {out_path}")


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
