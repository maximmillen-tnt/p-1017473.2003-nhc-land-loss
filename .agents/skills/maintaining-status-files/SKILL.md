---
name: maintaining-status-files
description: How each submodule's status.md is written and kept current across exposure, hazard and vul — the Approach / Where it is now / Next sections, the brevity rule, editing in place so the git diff carries the week's progress, and how the files are read together to draft the weekly progress update. Use when creating or updating a status.md, after finishing a piece of work in any of those submodules, or when asked for a weekly or progress update.
---

# Maintaining status files

Every submodule of `exposure`, `hazard` and `vul` under
`src/scripts/landloss/` carries a `status.md` beside its scripts. It is the
one-page answer to "where has this piece of work got to, and what is next?", and
it has two audiences: whoever picks the work up, and whoever writes the weekly
progress update to the client.

The file sits at the level the submodule sits at, so there is one per row below
rather than one per module:

| Module | Where the file goes | Example |
| --- | --- | --- |
| `exposure` | `exposure/<asset>/status.md` | `exposure/land/status.md` |
| `hazard` | `hazard/<hazard>/status.md` | `hazard/shaking/status.md` |
| `vul` | `vul/<hazard>/<asset>/status.md` | `vul/landslide/land/status.md` |

`loss` is flat, so it takes a single `loss/status.md` if and when it needs one.

The second audience is what makes these files different from the rest of the
project's documentation. They are not written once and left. They are updated as
the work moves, and the weekly update is assembled from them, so a status file
that is a week stale does not just mislead a reader — it puts a wrong statement
in front of NHC.

`src/scripts/landloss/hazard/shaking/status.md` is the worked example. Copy its
shape.

## 1. The sections, in this order

```markdown
# <what this submodule covers>: status

**Status:** <one clause — Not started / Approach agreed, porting in progress / …>

**Updated:** <YYYY-MM-DD>

## Approach

Intended, not implemented.   ← drop this line once some of it is built

- <the decision, and at most one clause of why>

## Where it is now

<what exists in the repo today>

## Next

1. <the next concrete move>

## Validation

- <the check, and where it lives>

## Open decisions

- **T-nn** — <the register task this hazard is waiting on>

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
```

**`Approach` comes before `Where it is now`.** The current state means nothing
to a reader who does not yet know what is being attempted, so the method leads
and the progress follows it. This is the order the project lead asked for, after
a first draft led with the state.

`Status` and `Updated` sit at the top because they are what the weekly update
reads first. Keep the blank line between them: two adjacent bold lines render as
one run-on line.

## 2. Be brief

A bullet states a decision and, at most, the one clause that explains why. The
argument for a choice — the alternatives weighed, the references, the numbers —
belongs in the step's method or implementation plan file, not here.

If a bullet runs past about three lines, the surplus belongs in a step file and
the bullet should point at it. A status file that has grown into an essay stops
being scannable, which is the only property it has to have.

## 3. Keep it current, and edit in place

**Any change to a submodule's scripts updates that submodule's `status.md` in
the same change,** for the same reason a step's method file is updated with its
scripts: a description believed to be current is worse than no description.

A change can reach two files. Work in `hazard/landslide/` that alters what the
vulnerability model receives updates `vul/landslide/land/status.md` too, because
that file's `Approach` describes what it reads. Follow the dependency in one
direction only — hazard, then exposure, then vul — and point at the upstream
method rather than restating it downstream.

In practice, when work lands:

| What happened | What changes in `status.md` |
| --- | --- |
| A planned item was built | Its line moves out of `Next` and into `Where it is now`, stated as fact |
| The approach changed | The `Approach` bullet is rewritten; the old intent is not kept as history |
| A new piece of work appeared | A numbered item is added to `Next` |
| A register decision closed | The `Open decisions` entry goes, and the resolution appears in `Approach` |
| Nothing is left unbuilt in `Approach` | Drop the "Intended, not implemented" line |

Always bump `Updated`.

**Edit the file in place; do not regenerate it.** Leave sentences that are still
true exactly as they are, and change only what moved. The point is that
`git log -p -- <path>/status.md` is then a readable history of the hazard's
progress, one commit per piece of work, and the weekly update can be drafted
from the diffs rather than from memory. Rewriting the whole file every time
destroys that — every line shows as changed and the week's actual movement is
invisible.

## 4. Drafting the weekly progress update

The weekly update is assembled from the status files, not written from scratch.

1. Find every file with
   `git ls-files "src/scripts/landloss/**/status.md"` and read each one's
   `Updated`, so a file nobody has touched is visible as exactly that rather
   than silently reported as "no change".
2. Diff them over the period with
   `git log -p --since="<date>" -- "src/scripts/landloss/**/status.md"`, and
   take the movement from `Next` into `Where it is now` as the period's
   progress. That transition is the unit of progress; a rewritten `Approach`
   bullet is a change of plan and is worth reporting as one.
3. Write one short paragraph per submodule that moved, grouped by module so the
   update reads in pipeline order — hazard, exposure, vul, loss. Say what moved,
   what is next, and anything blocked, naming the blocker by its register ID
   where there is one.
4. Carry the `Open decisions` entries up into the update. A decision the team is
   waiting on is the most useful thing in a progress report, because it is the
   only part the client can act on.

Report what the files say. If a submodule did not move, the update says it did
not move — do not reach into the repo to find something that sounds like
progress, and do not describe an `Approach` bullet as though it were built.

## 5. Honesty about what does not exist

A status file carries intent alongside state, which the step-level method files
deliberately do not. That makes one rule non-negotiable: **anything not yet
built is labelled as intent.**

- `Approach` opens with "Intended, not implemented." while none of it exists.
- Once part of it is built, that line goes and `Where it is now` states what
  actually runs; `Approach` continues to describe the method as a whole.
- `Where it is now` never describes planned work. "Nothing is implemented. This
  file is the only thing in the folder." is a complete and correct answer.

No "will" in `Where it is now`; no past tense in `Next`.

## 6. Creating one for a submodule that has none

`git ls-files "src/scripts/landloss/**/status.md"`, checked against the
submodule list in section 1, shows which are missing.

1. Copy the section skeleton above.
2. Fill `Where it is now` from what is actually in the folder — for
   `hazard/liquefaction` that is `report/fig_waterway_map.py` and
   `report/table_waterways.py`; for `exposure/land`, the `s2_land_value` step
   and the land value validation; for `vul/liquefaction/land`, the
   `s1_ces_observed_damage` step and the land damage figures. Where a step
   already has a method file, summarise from it and point at it rather than
   re-deriving from the scripts.
3. **Do not invent `Approach` or `Next`.** Those are the project lead's to set.
   Draft what is supportable from `.agents/context/`, the plans under
   `.agents/plans/` and any existing step method files, and ask about anything
   you would otherwise be guessing at. A plausible-looking next step that nobody
   agreed to is the one failure mode these files cannot tolerate, because it
   ends up in a client update.

## 7. Verify before reporting done

- Sections are in the order `Approach`, `Where it is now`, `Next`,
  `Validation`, `Open decisions`, with the short headings — not "The approach"
  or "What happens next".
- `Updated` carries today's date.
- No bullet in `Where it is now` describes something that is not in the repo.
- The diff shows only what actually changed, not a whole-file rewrite.
- The file still ends with the line pointing at the step files for detail.
- `uv run --frozen prek -a` passes.
