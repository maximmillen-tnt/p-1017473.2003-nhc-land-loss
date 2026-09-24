"""Run every loss step end to end, over the four tables vul hands across.

    uv run --frozen python src/scripts/landloss/loss/gen_loss.py

Reads what the vulnerability module wrote, so `gen_vul.py` runs first, and with
it the exposure and hazard modules it depends on. One step today: step 0 builds
the land cover cap on each claim, ``temp/loss/land-cover-cap-r<nnn>[-pilot].parquet``.

The extent and realisations come from ``config.py`` beside this; anything else a
step reads comes from that step's own ``config.py``.

**The module stops at the cap rather than at a settlement.** A settlement is
``min(repair cost, cap)`` less the excess, and nothing produces a repair cost
yet -- a wall's needs the three site ratings (**Q-10**) and damaged land has no
Land SOW behind it. The settlement step joins this pipeline when one of them
does, which is why the module already runs through a pipeline rather than a
single script.
"""

from scripts.landloss.loss import config
from scripts.landloss.loss.steps.s0_land_cover_cap import s0_gen_land_cover_cap
from scripts.landloss.pipeline import run_steps


def main(*, pilot, realisation_ids):
    """Run the loss steps in order.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to run.
    """
    ids = {"pilot": pilot, "realisation_ids": realisation_ids}
    run_steps(
        "loss",
        [
            (
                "s0, the land cover cap per claim",
                lambda: s0_gen_land_cover_cap.main(**ids),
            ),
        ],
    )


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
