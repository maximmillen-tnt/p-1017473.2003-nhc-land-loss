---
name: adding-steps-scripts
description: How a step is laid out under src/scripts/landloss/<module>/steps/ — its own numbered folder holding the scripts, a phased implementation plan with progress checked off, and a method file describing what is actually implemented and pointing at where each piece lives. Use whenever adding a new step to any module, changing the scripts inside an existing step, or asked where a step's methodology or its planned work is written down.
---

# Adding and changing step scripts

A step is a stage of a module's build: ordered, re-runnable, and owned by one
folder. Every step in the repository carries the same two markdown files beside
its scripts — a plan of what is intended, and a method description of what is
actually there. This skill defines that convention and what has to happen to the
two files when the scripts change.

The split exists because the two documents are read at different times by
different people. The project report is assembled later, from method files that
are already current; the team meanwhile keeps iterating quickly on the scripts.
If the methodology only ever existed as intent, writing the report would mean
reverse engineering four modules' worth of scripts at the point when there is
least time to do it. Keeping the description current as the work happens is
cheaper than reconstructing it afterwards.

The guiding rule follows from that: **the method file describes what the code
does today, never what it is meant to do.** Anything aspirational — a refinement
not yet coded, a dataset not yet obtained, a simplification to be revisited —
belongs in the implementation plan and nowhere else.

## 1. The layout of a step folder

Each step lives in its own numbered subfolder under the module's `steps/`
directory, named `s<n>_<topic>`:

```text
src/scripts/landloss/exposure/steps/
    __init__.py
    s1_parcels/
        __init__.py
        s1_parcels_implementation_plan.md
        s1_parcels_method.md
        gen_insured_land.py
        fig_insured_land_extent.py
    s2_land_value/
        __init__.py
        s2_land_value_implementation_plan.md
        s2_land_value_method.md
        get_rating_values.py
        gen_land_value_per_parcel.py
```

The number carries the run order, so a step folder is not renumbered once other
steps or documents refer to it. The two markdown files are prefixed with the step
folder's own name, which keeps them distinguishable when several are open at once
and makes them findable by name across modules.

Both markdown files are **tracked in git**. They are the step's documentation,
not scratch notes, and their diffs are how a reviewer sees the methodology change
alongside the code that changed it.

Every new folder needs an `__init__.py` with a one-line module docstring, matching
the existing `"""Steps that build the exposure model."""` in each `steps/`
package. Scripts inside follow the naming prefixes in `AGENTS.md` — `fig_`,
`table_`, `gen_`, `get_` — and the script pattern in
`src/scripts/landloss/hazard/report/fig_waterway_map.py`: a module docstring
carrying the literal run command and any required `.env` keys, `argparse` with
`description=__doc__`, and `def main()` returning 0 or 1.

## 2. The implementation plan

`<step>_implementation_plan.md` is written in phases, with progress marked off in
markdown checkboxes as each phase completes. It is the only place intent lives,
so it holds the work not yet done, the shortcuts taken deliberately, and the
improvements someone has asked for but that are not in the code.

Ticking a box is a statement that the code exists and runs, not that it was
started. A phase that turned out to be unnecessary is marked `Dropped` with a
reason rather than deleted — why a phase was abandoned is often the thing a later
reader needs.

Copy this template:

```markdown
# Step 2 — Land value: implementation plan

**Status:** Phase 2 in progress.

## Phase 1 — Source the rating values (complete)

- [x] Read the rating valuation layer for the study area (`get_rating_values.py`).
- [x] Confirm the parcel identifier joins to the exposure parcels.
- [x] Check the coverage across the four territorial authorities.

## Phase 2 — Derive a land value per parcel

- [x] Split the capital value into land and improvement components.
- [ ] Handle parcels carrying no valuation — currently dropped, which needs a
      decision on whether to infer a value from neighbours.
- [ ] Figure showing the land value distribution by territorial authority.

## Phase 3 — Revalue to the study date

- [ ] Apply an index from valuation date to the study date. Not started; the
      index source is still to be agreed with NHC.

## Potential future improvements

- Use sale prices rather than rating valuations where they are available; more
  accurate, but the data is not held for the full study area.
- Value the land separately from the retaining walls on it, which the current
  single figure per parcel does not distinguish.
```

## 3. The method file

`<step>_method.md` is a bullet-point description of the methodology **as
currently implemented**. Each bullet says what the step does and points at where
that information actually lives — the script, the function, the asset file, the
figure — rather than restating the content in prose.

This pointing rule is the substance of the convention. The project lead's own
example: the main centres the step uses are described as being *shown in the
figure produced by `fig_town_centres.py`*, rather than the list of centres being
retyped into the file. A restated list is a second copy that goes stale silently
the first time the script changes; a pointer cannot. So write a bullet as a
sentence about what happens, with the artefact that carries the detail named in
it.

Write plainly about what the code does. Do not hedge, do not describe
alternatives considered, and do not write "will" — any sentence with a "will" in
it belongs in the plan file.

The file **ends** with exactly this line, so a reader who wants to know what is
missing is sent to the one place that says:

```text
Potential future improvements: see `<step>_implementation_plan.md`.
```

Copy this template:

```markdown
# Step 2 — Land value: method

- Rating valuations are read for the four territorial authorities in the study
  area by `get_rating_values.py`, which pulls the valuation layer through
  Koordinates and clips it to the study extent.
- The valuation is joined to the exposure parcels on the parcel identifier by
  `join_valuations_to_parcels()` in `gen_land_value_per_parcel.py`. Parcels with
  no matching valuation are dropped, and the count dropped is printed by the run.
- Land value is taken as the land component of the rating valuation, not the
  capital value, so buildings are excluded — the split is done in
  `split_capital_value()`.
- The coverage achieved across the study area is shown in the figure produced by
  `fig_land_value_coverage.py`, written to `report/exposure/land_value/fig/`.
- Valuations are used at their own valuation date; no revaluation to a common
  date is applied.

Potential future improvements: see `s2_land_value_implementation_plan.md`.
```

Note the fourth bullet naming a figure rather than describing it, and the last
one stating a simplification flatly. Both are true of the code as it stands, and
both are what the report needs.

## 4. Any script change updates the method file

**A change to a step's scripts updates that step's method file in the same
change.** Preventing drift between the two is the entire reason the convention
exists, and a method file three commits behind the code is worse than no method
file, because it is believed.

In practice:

| What changed in the scripts | What happens in the method file |
| --- | --- |
| A new script, or a new stage within one | A new bullet naming it |
| A function renamed or moved | The bullet pointing at it is corrected |
| A default, threshold or dataset swapped | The bullet stating the old one is rewritten |
| A figure added | A bullet naming the script and its `fig/` directory |
| A simplification implemented properly | The bullet describing it is rewritten, and the matching plan box is ticked |
| A script deleted | Its bullet is deleted |

If a change implements something the plan listed, tick the box in the plan **and**
add or rewrite the method bullet. Those two edits belong in the same commit as the
code; splitting them into a follow-up is how drift starts.

Only the method file is constrained this way. The plan can be edited on its own
whenever the intent changes, which is expected.

## 5. Figures and where plotting lives

Figures produced by a step go to `report/<module>/<topic>/fig/`, resolved from
`Path(__file__).resolve().parents[N]` rather than a hardcoded path. Any directory
named `fig` is gitignored, so figures are regenerated rather than committed and
the script is the record of how each one was made. That is exactly why a method
bullet may point at a figure: the figure itself is not in the repository, but the
script that draws it always is.

Keep the plotting logic in the step's script. Only genuinely shared styling — the
map panel helpers in `src/landloss/common/utils/plot.py` — belongs in the
library. A figure script is `fig_`, never `plot_`.

## 6. Checklist: adding a new step

1. Create `src/scripts/landloss/<module>/steps/s<n>_<topic>/` with an
   `__init__.py` carrying a one-line module docstring.
2. Write `s<n>_<topic>_implementation_plan.md` first, in phases, with every box
   unticked. Writing the phases before the code is what makes the plan worth
   reading later.
3. Write the scripts, following the naming prefixes and the script pattern.
4. Write `s<n>_<topic>_method.md` describing what you actually built, with every
   bullet pointing at a script, function, asset or figure, and ending with the
   `Potential future improvements:` line.
5. Tick the plan boxes the work completed, and move anything you decided not to
   do into a later phase or the improvements list rather than dropping it.
6. Confirm both markdown files are tracked — no ignore rule covers them, but
   check, because a step documented only in an untracked file is a step
   documented nowhere.
7. Run `uv run --frozen prek -a`.

## 7. Checklist: changing an existing step

1. Make the script change.
2. Re-read the step's method file top to bottom, not just the bullet you think is
   affected. A changed threshold often contradicts a second bullet elsewhere.
3. Correct every bullet the change made untrue, and add a bullet for anything new.
4. Tick any plan box the change completed, and add a new plan entry if the change
   created work or a new known limitation.
5. Check the method file still ends with the `Potential future improvements:`
   line pointing at that step's plan file.
6. Keep the code and the two markdown edits in one commit.
7. Run `uv run --frozen prek -a`.

## 8. Verify before reporting done

- The step folder is numbered, holds an `__init__.py`, and both markdown files
  are prefixed with the folder name.
- No sentence in the method file describes something the code does not do, and no
  "will" or "should" appears in it.
- Every method bullet names the script, function, asset file or figure that holds
  the detail, rather than restating the detail.
- The method file's last line is the `Potential future improvements:` line naming
  that step's implementation plan.
- Everything aspirational is in the plan file and only there.
- Figures are written under `report/<module>/<topic>/fig/`, and no plotting logic
  moved into `src/landloss/`.
- `uv run --frozen prek -a` passes.
