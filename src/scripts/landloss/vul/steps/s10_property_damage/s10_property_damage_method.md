# Step 10 — Property damage: method

- The step writes the **four tables vul hands to loss**, per realisation, as
  set out in section 1 of `.agents/plans/asset-pricing-approach.md`: land,
  retaining walls, culverts and bridges. It is run by `gen_property_damage.py`
  and adds no modelling of its own. Every number it writes was decided by the
  step it came from.
- The assembly is in `landloss.vul.loss_input`: `build_land_table()`,
  `build_rw_table()` and `build_crossing_tables()`. The contract column names
  come from `landloss.domain.loss_contract`, and each builder checks them with
  `check_contract_columns()` before returning.
- It reads seven files, each through its own step's path function:
  - the insured land (exposure step 5);
  - the liquefaction land damage (vul step 2) and the landslide land damage
    (vul step 3), both keyed on `land_id`;
  - the retaining wall damage states (`vul/shaking/rw` step 9) and the wall
    landslide flags (`vul/landslide/rw` step 11), keyed on `rw_id`;
  - the culvert and bridge damage states (`vul/shaking/culverts_bridges`
    step 9) and the crossing landslide flags (`vul/landslide/culverts_bridges`
    step 11), keyed on `crossing_id`.
- Every row carries its asset id and the `claim_id` of the LINZ property it
  belongs to, both minted in exposure and carried unchanged. Only insured
  assets reach this step: the exposure steps filter walls and crossings to the
  insured land.
- **Land**, one row per insured land polygon, spined on the insured land so a
  polygon no hazard reached still appears:
  - columns `land_id`, `claim_id`, `$/m2 market value` (the exposure land
    rate including GST, `land_rate_incl_gst_nzd_per_m2`; the exclusive rate
    stays in the exposure file), `Liq_LD_state`, `total_insured_land_area`,
    `land_slide_total_insured_land_area`, `inundated_insured_area`,
    `inundated_mean_depth` and `evacuated_area`;
  - `land_slide_total_insured_land_area` is the union of evacuated and
    inundated ground from vul step 3, not their sum;
  - landslide areas default to zero where no landslide reached the polygon,
    and `inundated_mean_depth` defaults to missing;
  - `Liq_LD_state` is 1, None, on land off the liquefaction grid, as written by
    vul step 2;
  - `dwelling_count` is carried as an extra column, pending Q-07.
- **Retaining walls**, one row per insured wall: `rw_id`, `claim_id`,
  `rw_size`, `rw_length`, `is_damaged_by_shaking` (the shaking damage state is
  replace), `is_evacuated` and `is_inundated`.
- **Culverts and bridges** are split from the crossings by structure kind, the
  `crossing_id` becoming `culvert_id` or `bridge_id`:
  - culverts: `culvert_id`, `claim_id`, `is_inundated`, `is_damaged` (the
    shaking damage state is replace), plus `is_evacuated` as an extra column
    pending Q-09;
  - bridges: `bridge_id`, `claim_id`, `is_damaged_by_shaking`, `is_evacuated`
    and `is_inundated`.
- An asset with no landslide flags row stops the run rather than defaulting to
  undamaged (`_merge_flags()` in `landloss.vul.loss_input`).
- The geometry comes from the exposure layers (the insured land polygon, the
  wall line and the crossing geometry) and supplies the coordinates. Each table
  is written in EPSG:2193, reprojected if needed, and refused if it has no CRS
  (`in_default_crs()`).
- Each table carries a `realisation_id` as its first column.
- The run prints, per realisation:
  - land polygons, claims and dwellings, and the liquefaction states present;
  - the landslide union total against the evacuated plus inundated sum, to show
    what the union avoids double counting;
  - walls, culverts and bridges, with the count carrying each flag;
  - the **T-27** overlap: claims carrying both a liquefaction land damage state
    and a wall damaged by shaking. If the Canterbury land damage rates already
    include retaining wall damage, each of those is charged for its wall twice.
- **Nothing is settled.** Caps, excesses, GST and pricing belong to the loss
  module, which this step does not touch.
- Output is `temp/vul/loss-input-<table>-r<nnn>[-pilot].geoparquet`, one file
  per table (`land`, `rw`, `culverts`, `bridges`), from `loss_input_path()`.
- The step has not yet been run on the pilot since the rework, so no counts are
  recorded here. It needs exposure steps 5, 6 and 7 and every vul step it reads
  rerun first.

Potential future improvements see `s10_property_damage_implementation_plan.md`.
