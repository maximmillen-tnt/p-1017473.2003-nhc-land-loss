"""Run every hazard step end to end.

    uv run --frozen python src/scripts/landloss/hazard/gen_hazard.py

Shaking, then liquefaction, then landslide, for the extent and realisations set
in ``config.py`` beside this. The hazards read no exposure, so this can run
before or after the exposure module. Anything else a step reads comes from that
step's own ``config.py``.

The slope failure susceptibility step is not run: nothing downstream reads it
yet, as it rebuilds the GWRC model for comparison against the supplied grid
rather than feeding the chain.
"""

from scripts.landloss.hazard import config
from scripts.landloss.hazard.landslide.steps.s1_landslide_realisation import (
    config as landslide_config,
)
from scripts.landloss.hazard.landslide.steps.s1_landslide_realisation import (
    s1_simulate_landslides,
)
from scripts.landloss.hazard.liquefaction.steps.s2_ld_probabilities import (
    gen_liq_ld_probabilities,
)
from scripts.landloss.hazard.liquefaction.steps.s3_ld_states import (
    gen_liq_ld_states,
)
from scripts.landloss.hazard.shaking.steps.s1_pga_realisation import (
    gen_pga_realisations,
)
from scripts.landloss.pipeline import run_steps


def main(*, pilot, realisation_ids):
    """Run the hazard steps in order.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to run.
    """
    ids = {"pilot": pilot, "realisation_ids": realisation_ids}
    run_steps(
        "hazard",
        [
            (
                "shaking s1, PGA realisations",
                lambda: gen_pga_realisations.main(**ids),
            ),
            (
                "liquefaction s2, land damage probabilities",
                lambda: gen_liq_ld_probabilities.main(pilot=pilot),
            ),
            (
                "liquefaction s3, land damage states",
                lambda: gen_liq_ld_states.main(**ids),
            ),
            (
                "landslide s1, landslide realisations",
                lambda: s1_simulate_landslides.main(
                    **ids, use_cached_dem=landslide_config.USE_CACHED_DEM
                ),
            ),
        ],
    )


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
