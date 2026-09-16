# Welcome to NHC Land Loss

## How We Use Claude

Based on Maxim Millen's usage over the last 30 days (6 sessions, 5 with
descriptors):

Work Type Breakdown:
  Write Docs       ████░░░░░░░░░░░░░░░░  20%
  Build Feature    ████░░░░░░░░░░░░░░░░  20%
  Analyze Data     ████░░░░░░░░░░░░░░░░  20%
  Debug Fix        ████░░░░░░░░░░░░░░░░  20%
  Plan Design      ████░░░░░░░░░░░░░░░░  20%

An even spread — no single mode dominates. Sessions ranged from capturing the
project brief as context files, to wiring up the pre-commit hooks, to asking
whether data could be pulled out of the Natural Hazards Portal, to decoding a
git error.

Top Skills & Commands:
  /clear           ████░░░░░░░░░░░░░░░░  1x/month

Top MCP Servers:
  None recorded    ░░░░░░░░░░░░░░░░░░░░  0 calls

Light on slash commands and MCP so far — most of the work has been plain
conversation plus the repo's own skills.

## Your Setup Checklist

### Codebases
- [ ] p-1017473.2003-nhc-land-loss — git@github.com:maximmillen-tnt/p-1017473.2003-nhc-land-loss.git (this project)
- [ ] p-1017473-national-liquefaction-model — git@github.com:tonkintaylor/p-1017473-national-liquefaction-model.git (geology, liquefaction and slope inputs this project builds on)
- [ ] p-1017473-nlm-loss-modelling — git@github.com:tonkintaylor/p-1017473-nlm-loss-modelling.git (loss modelling approach)
- [ ] p-1017473.2002-nhc-risk-model-understanding — git@github.com:tonkintaylor/p-1017473.2002-nhc-risk-model-understanding.git (earlier NHC work)
- [ ] p-1099456-hurunui-high-level-geotech — git@bitbucket.org:tonkintaylor/p-1099456-hurunui-high-level-geotech.git (reference for the Koordinates readers pattern)

### Environment
- [ ] Run `./tasks/dev_sync.ps1` to set up the Python environment (uv, Python 3.13)
- [ ] Copy `.env.example` to `.env` and fill in `TNT_KOORDINATES_API_KEY` and `LINZ_API_KEY` — ask Maxim for keys. `.env` is gitignored; never commit it
- [ ] Check `uv run --frozen pytest` and `uv run --frozen prek -a` both pass before you change anything

### MCP Servers to Activate
- [ ] None in use yet — no MCP calls recorded in the last 30 days. Several are configured in this workspace (Atlassian, Deltek VantagePoint, T+T Intranet, Koordinates, Microsoft 365) and authenticate on first use if you need them

### Skills to Know About
- [ ] `recording-project-context` — turns a meeting transcript, email or note into durable project context: tasks, limitations and improvements in the register workbook, refinements to the objectives and scope, and standalone notes on recurring topics. Use it whenever you hand Claude a transcript
- [ ] `seismic-landslide-hazard-wellington` — the method reference for earthquake-induced landslide work in the Wellington region: Newmark analysis, displacement methods by source mechanism, topographic amplification, and which GWRC datasets to pull rather than rebuild
- [ ] `/clear` — start a fresh context when you switch tasks. The only built-in command showing up in the stats

## Team Tips

**Read the context files before you ask Claude for anything.** This is the most
important habit on this project. `.agents/context/` holds what the project is
for, what was agreed, and what we already know — and `AGENTS.md` points Claude at
them. Today that is:

- `project-objectives.md` and `project-scope.md` — the brief, the four phases,
  and what is explicitly out of scope. Both carry a **Refinements** section
  recording where later discussion clarified or narrowed the original scope
- `nhc-land-cover-and-settlement.md` — how NHC cover attaches to a property, the
  $25k retaining wall cap, insured land, sub-caps
- `land-damage-mechanisms.md` — how land damage actually happens in Wellington
- `data-sources.md` — which dataset comes from where, and what is not obtainable
- `code-structure.md` — the four modules (hazard, exposure, vul, loss), the
  library/scripts split, and the causes of financial land loss
- plus notes on the Natural Hazards Portal, event parameters and retaining wall
  fragility

Claude will not infer this from the code. A question asked without it gets an
answer that ignores decisions the team has already made.

**Everything new goes back into context.** If a meeting, email or call produces
something durable, use the `recording-project-context` skill so it lands in
`.agents/context/` rather than staying in a transcript. Add new files to the list
in `AGENTS.md` or nobody — including Claude — will read them.

**The register is append-only.** Tasks, limitations and improvements live in
`.agents/context/register.json` and render to a workbook in the OneDrive project
folder. Add entries; never renumber or rewrite existing ones, because other
documents cite the IDs. The workbook owns the Status column, so anything you tick
off in Excel survives the next append.

**Never hardcode your username in a path.** The project outputs live in a shared
OneDrive folder, so write `$env:USERPROFILE` (or `Path.home()` in Python). A path
with one person's username in it is wrong for everyone else.

**Plans go in `.agents/plans/`** so the reasoning behind an approach is reviewable
alongside the code.

## Get Started

No starter ticket — pick up whatever is current.

1. Read `AGENTS.md`, then `project-objectives.md` and `project-scope.md` in
   `.agents/context/`. Twenty minutes, and it will save you a lot more
2. Run the example to check your keys and see how data loading works:
   `uv run --frozen python src/scripts/landloss/example_download_linz_data.py`
3. Open the register workbook to see what is open and who owns it
4. Ask Maxim what is live right now — this project moves faster than the docs

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->