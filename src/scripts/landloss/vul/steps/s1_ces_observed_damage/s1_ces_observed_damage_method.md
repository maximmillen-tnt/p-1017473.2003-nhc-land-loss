# Step 1 — Canterbury observed land damage: method

- The step joins NHC's settled Canterbury earthquake sequence losses to the
  National Liquefaction Model's mapped land damage observations and its per-event
  LSN grid, producing one row per insured property per event. It is the only New
  Zealand dataset holding all three, and it is the evidence the Wellington land
  damage relationships are calibrated against.
- The three events covered, the raw event string each carries in the NHC extract,
  the observation file that belongs to it and its LSN grid are all listed in
  `EVENTS` in `gen_observed_damage_db.py`. The observation filenames do not
  announce which event they hold — `CESSept` is Darfield, `CESFeb` is February
  2011, `CHCH16` is February 2016 — so `EVENTS` is the record of that mapping.
- The two National Liquefaction Model releases read are pinned as `NLM_VERSION`
  and `NLM_OBS_VERSION` in `src/landloss/domain/constants.py`. The observations
  come from the older release; they are survey data and do not change when the
  model is re-run.
- The loss records are read from the GeoPackage written by
  `../../static_data_gen/gen_ces_loss_data.py`, not from NHC's source CSV, so
  that script runs first.
- Column names are stripped of the stray whitespace the source carries and
  renamed to snake_case through `COLUMN_MAPPINGS` in
  `gen_observed_damage_db.py`, which is taken from the National Liquefaction
  Model loss repository so the two studies name the same field the same way.
- The dollar columns arrive as text carrying a currency symbol, thousands
  separators and a bare `-` for nil. `to_money` converts them, treating a lone
  dash as nil and leaving a genuine negative — a credit — intact.
- Records outside the three modelled events, records with a null or non-positive
  QPID, and records with missing or empty geometry are dropped by `get_losses`,
  which prints the count dropped at each of those three steps. Empty geometry is
  tested at the shapely level rather than through `GeoSeries.notna`, which warns
  on exactly the case being looked for.
- Records are aggregated to one row per property and event by `get_losses`,
  summing the dollar columns and counting the claims into `n_claims`. Aggregating
  before the joins means a property with many claims is joined once.
- Each event's observation layer uses its own vocabulary — numeric severity codes
  for one, damage descriptions for another, liquefaction presence for the third.
  `OBS_HAZ_MAP` in `gen_observed_damage_db.py` folds all of them onto five
  categories, and `get_observed_damage` prints by name any class the map does not
  cover and leaves those polygons out.
- The February 2016 layer also carries classes describing something other than
  land damage. Only the liquefaction presence classes in `CHCH16_LIQ_CLASSES` are
  kept, matching the National Liquefaction Model's treatment.
- Properties are joined to the observation polygons by `assign_observed_damage`
  with an intersects spatial join. Where a property falls inside more than one
  polygon the worst category wins, ranked by `DAMAGE_RANKS`, with `Unknown`
  ranking below every known category so it never displaces one. The National
  Liquefaction Model's build instead flattens the same join to a dictionary,
  which keeps an arbitrary match.
- `OBS_HAZ_MAP` departs from the National Liquefaction Model's map in one place:
  a raw `Minor` stays `Minor` here, where theirs sends it to `None Observed`
  while sending the numeric code `2` to `Minor`. Figures from the two studies
  therefore differ.
- A property covered by no observation polygon keeps a null category. It appears
  in the figure's combined panel and in none of the five category panels.
- LSN is attached by `assign_lsn`, which buffers each grid node to a 50 m square
  to recover the raster cell it stands for and joins the properties to those
  cells. A property on a cell boundary intersects two, and the higher LSN is
  taken so the row is not duplicated. A property outside the grid keeps a null
  LSN, which the run reports as a match rate per event.
- The database is written as `observed_damage_db.parquet` under the vul module's
  `ces_observed_damage` area of the project's versioned data store, through
  `landloss.io.versioned_store.save_vul` (see `OUT_NAME`/`OUT_SUB_DIRS` in
  `gen_observed_damage_db.py`). It is derived and large, so it is regenerated
  rather than committed, and it respects `DATA_VERSION` and local-only working
  mode rather than a fixed `T:` path. `fig_land_damage_v_lsn.py` reads it back
  the same way, through `versioned_store.read_vul`. Its columns are listed in
  `OUTPUT_COLUMNS`, and the geometry is kept so the database can be joined to
  further layers.
- Settled land damage against LSN is plotted by
  `src/scripts/landloss/vul/report/fig_land_damage_v_lsn.py` as a six panel
  figure — one panel holding every property and five splitting them by observed
  damage category — written to `report/vul/liq/fig/`. Damage is clipped to
  `DAMAGE_CAP` rather than filtered, so the pile-up at the top of the axis shows
  how much sits beyond the scale. The layout follows `fig_bdr_v_lsn.py` in the
  National Liquefaction Model loss repository so a panel from this study can be
  read against one from that one.
- The Canterbury sequence is dominated by flat land liquefaction damage, so this
  evidence constrains the liquefaction land damage relationship and not the
  landslide relationships. That is limitation L-09 in the project register.

Potential future improvements: see `s1_ces_observed_damage_implementation_plan.md`.
