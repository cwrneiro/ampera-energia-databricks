---
version: 1
slug: "app-frontend"
primary_target: "app/frontend"
related_targets: []
---

# Surface: Ampera app (app/frontend)

Mode: Operate. Audience: Ampera data team + decision-makers; presented live on a projector,
then explored by the team. Task: read generation by CEG/conjunto, trust the reconciliation,
find a plant on the map, inspect price and weather for it. Pages: Visão geral, Reconciliação, Mapa,
Usina. Constraints: PT-BR UI, brand tokens in specs/08-branding.md (light, Nunito), Ampera-only
branding, the text wordmark, estimado/measured-vs-modeled labels (spec 06).

## Direction contract

THESIS: Every page is a surveyed sheet (carta topográfica): one plot owns a neat-line frame and the
margin carries legend, notes and sources. Refuses the KPI-card-grid + left-sidebar BI dashboard.
Amended 2026-10-05 (user): the Mapa sheet has no margin; the map fills the sheet and its title, legend,
filter menu and notes float over it as readouts. Its camera glides to a filter (900 ms).

OWN-WORLD: White sheet on #f8f8f8 table with a soft shadow; purple #541790 neat line and title
block; real coordinates only: 5° graticule on the map with degree ticks/labels at the neat line,
period/lat-long corners elsewhere (no decorative fixed-pitch ticks). Fonte hues (HID #0089f7,
EOL #8047c6, SOL #f26200, THERM #b0175a, NUC #00a39b, OTHER #8f8a2a) live only in plots and legends.
Amended 2026-10-02: THERM grey / muted NUC-OTHER failed the dataviz validator (normal-vision ΔE < 15,
chroma floor), so the validated set ships. Method hues are a separate ramp, never a fonte hue: resolved =
purples, unresolved/aggregate = greys, "não reconciliado" = ink #0a0a0a. Nunito, tabular numerals.
Raises: split-flap (fixed-column boards, values update in place), lexicon (colour quarantined to
plots/legend), catalog sleeve (one plot per sheet), j-card (breakdowns visibly fill 100%),
title-card wall (selection lifts, rest dims).

STORY: The visitor sees how much Brazil generated, where, how ONS links to SIGA (and how little is
unmatched), then drills into one plant's price and weather — trusting every total.

FIRST VIEWPORT: Visão geral sheet: title block "Geração reconciliada · Brasil" with period; the
dominant stacked series by fonte inside the frame (~70% width); margin column: total TWh large,
legend with each fonte's share bar summing to 100%, notes (estimado share), sources. Sheet index
(nav to the 4 sheets) and filters in the header strip above the sheet.

LAYOUT: one plot per neat-line frame; boards and tables sit on the sheet below it.

FORM: Carta topográfica (IBGE/DSG 1:250.000 sheet), position 5 of 7 on the ordered list, seed key
8ae1610b. Signature interaction: selecting a plant/fonte lifts it and dims the rest across plot,
legend and board; motion grammar = short ink-draw of plots on sheet change, nothing else.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
