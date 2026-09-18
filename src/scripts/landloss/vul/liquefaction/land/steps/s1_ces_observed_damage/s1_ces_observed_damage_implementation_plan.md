# Step 1 — Canterbury observed land damage: implementation plan

**Status:** Phase 4 not started — neither script has been run against the real
data yet.

## Why this step exists

The vulnerability module needs evidence for how much land damage costs at a
given level of liquefaction demand. The Canterbury earthquake sequence is the
only New Zealand dataset with both settled land claims and mapped land damage
observations, so it is what the Wellington land damage relationships are
calibrated against.

A version of this figure already exists in the National Liquefaction Model loss
repository (`p-1017473-nlm-loss-modelling`), as
`src/scripts/figs/fig_bdr_v_lsn.py`. The figure is worth having here; the way its
database is built is not. There the underlying `bdr_observed_damage_db.parquet`
is the tail of a four script chain that pulls in the NHC building portfolios
through pins, the per-event simulated loss parquets, a QPID-keyed merge with a
100 m spatial fallback, and a KNN imputation of missing building losses. None of
that is needed for a land damage figure, and the last step flattens its spatial
join to a Python dictionary, which silently keeps an arbitrary match where a
property falls inside more than one observation polygon. This step replaces the
chain with a single join from the loss points straight to the observations and
the LSN grid.

## Phase 1 — Pin the National Liquefaction Model release (complete)

- [x] `NLM_VERSION` and `NLM_OBS_VERSION` added to
      `src/landloss/domain/constants.py`, so the release is named once rather
      than spelled out in every path reaching into its tree.
- [x] Comment recording why the observation release is deliberately older than
      the model release.

## Phase 2 — Join the losses to the observations and the LSN grid (complete)

- [x] Read the geocoded loss GeoPackage, clean the dollar columns and drop
      unusable QPIDs and geometry (`get_losses` in `gen_observed_damage_db.py`).
- [x] Aggregate to one row per property per event before joining, so a property
      with many claims is joined once.
- [x] Fold each event's observation vocabulary onto the five standard categories
      (`OBS_HAZ_MAP`, `get_observed_damage`).
- [x] Join the observations with a worst-category-wins reduction where a
      property falls inside several polygons (`assign_observed_damage`).
- [x] Join the LSN grid through a 50 m square buffer (`assign_lsn`).
- [x] Write `observed_damage_db.parquet`, keeping the geometry.

## Phase 3 — Draw the figure (complete)

- [x] Six panel figure, per event and for all events together
      (`src/scripts/landloss/vul/liquefaction/land/report/`
      `fig_land_damage_v_lsn.py`).
- [x] Diagnostics printed before plotting, so a bad join is caught before a
      figure is believed.

## Phase 4 — First run against the real data

- [ ] Run both scripts and check the counts against what the National
      Liquefaction Model repository asserts about the same source: 327,247 loss
      records, 1,970 with a null QPID, 16,230 with a QPID at or below zero.
- [ ] Confirm the observation and LSN match rates are plausible. A near-zero
      rate means a CRS or column name assumption is wrong rather than that the
      data is sparse.
- [x] Confirm the output location. The database now writes through
      `landloss.io.versioned_store.save_vul` (`OUT_SUB_DIRS`/`OUT_NAME` in
      `gen_observed_damage_db.py`), so it follows the project's versioned data
      store layout rather than a guessed `T:` path.
- [ ] Compare a panel against the National Liquefaction Model's equivalent
      figure. The point clouds should be recognisably the same shape; they will
      not be identical, because this database is not restricted to properties
      present in the NHC building portfolio.

## Potential future improvements

- Normalise the damage. The figure plots land damage in dollars, capped at
  $20,000. A damage ratio against the property's land value is the more
  transferable quantity and what the Wellington model ultimately needs, but the
  NHC extract carries no land value; it would have to come from the rating
  values being sought from the councils, joined on QPID.
- Compare assessment against payment. `land_assessment` is what was assessed and
  `land_paid` what was settled, and the two differ where the cap bites. Both are
  carried in the database and only the assessment is plotted; comparing them
  would show how much of the Canterbury land loss the cap absorbed, which bears
  directly on the policy settings this study tests.
- Bin the scatter. At this many properties the cloud is heavily overplotted. The
  National Liquefaction Model's sibling figure adds a rolling mean in LSN bins of
  two up to LSN 40, which reads better than the straight line fit and would make
  the relationship at low LSN legible.
- Map the observation coverage. The proportion of properties matching an
  observation polygon is printed but not mapped, so it is not known whether the
  unmatched properties are a random scatter or a systematic hole — which changes
  how much weight the categories can carry.
- Separate flat from sloping land. The Canterbury sequence is dominated by flat
  land liquefaction, recorded as limitation L-09 in the project register.
  Splitting the properties by the National Liquefaction Model flatland layer
  would at least show how few sloping land observations there are, rather than
  leaving the limitation as an assertion.
- Settle the `Minor` mapping with the National Liquefaction Model team. This step
  deliberately departs from their category map, which sends a raw `Minor` to
  `None Observed` while sending the numeric code `2` to `Minor`. That looks like
  a defect rather than a judgement, but it has not been confirmed with whoever
  wrote it, and until it is the two studies' figures differ for a reason that is
  in neither method.
- Move the figure script into this folder. It sits in
  `src/scripts/landloss/vul/liquefaction/land/report/` because that is where the
  project lead asked for it, which predates the step folder convention in the
  `adding-steps-scripts` skill; the skill would put it here beside the step it
  belongs to.
