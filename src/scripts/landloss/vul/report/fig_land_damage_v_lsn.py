"""Plot settled Canterbury land damage against modelled LSN.

One panel holds every property, and the five that follow split them by the land
damage category surveyed on the ground after the event. Reading the panels
together is the point: it shows both how land damage cost rises with LSN, and
how much of the scatter at any given LSN is explained by what was actually
observed on the property rather than by the model.

    uv run --frozen python src/scripts/landloss/vul/report/fig_land_damage_v_lsn.py

Reads the database built by
``src/scripts/landloss/vul/steps/s1_ces_observed_damage/gen_observed_damage_db.py``
through ``landloss.io.versioned_store.read_vul`` (T: by default, or a local
cache/working copy depending on configuration). Pass --database to read from
an explicit path instead, or --event to draw a single event instead of all
four figures.

The layout follows ``fig_bdr_v_lsn.py`` in the National Liquefaction Model loss
repository, so a panel from this study can be read against one from that one.
"""

import argparse
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")  # non-interactive: this script only writes PNGs

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from landloss.io import versioned_store

# Repo root, from src/scripts/landloss/vul/report/ -- five levels up.
REPO_ROOT = Path(__file__).resolve().parents[5]
FIG_DIR = REPO_ROOT / "report" / "vul" / "liq" / "fig"

# Written by ../steps/s1_ces_observed_damage/gen_observed_damage_db.py through
# landloss.io.versioned_store.save_vul, not a hardcoded T: path.
DB_SUB_DIRS = ["ces_observed_damage"]
DB_NAME = "observed_damage_db.parquet"

DPI = 200
FIGSIZE = (12, 8)

# The land damage settled, in dollars. The distribution has a long tail -- a
# handful of properties written off entirely -- so the axis is capped and the
# values clipped to it. Clipping rather than filtering keeps the pile-up at the
# top visible, so a reader can see how much is off the end of the scale.
DAMAGE_COLUMN = "land_assessment"
DAMAGE_LABEL = "Land damage"
DAMAGE_CAP = 20_000

LSN_COLUMN = "lsn_p50"
CATEGORY_COLUMN = "observed_land_damage_category"
EVENT_COLUMN = "simple_event_name"

# Ordered worst last, which is also the panel order. Colours are the National
# Liquefaction Model's, so the same category reads the same across both studies.
COLOURS = {
    "Unknown": "black",
    "None Observed": "#3AB04A",
    "Minor": "#FEE900",
    "Moderate": "#F8951D",
    "Major +": "#9D1C1F",
}

EVENT_LABELS = {
    "darfield": "Darfield, September 2010",
    "chch_feb_2011": "Christchurch, February 2011",
    "chch_feb_2016": "Christchurch, February 2016",
}

RULE = "-" * 72


def describe(database):
    """Print what the database holds, so a bad join is caught before plotting."""
    print(RULE)
    print(f"Loaded {len(database):,} property-event rows")

    print(f"\n  {'Event':<30} {'Rows':>8} {'With LSN':>9} {'Observed':>9}")
    for event, label in EVENT_LABELS.items():
        subset = database.loc[database[EVENT_COLUMN] == event]
        if subset.empty:
            continue
        print(
            f"  {label:<30} {len(subset):>8,}"
            f" {int(subset[LSN_COLUMN].notna().sum()):>9,}"
            f" {int(subset[CATEGORY_COLUMN].notna().sum()):>9,}"
        )

    print("\n  Observed land damage category:")
    counts = database[CATEGORY_COLUMN].value_counts(dropna=False)
    for category in COLOURS:
        print(f"    {category:<18} {counts.get(category, 0):>9,}")
    print(
        f"    {'No observation':<18} {int(database[CATEGORY_COLUMN].isna().sum()):>9,}"
    )


def polyfit(ax, x, y):
    """Draw a straight-line least squares fit through the points, if there are any."""
    usable = (~np.isnan(x)) & (~np.isnan(y))
    if usable.sum() < 2:
        return

    coefficients = np.polyfit(x[usable], y[usable], 1)
    x_fit = np.linspace(x[usable].min(), x[usable].max(), 100)
    ax.plot(x_fit, np.polyval(coefficients, x_fit), color="black", ls=":", lw=1.5)


def draw_category(ax, database, category, colour):
    """Draw one category's points, and its mean and median, on an axes.

    Args:
        ax: The axes to draw on.
        database: The rows to draw from, already cut to one event if wanted.
        category: The observed land damage category to select.
        colour: The colour for the category.

    Returns:
        The selected rows' LSN and damage as arrays, for the caller to fit.
    """
    selected = database.loc[database[CATEGORY_COLUMN] == category]
    x = selected[LSN_COLUMN].to_numpy(dtype="float64")
    y = selected[DAMAGE_COLUMN].clip(upper=DAMAGE_CAP).to_numpy(dtype="float64")

    # Small, translucent markers: at a hundred thousand properties the cloud is
    # mostly overplotted, and the density is the thing worth seeing.
    ax.scatter(x, y, alpha=0.5, s=0.1, color=colour)

    # An all-NaN slice would make nanmedian warn rather than return, and a
    # category with no settled damage at all is a real possibility per event.
    if np.isfinite(y).any():
        ax.axhline(np.nanmedian(y), color=colour, ls="--", lw=1, alpha=0.7)
        ax.axhline(np.nanmean(y), color=colour, ls="-", lw=1, alpha=0.7)

    return x, y


def add_legend(ax):
    """Put the category and line-style key on one panel, rather than on all six."""
    handles = [Patch(facecolor=colour, label=cat) for cat, colour in COLOURS.items()]
    handles += [
        Line2D([], [], color="black", lw=1, ls="--", label=f"Median {DAMAGE_LABEL}"),
        Line2D([], [], color="black", lw=1, ls="-", label=f"Mean {DAMAGE_LABEL}"),
        Line2D([], [], color="black", lw=1.5, ls=":", label="Linear fit"),
    ]
    ax.legend(
        handles=handles,
        title="Observed land damage category",
        loc="upper right",
        fontsize="x-small",
        title_fontsize="x-small",
        alignment="left",
    )


def plot_land_damage_v_lsn(database, title):
    """Draw the six panel figure for one event, or for every event together.

    Args:
        database: The rows to draw.
        title: The figure title.

    Returns:
        The figure, ready to save.
    """
    fig, axs = plt.subplots(nrows=2, ncols=3, figsize=FIGSIZE, sharex=True, sharey=True)
    combined = axs[0, 0]

    for (category, colour), ax in zip(COLOURS.items(), axs.flatten()[1:], strict=True):
        draw_category(combined, database, category, colour)
        x, y = draw_category(ax, database, category, colour)
        polyfit(ax, x, y)
        ax.set_title(f"{category} ({len(x):,})", fontsize=10)

    # The combined panel is fitted over everything, including the properties no
    # observation polygon covered, which none of the five panels show.
    polyfit(
        combined,
        database[LSN_COLUMN].to_numpy(dtype="float64"),
        database[DAMAGE_COLUMN].clip(upper=DAMAGE_CAP).to_numpy(dtype="float64"),
    )
    combined.set_title(f"All categories ({len(database):,})", fontsize=10)

    for ax in axs.flatten():
        ax.set_ylim(0, DAMAGE_CAP)
        ax.set_xlim(left=0)

    # The axes are shared, so only the outer ones are labelled; repeating the
    # label under all six panels crowds out the panel titles.
    for ax in axs[-1, :]:
        ax.set_xlabel("LSN (p50)")
    for ax in axs[:, 0]:
        ax.set_ylabel(f"{DAMAGE_LABEL} ($, capped at {DAMAGE_CAP:,})")

    add_legend(axs[0, 2])
    fig.suptitle(title)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=(
            "The observed damage database from the s1_ces_observed_damage "
            "step. Without it, read from the vul versioned data store."
        ),
    )
    parser.add_argument(
        "--event",
        choices=sorted(EVENT_LABELS),
        help="Draw only this event. Without it, every event and the combined figure.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=FIG_DIR,
        help="Where to write the figures.",
    )
    args = parser.parse_args()

    if args.database is not None:
        if not args.database.exists():
            print(f"Cannot reach {args.database}")
            return 1
        database = gpd.read_parquet(args.database)
    else:
        try:
            database = versioned_store.read_vul(fname=DB_NAME, sub_dirs=DB_SUB_DIRS)
        except ValueError as err:
            print(err)
            print("\nRun the s1_ces_observed_damage step first.")
            return 1

    describe(database)

    if args.event:
        figures = {args.event: EVENT_LABELS[args.event]}
    else:
        figures = {"all": "All events", **EVENT_LABELS}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(RULE)
    for event, label in figures.items():
        subset = (
            database
            if event == "all"
            else database.loc[database[EVENT_COLUMN] == event]
        )
        if subset.empty:
            print(f"No rows for {label}, skipping")
            continue

        fig = plot_land_damage_v_lsn(subset, label)
        out = args.out_dir / f"land-damage-v-lsn-{event}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {out}")

    return 0


if __name__ == "__main__":
    # Only raise on failure. Falling off the end already exits 0, so the shell
    # contract is unchanged, but running this under an IPython or PyCharm console
    # no longer ends in a "SystemExit: 0" traceback that reads like a crash.
    status = main()
    if status:
        raise SystemExit(status)
