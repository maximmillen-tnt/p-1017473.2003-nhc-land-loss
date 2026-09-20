// Weekly progress update — Typst template.
//
// The handlebar placeholders are replaced with content lifted from the status.md
// files under src/scripts/landloss/. See the `writing-weekly-updates` skill for how
// one is generated and what goes in each section.
//
// Replacement text is Typst markup: a numbered list is one `+ item` per line,
// and an asset group inside a vul cell is `*Land*` on its own line followed by
// its list. Keep every item to one line.
//
// This file does not compile until the handlebars are substituted. Compile a
// filled copy with:
//
//     typst compile release_updates/update_week_of_<monday>.typ

#set page(paper: "a4", margin: (x: 1.3cm, y: 1.1cm))
#set text(font: "Arial", size: 9.5pt)
#set par(leading: 0.5em)
#set enum(indent: 0pt, body-indent: 4pt, spacing: 0.4em)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 10.5pt)
#show heading.where(level: 2): set block(above: 0.9em, below: 0.45em)

#let statusrow(n) = table.cell(colspan: n, fill: luma(96%))[_Current status_]
#let nextrow(n) = table.cell(colspan: n, fill: luma(96%))[_What's next_]

#let grid3 = (
  columns: (1fr, 1fr, 1fr),
  align: top + left,
  inset: 3.5pt,
  stroke: 0.5pt + luma(70%),
)

= NHC land loss — weekly update

*Week of {{date}}*

== 1. General updates

{{general_updates}}

== 2. Hazard

#table(
  ..grid3,
  table.header([*Liquefaction*], [*Landslide*], [*Shaking*]),
  statusrow(3),
  [
    {{hazard_liquefaction_status}}
  ],
  [
    {{hazard_landslide_status}}
  ],
  [
    {{hazard_shaking_status}}
  ],
  nextrow(3),
  [
    {{hazard_liquefaction_next}}
  ],
  [
    {{hazard_landslide_next}}
  ],
  [
    {{hazard_shaking_next}}
  ],
)

== 3. Exposure

#table(
  ..grid3,
  table.header([*Land*], [*Retaining walls*], [*Culverts*]),
  statusrow(3),
  [
    {{exposure_land_status}}
  ],
  [
    {{exposure_rw_status}}
  ],
  [
    {{exposure_culverts_status}}
  ],
  nextrow(3),
  [
    {{exposure_land_next}}
  ],
  [
    {{exposure_rw_next}}
  ],
  [
    {{exposure_culverts_next}}
  ],
)

== 4. Vulnerability

#table(
  ..grid3,
  table.header([*Liquefaction*], [*Landslide*], [*Shaking*]),
  statusrow(3),
  [
    {{vul_liquefaction_status}}
  ],
  [
    {{vul_landslide_status}}
  ],
  [
    {{vul_shaking_status}}
  ],
  nextrow(3),
  [
    {{vul_liquefaction_next}}
  ],
  [
    {{vul_landslide_next}}
  ],
  [
    {{vul_shaking_next}}
  ],
)

== 5. Loss

#table(
  columns: (1fr),
  align: top + left,
  inset: 3.5pt,
  stroke: 0.5pt + luma(70%),
  statusrow(1),
  [
    {{loss_status}}
  ],
  nextrow(1),
  [
    {{loss_next}}
  ],
)
