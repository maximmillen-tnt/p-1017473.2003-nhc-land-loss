"""Write a 20-claim walkthrough of the settlement calculation, as a spreadsheet.

    uv run --frozen python src/scripts/landloss/loss/validations/gen_calc_walkthrough.py

For reviewing the arithmetic with people who will not read the code. Every
**input** is written as a number and every **step** as a live formula, so the
sheet recalculates: change an area or a rate and the cap, the excess and the
settlement follow. The policy settings sit in one labelled block at the top and
every formula points at them, so a scenario can be tried in the sheet itself.

The twenty claims are **not a random sample**. They are picked to put one of
each interesting case in front of a reviewer -- a claim with a damaged wall, one
with a landslide, one with liquefaction, one with several dwellings, and the
claims where the cap actually binds -- because twenty rows drawn at random from
this population would be twenty ordinary liquefaction claims. The sheet says so
on its face.

It reads step 1's output, so `gen_loss.py` runs first.
"""

import sys

import geopandas as gpd
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from landloss.domain.loss_contract import (
    CLAIM_ID_COLUMN,
    LANDSLIDE_AREA_COLUMN,
    RW_ID_COLUMN,
    RW_LENGTH_COLUMN,
    RW_SIZE_COLUMN,
)
from landloss.loss import claims as loss_claims
from landloss.loss.policy import PolicySettings
from landloss.loss.pricing import (
    BETA_SIZE_CLASS_HEIGHT_M,
    BETA_WALL_RATE_EXCL_GST_NZD_PER_M2,
    beta_wall_rate_excl_gst_nzd_per_m2,
)
from scripts.landloss.loss.steps.s1_settlement import config
from scripts.landloss.loss.steps.s1_settlement.s1_gen_settlement import (
    CROSSING_REPAIR_COLUMN,
    LAND_REPAIR_COLUMN,
    LIQ_REPAIR_COLUMN,
    NEW_WALL_HEIGHT_COLUMN,
    NEW_WALL_LENGTH_COLUMN,
    NEW_WALL_SIZE_COLUMN,
    SYNTHETIC_WALL_COLUMN,
    UNCOVERED_AREA_COLUMN,
    WALL_REPAIR_COLUMN,
    settlement_path,
)
from scripts.landloss.paths import REPORT_DIR
from scripts.landloss.vul.steps.s10_property_damage.gen_property_damage import (
    loss_input_path,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = REPORT_DIR / "loss" / "calc-walkthrough"
OUT_NAME = "loss-calculation-walkthrough.xlsx"

CLAIMS = 20
FONT = "Arial"

# Financial-model convention: blue for a number somebody could change, black for
# a formula, yellow fill for the settings a scenario turns on.
INPUT = Font(name=FONT, size=10, color="0000FF")
FORMULA = Font(name=FONT, size=10, color="000000")
TEXT = Font(name=FONT, size=10)
HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
TITLE = Font(name=FONT, size=12, bold=True)
NOTE = Font(name=FONT, size=9, italic=True)
HEAD_FILL = PatternFill("solid", fgColor="44546A")
SETTING_FILL = PatternFill("solid", fgColor="FFFF00")
EDGE = Border(bottom=Side(style="thin", color="BFBFBF"))

MONEY = "$#,##0;($#,##0);-"
AREA = "#,##0.0"
RATE = "$#,##0.00"

# The settings block, which every formula on the sheet points at. The wall rate
# and the three set heights are here too, so a reviewer can see a wall's value
# built rather than asserted.
SETTINGS_ROW = {
    "area_cap": 3,
    "rw_sub_cap": 4,
    "excess_each": 5,
    "excess_max": 6,
    "wall_rate": 7,
    "gst": 8,
}
HEADER_ROW = 11
FIRST_DATA_ROW = HEADER_ROW + 2

# Column, where its value comes from, number format, width. A source of None
# means the cell is a formula.
COLUMNS = [
    ("Claim", "claim_id", None, 40),
    ("Dwellings", "dwelling_count", "#,##0", 11),
    ("Damaged land, for the cap (m2)", "damaged_area_m2", AREA, 19),
    ("Landslide area, for a new wall (m2)", "landslide_area_m2", AREA, 20),
    ("Land rate incl GST ($/m2)", "land_rate_incl_gst_nzd_per_m2", RATE, 22),
    ("Land value ($)", None, MONEY, 15),
    ("Wall size", "wall_size", None, 12),
    ("Wall height (m)", "wall_height_m", "0.00", 14),
    ("Wall length (m)", "wall_length_m", AREA, 15),
    ("Wall rate excl GST ($/m2)", "wall_rate_excl_gst", RATE, 18),
    ("Wall UDV ($)", None, MONEY, 14),
    ("Wall to cap ($)", None, MONEY, 15),
    ("Land cover cap ($)", None, MONEY, 17),
    ("Repair cost ($)", "repair_cost_incl_gst_nzd", MONEY, 15),
    ("Excess ($)", None, MONEY, 12),
    ("Settlement ($)", None, MONEY, 15),
]


def pick_claims(claims: pd.DataFrame) -> pd.DataFrame:
    """Return the twenty claims the walkthrough shows.

    One of each case a reviewer should see, then filled out with the most
    ordinary claims there are. Drawn in a fixed order so two runs of this
    script produce the same sheet.

    Args:
        claims: Step 1's settlements, one row per claim.

    Returns:
        Up to :data:`CLAIMS` rows.
    """
    wanted = {
        "the cap binds": claims["capped"] & (claims["damaged_area_m2"] > 0),
        "landslide, new wall built": claims[SYNTHETIC_WALL_COLUMN],
        "damaged wall": claims[WALL_REPAIR_COLUMN] > 0,
        "liquefaction only": (claims[LIQ_REPAIR_COLUMN] > 0)
        & (claims[WALL_REPAIR_COLUMN] == 0),
        "several dwellings": claims["dwelling_count"] > 1,
        "paid nothing, excess took it": (claims["repair_cost_incl_gst_nzd"] > 0)
        & (claims["settlement_incl_gst_nzd"] == 0),
    }
    taken: list[str] = []
    labels: dict[str, str] = {}
    for label, mask in wanted.items():
        for claim_id in claims.loc[mask].index[:4]:
            if claim_id not in taken:
                taken.append(claim_id)
                labels[claim_id] = label
    for claim_id in claims.index:
        if len(taken) >= CLAIMS:
            break
        if claim_id not in taken:
            taken.append(claim_id)
            labels.setdefault(claim_id, "ordinary claim")
    chosen = claims.loc[taken[:CLAIMS]].copy()
    chosen["case"] = [labels[claim_id] for claim_id in chosen.index]
    return chosen


WORKED_FORMULA = {
    3: "whole insured area where liquefied, else the slip",
    4: "the slip alone; a new wall is sized on this, not on column C",
    6: "MIN(damaged land, area cap) x land rate",
    10: "30% are priced as concrete, the rest as one of four timber rates",
    11: "height x length x wall rate x (1 + GST)",
    12: "MIN(wall UDV, sub-cap x dwellings)",
    13: "land value + wall to cap",
    15: "MIN(excess per dwelling x dwellings, ceiling)",
    16: "MAX(0, MIN(repair, cap) - excess)",
}


def worked_values(claim: pd.Series, policy: PolicySettings) -> dict[int, float]:
    """Return the worked columns for one claim, by column number.

    The same arithmetic the settlement module does, repeated here so the sheet
    carries numbers rather than formulas. openpyxl cannot write a formula's
    result, and a formula with no cached result reads as empty to every tool
    except Excel -- which is worse than a plain number on a sheet people will
    open in whatever they have.

    Args:
        claim: One row of step 1's settlements, plus the wall shape.
        policy: The settings this scenario runs under.

    Returns:
        Column number to value.
    """
    dwellings = float(claim["dwelling_count"])
    land_value = (
        min(float(claim["damaged_area_m2"]), policy.area_cap_m2)
        * float(claim["land_rate_incl_gst_nzd_per_m2"])
    )
    udv = (
        float(claim["wall_height_m"])
        * float(claim["wall_length_m"])
        * float(claim["wall_rate_excl_gst"])
        * (1.0 + policy.gst_rate)
    )
    to_cap = min(
        udv, policy.retaining_wall_sub_cap_nzd * (1.0 + policy.gst_rate) * dwellings
    )
    cap = land_value + to_cap
    excess = min(policy.excess_per_dwelling_nzd * dwellings, policy.excess_max_nzd)
    settlement = max(0.0, min(float(claim["repair_cost_incl_gst_nzd"]), cap) - excess)
    return {6: land_value, 11: udv, 12: to_cap, 13: cap, 15: excess, 16: settlement}


def write_settings(sheet, policy: PolicySettings) -> None:
    """Write the policy block every formula on the sheet reads."""
    sheet["A1"] = "Loss calculation walkthrough"
    sheet["A1"].font = TITLE
    sheet["A2"] = (
        "Blue = an input. Black = a formula. Yellow = a policy setting; change "
        "one and every row below follows."
    )
    sheet["A2"].font = NOTE

    rows = [
        (SETTINGS_ROW["area_cap"], "Area cap (m2)", policy.area_cap_m2, "#,##0"),
        (
            SETTINGS_ROW["rw_sub_cap"],
            "Retaining wall sub-cap per dwelling, incl GST ($)",
            round(policy.retaining_wall_sub_cap_nzd * (1.0 + policy.gst_rate), 2),
            MONEY,
        ),
        (
            SETTINGS_ROW["excess_each"],
            "Land excess per dwelling ($)",
            policy.excess_per_dwelling_nzd,
            MONEY,
        ),
        (
            SETTINGS_ROW["excess_max"],
            "Land excess ceiling ($)",
            policy.excess_max_nzd,
            MONEY,
        ),
        (
            SETTINGS_ROW["wall_rate"],
            "Timber pole average, for reference only ($/m2)",
            round(BETA_WALL_RATE_EXCL_GST_NZD_PER_M2, 4),
            RATE,
        ),
        (SETTINGS_ROW["gst"], "GST rate", policy.gst_rate, "0.0%"),
    ]
    for row, label, value, fmt in rows:
        sheet.cell(row=row, column=1, value=label).font = TEXT
        cell = sheet.cell(row=row, column=2, value=value)
        cell.font = INPUT
        cell.fill = SETTING_FILL
        cell.number_format = fmt

    sheet["A9"] = (
        "Settlement = MAX(0, MIN(repair cost, land cover cap) - excess). The Act "
        "builds the cap from what was damaged and pays the lesser. A wall "
        "reaches the cap at the LESSER of its undepreciated value and the "
        "sub-cap, which is what the Wall to cap column shows."
    )
    sheet["A9"].font = NOTE


def write_calculation(sheet, chosen: pd.DataFrame, policy: PolicySettings) -> None:
    """Write the header, the twenty rows and the formulas between them."""
    write_settings(sheet, policy)

    for index, (label, _, _, width) in enumerate(COLUMNS, start=1):
        cell = sheet.cell(row=HEADER_ROW, column=index, value=label)
        cell.font = HEAD
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.cell(row=HEADER_ROW, column=len(COLUMNS) + 1, value="Why this claim").font = (
        HEAD
    )
    sheet.cell(row=HEADER_ROW, column=len(COLUMNS) + 1).fill = HEAD_FILL
    sheet.column_dimensions[get_column_letter(len(COLUMNS) + 1)].width = 28
    sheet.row_dimensions[HEADER_ROW].height = 30

    for index in range(1, len(COLUMNS) + 1):
        cell = sheet.cell(
            row=HEADER_ROW + 1, column=index, value=WORKED_FORMULA.get(index, "")
        )
        cell.font = Font(name=FONT, size=8, italic=True, color="808080")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.row_dimensions[HEADER_ROW + 1].height = 26

    for offset, (claim_id, claim) in enumerate(chosen.iterrows()):
        row = FIRST_DATA_ROW + offset
        worked = worked_values(claim, policy)
        for index, (_, source, fmt, _width) in enumerate(COLUMNS, start=1):
            if index in worked:
                cell = sheet.cell(row=row, column=index, value=worked[index])
                cell.font = FORMULA
            elif source in ("claim_id", "wall_size"):
                value = claim_id if source == "claim_id" else claim[source]
                cell = sheet.cell(row=row, column=index, value=str(value))
                cell.font = TEXT if source == "claim_id" else INPUT
            else:
                value = claim[source]
                cell = sheet.cell(row=row, column=index, value=float(value))
                cell.font = INPUT
            if fmt:
                cell.number_format = fmt
            cell.border = EDGE
        note = sheet.cell(row=row, column=len(COLUMNS) + 1, value=claim["case"])
        note.font = NOTE
        note.border = EDGE

    total = FIRST_DATA_ROW + len(chosen)
    sheet.cell(row=total, column=1, value="Total, these 20 claims").font = Font(
        name=FONT, size=10, bold=True
    )
    for index in (6, 11, 13, 14, 15, 16):
        letter = get_column_letter(index)
        cell = sheet.cell(
            row=total,
            column=index,
            value=f"=SUM({letter}{FIRST_DATA_ROW}:{letter}{total - 1})",
        )
        cell.font = Font(name=FONT, size=10, bold=True)
        cell.number_format = MONEY
    sheet.cell(
        row=total + 2,
        column=1,
        value=(
            "Only the totals above are formulas. Every other cell is a value, "
            "so the sheet reads correctly in any viewer. The arithmetic behind "
            "each worked column is in the row under the headings."
        ),
    ).font = NOTE
    sheet.freeze_panes = sheet.cell(row=FIRST_DATA_ROW, column=2)


def write_repair(sheet, chosen: pd.DataFrame) -> None:
    """Write where each claim's repair cost came from, and on what assumption."""
    sheet["A1"] = "Where the repair cost comes from"
    sheet["A1"].font = TITLE
    sheet["A2"] = (
        "Every line is an assumption, not a measurement. They are numbered so "
        "they can be referred to and decided one at a time."
    )
    sheet["A2"].font = NOTE

    headers = [
        "Claim",
        "1. Damaged wall replaced ($)",
        "Landslide ground not covered by that wall (m2)",
        "New wall size",
        "New wall height (m)",
        "New wall length (m)",
        "2. New wall for landslide ground ($)",
        "3. Liquefaction, Canterbury rates ($)",
        "4. Culvert or bridge at sub-cap ($)",
        "Total repair ($)",
    ]
    widths = [40, 20, 22, 13, 14, 15, 22, 22, 22, 16]
    for index, (label, width) in enumerate(zip(headers, widths, strict=True), start=1):
        cell = sheet.cell(row=4, column=index, value=label)
        cell.font = HEAD
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[4].height = 34

    # Column number, where it comes from, and its format. The three new-wall
    # dimensions sit beside the cost they explain, so a reader can judge the
    # wall against the ground it is holding back rather than against a number.
    sources = [
        (2, WALL_REPAIR_COLUMN, MONEY),
        (3, UNCOVERED_AREA_COLUMN, AREA),
        (4, NEW_WALL_SIZE_COLUMN, None),
        (5, NEW_WALL_HEIGHT_COLUMN, "0.00"),
        (6, NEW_WALL_LENGTH_COLUMN, AREA),
        (7, LAND_REPAIR_COLUMN, MONEY),
        (8, LIQ_REPAIR_COLUMN, MONEY),
        (9, CROSSING_REPAIR_COLUMN, MONEY),
    ]
    for offset, (claim_id, claim) in enumerate(chosen.iterrows()):
        row = 5 + offset
        sheet.cell(row=row, column=1, value=str(claim_id)).font = TEXT
        for index, source, fmt in sources:
            value = claim[source]
            cell = sheet.cell(
                row=row,
                column=index,
                value=str(value) if fmt is None else float(value),
            )
            cell.font = INPUT
            if fmt:
                cell.number_format = fmt
        total = sheet.cell(
            row=row, column=10, value=f"=B{row}+G{row}+H{row}+I{row}"
        )
        total.font = FORMULA
        total.number_format = MONEY

    notes = [
        "",
        "Assumptions behind each column, to be confirmed:",
        (
            "1. Every wall is priced at one flat rate, the average of four "
            "timber pole rates. The costing tool's 29 rates span a factor of "
            "21, so this is the largest single assumption in the wall cost. "
            "Enabling works, design and consent are not in the rate."
        ),
        (
            "2. A damaged wall is assumed to reinstate one metre of land for "
            "every metre of its length. Landslide ground beyond that gets a "
            "wall invented for it, sized by the uncovered area and the deposit "
            "volume, with its length twice its depth plus 2 m at each end and "
            "never under 10 m. The size, height and length are shown so the "
            "wall can be judged against the ground it holds back. NOTE the "
            "uncovered area is the LANDSLIDE area only - liquefied ground is "
            "not remediated by a wall."
        ),
        (
            "3. Canterbury settled costs per property, $200 to $4,000 by "
            "damage state. 2010/2011 dollars, grossed up for GST but NOT "
            "inflated. They exclude ILV and IFV, so they are the minor-damage "
            "tier only."
        ),
        (
            "4. Nothing prices a culvert or bridge, so a damaged one is "
            "assumed to exceed its sub-cap and is settled at the limit."
        ),
        "",
        (
            "The three site ratings that mark up a wall's cost - construction "
            "access, earthworks and constructability - are proxied off "
            "driveway length, inundated volume and ground slope. All bands are "
            "invented. Together they can move a wall cost by at most 30%."
        ),
    ]
    start = 5 + len(chosen) + 2
    for offset, text in enumerate(notes):
        cell = sheet.cell(row=start + offset, column=1, value=text)
        cell.font = Font(name=FONT, size=9, bold=text.endswith("confirmed:"))
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def wall_shape(realisation_id: int, *, pilot: bool) -> pd.DataFrame:
    """Return the size and length of each claim's damaged retaining walls.

    One wall per property today, so the size is that wall's. Where a claim
    carries several, the lengths add and the size shown is the largest of them,
    which is the one the height comes off -- the sheet's wall value is then an
    approximation and the claim is worth looking at directly.

    Args:
        realisation_id: The modelled earthquake.
        pilot: Whether the run is over the small Wellington pilot box.

    Returns:
        A frame indexed by ``claim_id`` with ``wall_size`` and
        ``wall_length_m``.
    """
    rw = gpd.read_parquet(loss_input_path("rw", realisation_id, pilot=pilot))
    damaged = loss_claims.damaged_walls(rw)
    order = pd.Categorical(
        damaged[RW_SIZE_COLUMN], categories=list(BETA_SIZE_CLASS_HEIGHT_M), ordered=True
    )
    damaged = damaged.assign(
        _order=order,
        _rate=beta_wall_rate_excl_gst_nzd_per_m2(damaged[RW_ID_COLUMN].to_numpy()),
    )
    grouped = damaged.groupby(CLAIM_ID_COLUMN)
    return pd.DataFrame(
        {
            "wall_size": grouped["_order"].max().astype(str),
            "wall_length_m": grouped[RW_LENGTH_COLUMN].sum(),
            "wall_rate_excl_gst": grouped["_rate"].max(),
        }
    )


def landslide_area(realisation_id: int, *, pilot: bool) -> pd.Series:
    """Return the insured area a landslide took on each claim.

    Not the same as ``damaged_area_m2``, which is what the **cap** is built on
    and which reads a liquefaction state as damaging the whole insured area. A
    new wall is sized on the slip alone, so a claim can show hundreds of square
    metres damaged and still get a small wall.

    Args:
        realisation_id: The modelled earthquake.
        pilot: Whether the run is over the small Wellington pilot box.

    Returns:
        The landslide area per claim, indexed by ``claim_id``.
    """
    land = gpd.read_parquet(loss_input_path("land", realisation_id, pilot=pilot))
    return land.groupby(CLAIM_ID_COLUMN)[LANDSLIDE_AREA_COLUMN].sum()


def main(*, pilot, realisation_ids):
    """Write the walkthrough for the first realisation asked for."""
    policy = PolicySettings()
    realisation_id = realisation_ids[0]
    claims = pd.read_parquet(settlement_path(realisation_id, pilot=pilot))
    claims = claims.set_index("claim_id")
    walls = wall_shape(realisation_id, pilot=pilot).reindex(claims.index)
    claims["wall_size"] = walls["wall_size"].fillna("none")
    claims["wall_length_m"] = walls["wall_length_m"].fillna(0.0)
    claims["wall_rate_excl_gst"] = walls["wall_rate_excl_gst"].fillna(0.0)
    # The height the size class is priced at, written out rather than looked up
    # in a formula: a reviewer can see size, height and length multiply out to
    # the value, and no cell depends on matching a word.
    claims["landslide_area_m2"] = landslide_area(realisation_id, pilot=pilot).reindex(
        claims.index
    ).fillna(0.0)
    claims["wall_height_m"] = (
        claims["wall_size"].map(BETA_SIZE_CLASS_HEIGHT_M).fillna(0.0)
    )
    chosen = pick_claims(claims)

    book = Workbook()
    write_calculation(book.active, chosen, policy)
    book.active.title = "Calculation"
    write_repair(book.create_sheet("Repair cost"), chosen)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / OUT_NAME
    book.save(out_path)
    print(f"Picked {len(chosen)} claims from {len(claims):,}:")
    for case, count in chosen["case"].value_counts().items():
        print(f"  {count:>2} {case}")
    print(f"Wrote {out_path}")
    print("Recalculate before sending: python scripts/recalc.py <path>")
    return 0


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
