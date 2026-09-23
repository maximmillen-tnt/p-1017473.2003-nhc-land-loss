"""Run the whole pipeline end to end: exposure, hazard, then vul.

    uv run --frozen python src/scripts/landloss/gen_all.py

Each module runs through its own ``gen_<module>.py``, with the extent and
realisations set in ``config.py`` beside this, so every module runs over the
same ground and the same earthquakes. It ends at the four tables the loss
module reads, ``temp/vul/loss-input-<table>-r<nnn>[-pilot].geoparquet``; the
loss module itself is not run from here.
"""

from scripts.landloss import config
from scripts.landloss.exposure import gen_exposure
from scripts.landloss.hazard import gen_hazard
from scripts.landloss.vul import gen_vul


def main(*, pilot, realisation_ids):
    """Run every module in order.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to run.
    """
    for module in (gen_exposure, gen_hazard, gen_vul):
        module.main(pilot=pilot, realisation_ids=realisation_ids)


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
