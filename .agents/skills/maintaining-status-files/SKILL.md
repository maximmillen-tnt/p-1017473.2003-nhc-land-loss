---
name: maintaining-status-files
description: How each hazard module's status.md is written and kept current — the Approach / Where it is now / Next sections, the brevity rule, editing in place so the git diff carries the week's progress, and how the files are read together to draft the weekly progress update. Use when creating or updating a status.md, after finishing a piece of work in a hazard module, or when asked for a weekly or progress update.
---

# Maintaining status files

Every hazard submodule under `src/scripts/landloss/hazard/` carries a
`status.md` beside its scripts. It is the one-page answer to "where has this
hazard got to, and what is next?", and it has two audiences: whoever picks the
work up, and whoever writes the weekly progress update to the client.

The second audience is what makes these files different from the rest of the
project's documentation. They are not written once and left. They are updated as
the work moves, and the weekly update is assembled from them, so a status file
that is a week stale does not just mislead a reader — it puts a wrong statement
in front of NHC.

`src/scripts/landloss/hazard/shaking/status.md` is the worked example. Copy its
shape.

## 1. The sections, in this order

```markdown
# <Hazard> hazard: status

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

**Any change to a hazard module's scripts updates that hazard's `status.md` in
the same change,** for the same reason a step's method file is updated with its
scripts: a description believed to be current is worse than no description.

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

1. Read the `status.md` of each hazard module, plus `Updated` on each, so a file
   nobody has touched is visible as exactly that rather than silently reported
   as "no change".
2. For each hazard, diff the file over the period —
   `git log -p --since="<date>" -- src/scripts/landloss/hazard/*/status.md` —
   and take the movement from `Next` into `Where it is now` as the week's
   progress. That transition is the unit of progress; a rewritten `Approach`
   bullet is a change of plan and is worth reporting as one.
3. Write one short paragraph per hazard: what moved, what is next, and anything
   blocked. Name the blocker by its register ID where there is one.
4. Carry the `Open decisions` entries up into the update. A decision the team is
   waiting on is the most useful thing in a progress report, because it is the
   only part the client can act on.

Report what the files say. If a hazard did not move, the update says it did not
move — do not reach into the repo to find something that sounds like progress,
and do not describe an `Approach` bullet as though it were built.

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

## 6. Creating one for a hazard that has none

At the time of writing only `hazard/shaking/status.md` exists.
`hazard/liquefaction/` and `hazard/landslide/` still need theirs.

1. Copy the section skeleton above.
2. Fill `Where it is now` from what is actually in the folder — for
   `liquefaction` that is `report/fig_waterway_map.py` and
   `report/table_waterways.py`; for `landslide`,
   `validations/fig_landslide_vulnerability_model_gwrc.py`.
3. **Do not invent `Approach` or `Next`.** Those are the project lead's to set.
   Draft what is supportable from `.agents/context/` and the plans under
   `.agents/plans/`, and ask about anything you would otherwise be guessing at.
   A plausible-looking next step that nobody agreed to is the one failure mode
   these files cannot tolerate, because it ends up in a client update.

## 7. Verify before reporting done

- Sections are in the order `Approach`, `Where it is now`, `Next`,
  `Validation`, `Open decisions`, with the short headings — not "The approach"
  or "What happens next".
- `Updated` carries today's date.
- No bullet in `Where it is now` describes something that is not in the repo.
- The diff shows only what actually changed, not a whole-file rewrite.
- The file still ends with the line pointing at the step files for detail.
- `uv run --frozen prek -a` passes.
