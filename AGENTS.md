# Agent Instructions

See the .agents/skills directory. You MUST use skills for all tasks.

You must start with `using-superpowers` for EVERY task, no matter how small. Keep `self-reflecting` active throughout — invoke it whenever you encounter failures, retries, or corrections. Next, you must apply `adapting-communication` to EVERY task. Before finishing you MUST use `verifying-claims` to verify your work, no matter what.

These are essential skills.

Use the `using-prek-pre-commit` skill when running pre-commit checks.

Extended thinking should only trigger for multi-step reasoning problems. When in doubt, respond directly without extended analysis.

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

The live register of tasks, limitations and future improvements is
`.agents/context/register.json`. It renders to a workbook in the OneDrive project
folder rather than the repo. Edit the JSON and
regenerate; see the `recording-project-context` skill.
