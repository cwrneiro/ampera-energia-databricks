---
name: Ampera · Geração reconciliada
description: Reconciled Brazilian generation (ONS × ANEEL SIGA) drawn as surveyed topographic sheets.
colors:
  survey-purple: "#541790"
  survey-purple-lift: "#6a24b0"
  signal-blue: "#0089f7"
  ink: "#0a0a0a"
  ink-secondary: "#626262"
  ink-tertiary: "#8a8794"
  sheet-white: "#ffffff"
  table-grey: "#f8f8f8"
  lavender-tint: "#eae9f6"
  hover-wash: "#f7f6fb"
  rule: "#e4e2ec"
  rule-faint: "#f0eff5"
  plot-grid: "#ecebf2"
  axis-line: "#d9d7e3"
  control-stroke: "#d6d3e1"
  ghost-stroke: "#cfc6e3"
  fonte-hid: "#0089f7"
  fonte-eol: "#8047c6"
  fonte-sol: "#f26200"
  fonte-therm: "#b0175a"
  fonte-nuc: "#00a39b"
  fonte-other: "#8f8a2a"
  method-ceg: "#541790"
  method-member: "#b08ae8"
  method-fuzzy: "#e3d8f6"
  method-conjunto: "#6e6478"
  method-aggregate: "#b5b5b5"
  method-unmatched: "#0a0a0a"
typography:
  display:
    fontFamily: "Nunito, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "3rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Nunito, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Nunito, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 800
    lineHeight: 1.5
  body:
    fontFamily: "Nunito, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  ui:
    fontFamily: "Nunito, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.5
  label:
    fontFamily: "Nunito, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.45
  corner:
    fontFamily: "Nunito, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: "18px"
    fontFeature: "tnum"
rounded:
  swatch: "2px"
  tag: "3px"
  control: "4px"
  sheet: "5px"
  dot: "50%"
spacing:
  cell: "8px"
  control-x: "12px"
  margin-gap: "28px"
  gutter: "32px"
  board-gap: "36px"
components:
  button-primary:
    backgroundColor: "{colors.survey-purple}"
    textColor: "{colors.sheet-white}"
    typography: "{typography.ui}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.survey-purple-lift}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.survey-purple}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
  button-ghost-hover:
    backgroundColor: "{colors.lavender-tint}"
  input:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "40px"
    padding: "0 12px"
  sheet-index-cell:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    padding: "8px 14px"
    width: "11.5rem"
  sheet-index-cell-current:
    backgroundColor: "{colors.lavender-tint}"
    textColor: "{colors.survey-purple}"
  segmented-on:
    backgroundColor: "{colors.survey-purple}"
    textColor: "{colors.sheet-white}"
    padding: "9px 16px"
  sheet:
    backgroundColor: "{colors.sheet-white}"
    rounded: "{rounded.sheet}"
    padding: "28px 32px 32px"
  corner-label:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.survey-purple}"
    typography: "{typography.corner}"
    padding: "0 8px"
---

# Design System: Ampera · Geração reconciliada

## Overview

**Creative North Star: "The Surveyed Sheet"**

Every page is a carta topográfica: a white sheet laid on a pale grey table, a title block at the head, one plot enclosed by a purple neat line, and a margin column carrying the legend, totals, notes and sources the way a printed survey sheet carries its key. Boards and tables sit on the sheet below the frame. The page reads like a document that was measured, not a dashboard that was assembled.

Density is moderate and projector-legible: 16px Nunito body, an 800-weight title block, tabular numerals everywhere a number appears. Chrome is quiet and purple; colour of meaning (fonte, match method) lives only in marks. The neat line's corners carry real coordinates or the real period of the plot, never decoration. The one motion is an ink-draw: the neat line strokes itself in and the plot animates in on sheet change. The map camera's glide to a filter is the only other motion.

The world refuses the KPI-card grid with a left sidebar. Navigation is a sheet index (four cells across the top strip), not a sidebar; the total sits in the margin, not in a stat card.

**Key Characteristics:**
- One plot per neat-line frame; the margin column is the key.
- Purple survey chrome, colour quarantined to plot marks and swatches.
- Corner labels and graticule ticks carry real dates and degrees.
- Breakdowns visibly fill 100% (whole bars, shares summing to 100%).
- Selection lifts one series and dims the rest across plot, legend and board.
- Fixed-column boards whose values update in place.

## Colors

A white-and-lavender survey sheet in brand purple, with two validated categorical ramps that appear only inside plots and legends.

### Primary
- **Survey Purple** (survey-purple): the neat line, corner labels, graticule labels and ticks, map scale bar, total figure, links, primary buttons, current sheet-index cell. Also the strongest match method (CEG exato).
- **Lifted Purple** (survey-purple-lift): hover state of primary buttons only.

### Secondary
- **Signal Blue** (signal-blue): the focus ring (2px outline, 2px offset) and the hatched "estimado" tag. It doubles as the Hidráulica fonte hue in plots.

### Neutral
- **Sheet White** (sheet-white): the sheet, controls, sticky board headers, corner-label knockouts.
- **Table Grey** (table-grey): the page behind the sheet.
- **Lavender Tint** (lavender-tint): selected and pressed states (current index cell, pressed legend row, ghost-button hover), text selection.
- **Hover Wash** (hover-wash): row and cell hover before selection.
- **Ink / Ink Secondary / Ink Tertiary**: headings and values; labels, scope lines, notes, axis ticks; disabled index cells, size-key rings, the modeled/average line in plots.
- **Rule / Rule Faint**: board header rule, margin divider, tooltip border; row dividers.
- **Plot Grid / Axis Line**: horizontal-only chart grid; axis strokes.
- **Control Stroke / Ghost Stroke**: input and select borders; ghost button and segmented-control borders.

### Data ramps
- **Fonte** (fonte-hid, -eol, -sol, -therm, -nuc, -other): fixed order Hidráulica, Eólica, Solar, Térmica, Nuclear, Outras, validated against white. Never cycled, never reassigned.
- **Match method** (method-*): resolved methods are purples (estimated member = the measured member hue plus a 45° hatch), unresolved and aggregate are greys, "não reconciliado" is ink.

### Named Rules
**The Quarantine Rule.** Fonte and method hues appear only as marks: bars, areas, lines, map circles, swatches and dots. Text beside a swatch stays in ink; chrome stays purple and grey.

**The Separate Ramps Rule.** A method colour is never a fonte hue. Any new categorical ramp must clear the existing ones, not borrow from them.

**The Hatch Means Estimated Rule.** A 45° hatch of a hue (2px colour, 3px at 28% tint) marks an estimated quantity, in plots, whole bars and the "estimado" tag alike. It means nothing else.

## Typography

**Display Font:** Nunito (variable 400–800, self-hosted woff2) with -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
**Body Font:** Nunito, same stack

**Character:** One rounded humanist family carrying everything by weight: 800 for the title block and figures, 700 for labels and names, 600 for controls, 400 for prose. Numbers are always tabular.

### Hierarchy
- **Display** (800, 3rem, 1.1, -0.02em, tabular): the period total in the margin, in Survey Purple, with its unit at 1.5rem/700 in ink. 2.5rem under 520px.
- **Headline** (800, 2.25rem, 1.1, -0.015em): the sheet title, one per page. 1.75rem under 900px.
- **Title** (800, 1.0625rem): board and panel headings below the frame. Margin block headings use 1rem/800; the selected plant's name on the map uses 1.25rem/800.
- **Body** (400, 1rem, 1.5): scope line and prose; ledes cap at 70ch, status messages at 46ch.
- **UI** (600, 0.9375rem): buttons, segmented control, legend rows, sheet-index names (700).
- **Label** (700, 0.8125rem): filter labels, notes and sources (400 in ink secondary), tooltip body. Board column heads use 0.78125rem/700 in ink secondary.
- **Corner** (700, 0.75rem, tabular, Survey Purple): neat-line corner labels; graticule degree labels at 0.6875rem.

### Named Rules
**The Tabular Rule.** Every numeric cell, axis tick, corner and total uses tabular numerals and right alignment in columns. Numbers format pt-BR (comma decimal, dot thousands), with the unit chosen to stay readable (MWh, GWh, TWh; R$ mi, R$ bi) and an em dash for missing values.

**The Weight Not Size Rule.** Hierarchy inside the margin and boards comes from weight (700/800 over 400), not from new sizes. Do not add sizes between the steps above.

## Layout

The page is a stack: a white top strip (wordmark left, sheet index right, 14px 32px padding, bottom rule), a filter row on the table, then one sheet, max-width 1600px, centred, 32px side padding.

Inside the sheet: the title block (title and scope left, actions right), then a two-column body: the main column (the neat-line frame, then the boards below it) and a 19rem margin column divided by a 1px left rule with 28px padding. Column gap is 32px; margin blocks are 28px apart; boards sit two-up with a 36px gap, 30px below the frame.

**The map sheet fits the viewport (>900px wide).** The page never scrolls: the sheet fills the full width and the space under the top strip (14px 24px table margin, 20px 24px sheet padding), and the map takes the whole neat-line frame — there is no margin column. Its title and key float over the map as readouts (white, 4px, the one shadow): title, scope and legend in one 17.5rem panel at the top-left; the filters (UF, Fonte, Conjunto) behind a 40px icon button at the top-right (purple funnel, plus the active count), opening as an 18rem menu of labelled selects with a "Limpar" text link when any is active; it closes on a click outside or Esc. The selected plant's readout sits under the button; the notes in a 90%-white footer band along the map's bottom edge, which the scale bar and zoom control sit above. Brazil is fitted to what the overlays leave clear (right of the left panel, above the footer) and refitted on every resize until the viewer pans or zooms. A filter frames its plants (padding 48px, max zoom 9) and no filter frames Brazil; the camera glides there over 900ms on the house ease (it jumps under reduced motion, and resizes always jump). Selecting never reflows anything; Esc clears it.

Responsive behaviour:
- **≤1180px:** the margin drops below the frame, becomes an auto-fit grid of 16rem blocks under a top rule.
- **≤900px:** the sheet flattens into reading order (on the map sheet the overlays drop into the frame as blocks: title, filters, the map, the selected plant, legend, notes): plot, then total and legend, then boards, then notes and sources. Index hints hide, the four index cells stay in one row, boards go single-column, sheet padding tightens to 20px 16px.
- **≤520px:** filters fold behind a "Filtros" disclosure showing the active count; low-value board columns (share bar, last column) hide.

### Named Rules
**The One Plot Rule.** A neat-line frame owns exactly one plot. Supporting tables and comparisons go below the frame on the sheet, never inside a second frame.

**The Margin Is The Key Rule.** Legend, total, notes and sources live in the margin column. They are not floated over the plot or put in cards. The one exception is the map sheet (user decision, 2026-10-05): the map fills the sheet and its key floats over it as readouts.

## Elevation & Depth

Flat paper on a table. A single soft shadow lifts the sheet off the table grey; everything on the sheet is flat and separated by hairline rules and whitespace. The same shadow is reused only for things that float over the sheet: chart tooltips, map popups, map controls.

### Shadow Vocabulary
- **Sheet lift** (`box-shadow: 6px 6px 18px rgba(40, 16, 80, 0.1), 0 1px 2px rgba(10, 10, 10, 0.06)`): the sheet, and floating readouts over it.

### Named Rules
**The One Shadow Rule.** One shadow value in the whole system. Nothing on the sheet surface (boards, legend, margin blocks) gets elevation.

## Shapes

Survey-sheet geometry: straight hairlines, small radii. The sheet rounds at 5px; controls, index cells (outer corners only), tooltips and legend hover rows at 4px; tags at 3px; swatches at 2px; dots and size rings are circles. The neat line is a 1.5px square-cornered purple stroke drawn as an SVG rect, with corner labels knocked out of it on white. Whole bars use 2px surface gaps between segments with 3px outer corners. Share bars round only their leading end (0 2px 2px 0).

## Components

### Buttons
Calm and rectangular; purple carries the action.
- **Shape:** gently squared (4px).
- **Primary:** Survey Purple fill and border, white 600 text, 10px 20px padding, 10px icon gap.
- **Hover / Focus:** fill shifts to Lifted Purple over 0.25s on the house ease; focus is the global blue ring.
- **Ghost:** transparent with Ghost Stroke border and purple text; hover fills Lavender Tint and the border turns purple. Used for "Limpar filtros", "Voltar ao mapa", "Limpar seleção".

### Segmented control
- **Style:** Ghost Stroke outline, 4px, cells divided by the same stroke, white cells with purple 600 text, 9px 16px.
- **State:** hover Lavender Tint; checked fills Survey Purple with white text. A radiogroup (e.g. Grão).

### Inputs / Fields
- **Style:** 40px high, white, Control Stroke border, 4px, 500 0.9375rem ink text, 12px side padding; label above in Label style.
- **Hover:** border darkens to #b7aed0. **Focus:** the global 2px Signal Blue outline.

### Navigation (sheet index)
Four joined cells (11.5rem max each), each a name (700, 0.9375rem) over a one-line hint (0.75rem, ink secondary). Hover takes Hover Wash; the current sheet takes Lavender Tint, a purple border and a purple name. The Usina cell is disabled (ink tertiary) until a plant is chosen. Under 1100px the hints hide so the logo and index stay one row; under 900px the cells shrink to centred names.

### Neat-line frame (signature)
The plot's frame: an SVG rect, 1.5px Survey Purple, drawn in over 1100ms on the house ease and static under reduced motion. Up to four corner labels sit on the stroke, knocked out on white, in Corner type: the plot's period (start and end dates or months) or, on the plant sheet, its latitude and longitude. On the map the frame carries the 5° graticule's degree labels and 7px ticks where the lines meet the frame.

### Margin blocks
Total (display figure plus sub-line plus whole bar), legend (swatch, name, share, pressable to focus a series), described legend (method name plus one-line explanation, rows split by Rule Faint), numbered notes, sources. Each block has a 1rem/800 heading.

### Boards
Fixed-column tables: sticky white header (0.78125rem/700, ink secondary, Rule underline), 8px cells, Rule Faint row dividers, a bold sum row above a Rule. Names are 700 with a small tabular sub-line (CEG, count). Ranked boards are clickable rows with Hover Wash. Share is shown as an inline bar at 55% purple tint scaled to the value. Values update in place while new data loads; the board never blanks.

### Whole bar
A single bar that visibly fills 100%: flex segments in their data hues with 2px gaps, 14px high in the margin, 22px as the reconciliation's headline whole. Estimated segments are hatched.

### Tags
Inline 0.71875rem/700 chips with a 3px radius. The only shipped variant is "estimado": ink text on a blue 45° hatch.

### Focus and dimming
Selecting a fonte, method or plant sets the others to 32% opacity (0.2s) across legend rows, board rows, dumbbell rows and plot series (areas drop to 0.04 fill and 0.25 stroke). On the map the selected plants get a 2.5px ink ring and the rest a 0.5px white one.

### States
Loading is a 140px, 2px purple ink stroke that draws across ("Lendo o Lakebase…"). A cold database is a loading state, not an error: the same ink stroke with "Acordando o banco de dados…" and a one-line ink-tertiary explanation, retrying every 3 s for ~30 s; when data is already on the sheet, the scope line says "acordando o banco…" and the values stay. Errors state the cause and offer a primary "Tentar de novo" button.

## Do's and Don'ts

### Do:
- **Do** give every page the sheet grammar: title block, one neat-line frame with one plot, boards below, margin column with legend, notes and sources.
- **Do** put only real values on the neat-line corners and graticule: the plot's actual period, the plant's actual coordinates, actual 5° degree lines.
- **Do** draw categorical colour from the fonte or method ramp in its fixed order, and label every hue in the margin legend.
- **Do** hatch estimated quantities and keep measured and modeled series visibly distinct (solid fonte hue for measured or primary, 1.5px dashed ink tertiary for modeled or average).
- **Do** make breakdowns sum visibly to 100% and let totals tie across sheets.
- **Do** use the single sheet shadow and the house ease (cubic-bezier(0.16, 1, 0.3, 1)) at 0.15–0.25s for state changes. Reduced motion removes the draw-in and all transitions.
- **Do** keep the UI copy PT-BR and number formatting pt-BR.

### Don't:
- **Don't** build KPI-card grids or a left-sidebar BI dashboard. The total belongs in the margin and navigation belongs in the sheet index.
- **Don't** put a second plot inside a neat-line frame or wrap boards in their own frames.
- **Don't** use fonte or method hues for text, chrome, buttons or backgrounds.
- **Don't** add decorative fixed-pitch ticks, rulers or fake coordinates to frames.
- **Don't** add shadows beyond the single sheet shadow, or elevate anything that sits on the sheet.
- **Don't** add motion beyond the ink-draw, the map camera's glide to a filter, the dimming fade and hover transitions.
- **Don't** show a Databricks mark or a fabricated logo. The brand slot is the text wordmark (Ampera in ink 700, Energia in Survey Purple 800).
