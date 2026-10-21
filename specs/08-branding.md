# 08 — Branding (reference for the app frontend)

## Goal

Brand tokens for the fictional firm Ampera Energia Analytics, guiding the Impeccable frontend (spec 06).
Not a build unit — a reference the app spec consumes.

## Palette

| Token | Hex | Use |
|-------|-----|-----|
| `--color-primary` | `#541790` | Purple — **dominant** brand anchor; primary CTAs, links, accents |
| `--color-secondary` | `#0089f7` | Bright sky blue — tech/data accent, hover, highlights |
| `--color-accent` | `#fe5200` | Orange — energy-sector accent, secondary CTAs |
| `--text-primary` | `#0a0a0a` | Headings / primary text |
| `--text-secondary` | `#626262` | Body / secondary text |
| `--bg-primary` | `#ffffff` | Primary background (light mode dominant) |
| `--bg-secondary` | `#f8f8f8` | Section/card background |
| `--bg-tint` | `#eae9f6` | Subtle purple tint areas |

## Typography

- Family: **Nunito** → fallback `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`.
- Weights: 300/400 (body), 500/600 (UI, buttons), 700 (headings), 800/900 (display).
- Base 16px; h1 ~42px, scaling down proportionally.

## UI feel

- **Light mode**, modern/corporate/tech, generous whitespace, card-based modular sections.
- Corner radius ~4–5px (buttons/cards), 50% for circular elements.
- Buttons: padding `10px 20px`, purple or blue bg, smooth `0.2–0.3s` hover transitions, 10px
  icon↔text gap.
- Soft shadows: `6px 6px 9px rgba(0,0,0,0.2)`; minimal borders — rely on color + spacing.
- Motifs: circuit/microchip, energy-grid, network/partnership icons; flat vector illustrations;
  data-viz graphics. Charts should favor the purple→blue→orange brand ramp.

## Note

Impeccable owns final visual decisions; these tokens anchor the direction so the demo clearly reads
as Ampera. Charts/maps should use accessible contrast against the light background.

## As built (spec 06)

`DESIGN.md` records the shipped system (the "carta topográfica" world). Differences from the tokens
above: a softer sheet shadow (`6px 6px 18px rgba(40,16,80,.10)`), a 2.25rem sheet title and a 3rem
display total instead of a ~42px h1, and orange `#fe5200` kept out of the UI chrome (it collided with
the Solar data hue) — it is not used in the UI. Data colors are separate validated
palettes, not the brand ramp.
