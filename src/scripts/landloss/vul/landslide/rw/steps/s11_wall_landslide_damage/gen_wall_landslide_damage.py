"""Flag each retaining wall a landslide reached.

Intersects every insured wall with the landslide realisation and writes whether
it touches evacuated ground, inundated ground, or both.

    uv run --frozen python src/scripts/landloss/vul/landslide/rw/steps/s11_wall_landslide_damage/gen_wall_landslide_damage.py

A wall is not measured by how much ground a landslide took from it, as land is,
but by whether a landslide reached it at all, so this step writes flags rather
than areas. The two kinds of ground stay apart because the policy settles them
differently.

**No cost is attached.** The flags are what the loss module prices.

What it runs over comes from ``config.py`` beside it.
"""

import sys

import geopandas as gpd

from landloss.domain.loss_contract import (
    CLAIM_ID_COLUMN,
    IS_EVACUATED_COLUMN,
    IS_INUNDATED_COLUMN,
    REALISATION_ID_COLUMN,
    RW_ID_COLUMN,
)
from landloss.vul.landslide.flags import landslide_flags
from scripts.landloss.exposure.rw.steps.s6_wall_population.gen_wall_population import (
    wall_population_path,
)
from scripts.landloss.hazard.landslide.steps.s1_landslide_realisation.s1_simulate_landslides import (
    realisation_path,
)
from scripts.landloss.paths import TEMP_DIR
from scripts.landloss.vul.landslide.rw.steps.s11_wall_landslide_damage import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "vul"
OUT_STEM = "wall-landslide-damage"
RULE = "-" * 72


def wall_landslide_damage_path(realisation_id, *, pilot):
    """Return the file a run writes one realisation's wall flags to."""
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.parquet"


def describe_flags(flags, landslides):
    """Print how many walls each kind of landslide ground reached."""
    evacuated = flags[IS_EVACUATED_COLUMN]
    inundated = flags[IS_INUNDATED_COLUMN]
    print(RULE)
    print(f"Landslide polygons: {len(landslides):,}")
    print(f"Walls: {len(flags):,}")
    print(f"  evacuated: {int(evacuated.sum()):,}")
    print(f"  inundated: {int(inundated.sum()):,}")
    print(f"  both: {int((evacuated & inundated).sum()):,}")


def main(*, pilot, realisation_ids):
    """Write the landslide flags per retaining wall, per realisation."""
    for realisation_id in realisation_ids:
        walls_path = wall_population_path(realisation_id, pilot=pilot)
        print(f"Reading the walls from {walls_path} ...", flush=True)
        walls = gpd.read_parquet(walls_path)

        slides_path = realisation_path(pilot=pilot, realisation_id=realisation_id)
        print(f"Reading the landslides from {slides_path} ...", flush=True)
        landslides = gpd.read_parquet(slides_path)

        flags = landslide_flags(walls, landslides, id_column=RW_ID_COLUMN)
        flags.insert(0, REALISATION_ID_COLUMN, realisation_id)
        claims = walls.set_index(RW_ID_COLUMN)[CLAIM_ID_COLUMN]
        flags.insert(2, CLAIM_ID_COLUMN, flags[RW_ID_COLUMN].map(claims))
        describe_flags(flags, landslides)

        out_path = wall_landslide_damage_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        flags.to_parquet(out_path)
        print(f"Wrote {len(flags):,} rows to {out_path}")

    print(RULE)
    print("Flags only. Nothing here is priced.")


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
