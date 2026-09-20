# Agent Instructions

See the .agents/skills directory. You MUST use skills for all tasks.

You must start with `using-superpowers` for EVERY task, no matter how small. Keep `self-reflecting` active throughout — invoke it whenever you encounter failures, retries, or corrections. Next, you must apply `adapting-communication` to EVERY task. Before finishing you MUST use `verifying-claims` to verify your work, no matter what.

These are essential skills.

Use the `using-prek-pre-commit` skill when running pre-commit checks.

Extended thinking should only trigger for multi-step reasoning problems. When in doubt, respond directly without extended analysis.

## Script naming

A script is named for what it produces, so a directory listing says what each
file is for without opening it. Use these prefixes:

| Prefix | Produces |
| --- | --- |
| `fig_` | A figure, for the report or for a validation. |
| `table_` | A CSV table for the report. |
| `gen_` | A generated layer — data this project derives and writes out. |
| `get_` | A retrieved layer — data fetched from a source someone else maintains. |

Do not use `plot_`; a figure script is `fig_`. The `gen_` and `get_` distinction
is the one that carries weight: it separates code that creates new data, which
has to be re-run deliberately and its output tracked, from code that only fetches
what already exists. Reading a LINZ layer through Koordinates is a `get_`;
deriving the study area boundaries from that layer is a `gen_`.

`gen_` and `get_` apply to functions as well as to filenames, so a function that
retrieves a layer is `get_`, not `load_` or `fetch_`.

## Koordinates readers

Every reader of a Koordinates layer must record that layer's data licence in its
docstring, under a `Licence:` section, together with what the licence requires of
us in practice — not just its name. Most of these datasets are CC BY, which
obliges us to attribute the source in anything derived and published, so the
obligation has to be visible to whoever is writing the figure or table, not
buried on a portal page.

Take the licence from the layer's own metadata rather than assuming. The
Koordinates API answers anonymously for metadata, even where downloading needs a
key:

    curl -s "https://<domain>/services/api/v1.x/layers/<layer_id>/"

The response carries `license` (title, type, version, url), `publisher` and any
`doi`, which is everything the docstring needs.

Record the publisher and any DOI in a `Source:` section alongside it. Layer IDs
belong in `landloss.domain.constants` with the portal URL in a comment, never
inline in the reader.

## Project context

Background on what this project is for lives in `.agents/context`. Read these
before making decisions about methodology, outputs, or what belongs in the tool:

- `.agents/context/project-objectives.md` — what NHC has asked T+T to deliver and
  how the work is expected to be run.
- `.agents/context/project-scope.md` — the four project phases, their key tasks,
  the out-of-scope items, and the deliverables.
- `.agents/context/nhc-event-parameters-email.md` — NHC's brief on the event
  geography, exposure and insurance profile the study should be shaped around.
- `.agents/context/nhc-land-cover-and-settlement.md` — how NHC cover attaches to a
  property, how retaining walls and sub-caps are settled, and what is still unconfirmed.
- `.agents/context/land-damage-mechanisms.md` — the team's working picture of how land
  damage actually occurs in Wellington, and what that means for the model.
- `.agents/context/data-sources.md` — which dataset comes from where, and what is not
  obtainable.
- `.agents/context/nhc-natural-hazards-portal.md` — why the public Natural Hazards
  Portal must not be scraped, and what to ask NHC for instead.
- `.agents/context/code-structure.md` — the four analysis modules, the library and
  scripts split, and the causes of financial land loss the model represents.

The live register of tasks, limitations and future improvements is
`.agents/context/register.json`. It renders to a workbook in the OneDrive project
folder rather than the repo. Edit the JSON and
regenerate; see the `recording-project-context` skill.

## Module structure

`exposure`, `hazard` and `vul` are each split into submodules, in both
`src/landloss/` and `src/scripts/landloss/`: `exposure` by insured asset type
(`land`, `rw`, `culverts`), `hazard` by hazard (`liquefaction`, `landslide`,
`shaking`), and `vul` by hazard and then asset type (`vul/liquefaction/land`).
`loss` is flat.

`steps/`, `validations/`, `report/` and `research/` are submodules of whichever
level the work belongs to. Work specific to one asset or one hazard goes in that
submodule; work shared across all of them — the address spine, the valley
cross-sections, the NHC claims datasets — stays at the module level. None of them
is created until there is something to put in it, and no submodule is created
speculatively either.

Every submodule of `exposure`, `hazard` and `vul` carries a brief `status.md`
at its own level — `exposure/<asset>/`, `hazard/<hazard>/`,
`vul/<hazard>/<asset>/` — with the sections `## Approach`, `## Where it is now`,
`## Next`, then `## Validation` and `## Open decisions`. It is the submodule's
orientation page, distinct from the per-step plan and method files, and it points
at those for detail rather than restating them. Where nothing is implemented yet
it says so plainly and labels the approach as intended.
`hazard/shaking/status.md` is the example.

These files are updated as the work moves and the weekly progress update to NHC
is assembled from them, so a stale one puts a wrong statement in front of the
client. Any change to a submodule's scripts updates that submodule's `status.md`
in the same change. Use the `maintaining-status-files` skill whenever you write
or update one.

## Weekly updates

The weekly progress update to NHC is generated from those status files into
`release_updates/update_week_of_<monday>.typ`, from the Typst template beside it,
and the project lead edits and finalises it. It is never written from scratch and
never sent. Use the `writing-weekly-updates` skill whenever you are asked for the
weekly update, a weekly summary or a progress update.

Repo-relative paths come from `src/scripts/landloss/paths.py` (`REPO_ROOT`,
`REPORT_DIR`, `RESEARCH_DIR`, `TEMP_DIR`) and packaged data files from
`landloss.io.ASSETS_DIR`. Scripts sit at several depths, so never resolve either
with a `Path(__file__).resolve().parents[N]` count of your own.

See `.agents/context/code-structure.md` for the reasoning behind both axes.

## Step scripts

Every step lives in its own numbered folder under a `steps/` directory, carrying,
alongside its scripts, an implementation plan written in phases and a method file
describing the methodology as currently implemented. Any change to a step's
scripts must update that step's method file in the same change. Step numbers run
across the module, so a step keeps its number when it sits in a submodule's
`steps/`.

Use the `adding-steps-scripts` skill whenever you add a step, change one, or
wonder where a piece of methodology should be written down.

## Environment variables

`README.md`'s "Environment variables" section must document every variable in
`.env.example`. Any change that adds or changes a `.env` variable must update
that section in the same change — it is the one place a new developer can read
what every variable does without hunting through source.


## Script configuration

Scripts under `src/scripts/` must not use `argparse` (or any other CLI-argument
parser) to make paths or other settings configurable. Hardcode the paths
directly in the script instead, using `tdrive_sync`/`versioned_store` to
resolve anything that lives on T: or in the versioned data store. A script's
behaviour should be determined entirely by reading its source, not by
undocumented flags a caller might pass.

Do not guard against missing files or an unmapped T: drive with manual
`try`/`except`/`path.exists()` checks that print a friendly message and
`return 1`. Let the natural exception (`FileNotFoundError`, `ValueError`,
etc.) propagate — its traceback already says what went wrong.

`main()` should not return a status code, and the `if __name__ == "__main__":`
block should just be:

```python
if __name__ == "__main__":
    main()
```

Do not add a `status = main(); if status: raise SystemExit(status)` dance.