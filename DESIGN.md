---
version: alpha
name: CUTI — Contemporary Decision Intelligence
description: "A calm, precise decision workspace that turns watch-market evidence into an actionable buying boundary."
colors:
  canvas: "#F3F5F8"
  surface: "#FFFFFF"
  surface-muted: "#EEF2F7"
  ink: "#172033"
  ink-muted: "#596579"
  ink-subtle: "#607087"
  border: "#B9C4D2"
  border-strong: "#8492A6"
  cobalt: "#315DC7"
  cobalt-strong: "#24479D"
  cobalt-soft: "#E9EFFF"
  signal: "#C84245"
  signal-soft: "#FCECED"
  positive: "#176B52"
  warning: "#93631F"
  negative: "#B73532"
  on-accent: "#FFFFFF"
  dark-canvas: "#0D141F"
  dark-topbar: "#121B29"
  dark-surface: "#172232"
  dark-surface-muted: "#202D3F"
  dark-surface-cobalt: "#203665"
  dark-surface-signal: "#3A252D"
  dark-ink: "#EEF3FB"
  dark-ink-muted: "#B7C2D1"
  dark-border: "#435168"
  dark-border-strong: "#718198"
  dark-cobalt: "#496DCC"
  dark-cobalt-strong: "#A9BFFF"
  dark-cobalt-soft: "#233A70"
  dark-signal: "#F27A7D"
  dark-positive: "#2B8467"
  dark-warning: "#F2C46C"
typography:
  display-lg:
    fontFamily: IBM Plex Sans
    fontSize: 64px
    fontWeight: 500
    lineHeight: 1.02
    letterSpacing: -0.045em
  headline-lg:
    fontFamily: IBM Plex Sans
    fontSize: 55px
    fontWeight: 500
    lineHeight: 1.05
    letterSpacing: -0.04em
  headline-md:
    fontFamily: IBM Plex Sans
    fontSize: 29px
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: -0.025em
  body-lg:
    fontFamily: IBM Plex Sans
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.45
  label-caps:
    fontFamily: IBM Plex Mono
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.1em
  data-md:
    fontFamily: IBM Plex Mono
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.35
  data-sm:
    fontFamily: IBM Plex Mono
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: 0.06em
rounded:
  xs: 4px
  sm: 6px
  md: 7px
  lg: 9px
  full: 9999px
spacing:
  micro: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  section: 48px
  page-bottom: 88px
  desktop-gutter: 24px
  mobile-gutter: 14px
components:
  topbar:
    backgroundColor: "#F8F9FB"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xs}"
    height: 72px
    padding: 0px 64px
  local-clock:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.data-sm}"
    rounded: "{rounded.md}"
    height: 44px
    padding: 8px
  theme-toggle:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    height: 44px
    padding: 11px
  page-context:
    backgroundColor: "{colors.cobalt-soft}"
    textColor: "{colors.cobalt-strong}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.md}"
    padding: 20px
  button-primary:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-accent}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    height: 46px
    padding: 17px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    height: 46px
    padding: 17px
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    height: 48px
    padding: 13px
  filter-active:
    backgroundColor: "{colors.cobalt-soft}"
    textColor: "{colors.cobalt-strong}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    height: 44px
    padding: 12px
  decision-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "{spacing.xl}"
  decision-metrics-negative:
    backgroundColor: "{colors.signal-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  market-record:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xs}"
    height: 64px
    padding: 12px
  pagination-button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.data-sm}"
    rounded: "{rounded.md}"
    height: 44px
    padding: 12px
  detail-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xs}"
    padding: 32px
---

# CUTI — Contemporary Decision Intelligence

## Overview

CUTI is a **decision workspace**, not a watch storefront and not a generic dashboard. It helps a buyer identify the exact product, inspect market evidence, compare the asking price with a defensible buying limit, and decide what to do next.

The product should feel **calm, precise, and consequential**. Its character comes from confident typography, disciplined alignment, soft technical surfaces, and a narrow semantic palette. “THE CUT” remains the core idea—the moment evidence becomes a buying boundary—but it is expressed through hierarchy and contrast rather than hard-edged brutalism.

The interface has four voices:

- **Workspace:** quiet blue-gray canvas and white surfaces that support long, focused use.
- **Intelligence:** cobalt context fields, selected states, and concise mono metadata that explain what the system is doing.
- **Decision:** a focused result surface where verdict, buying limit, price gap, and reason become the visual climax.
- **Time:** a live local clock in the persistent top bar reinforces that market context and auction activity are time-sensitive.

The result should look authored and deliberate without borrowing luxury-watch clichés or becoming a rounded SaaS tile collection.

## Colors

The palette uses cool neutral surfaces with one structural blue and restrained semantic colors.

- **Canvas** {colors.canvas} is a quiet blue-gray workspace that reduces glare and separates white working surfaces without visible boxes everywhere.
- **Surface** {colors.surface} holds inputs, evidence rows, results, and panels. **Surface muted** {colors.surface-muted} groups related metrics and hover states.
- **Ink** {colors.ink} is a deep blue-black for titles and essential content. Muted and subtle ink create hierarchy without lowering legibility.
- **Cobalt** {colors.cobalt} is the product's intelligence color. It marks active routes, primary actions, focus, selection, and contextual signals. Large solid cobalt fields are not part of this system.
- **Cobalt soft** {colors.cobalt-soft} is the preferred background for selected navigation, active filters, and compact context panels.
- **Signal red** {colors.signal} is reserved for an unfavorable decision boundary or real exception. It is always paired with text and a changed verdict state.

Dark mode is an authored companion palette, not an inversion. It uses {colors.dark-canvas} and {colors.dark-surface} as its workspace layers, {colors.dark-ink} for primary content, and brighter semantic colors designed for dark surfaces. Interactive borders and focus rings retain at least 3:1 contrast; normal text targets at least 4.5:1 in both themes.

Do not introduce gradients, glossy black, metallic gold, leather brown, or jewel tones to make the product feel “watch-like.”

## Typography

**IBM Plex Sans** is the primary voice for navigation, titles, labels, controls, and explanatory copy. Medium-weight display type creates authority without theatrical boldness.

**IBM Plex Mono** is used only where the content behaves like evidence: references, monetary values, ratios, timestamps, row indices, pagination, and compact system context. It must not dominate body copy or general navigation.

The fonts are bundled with the application. Arial and Consolas remain implementation fallbacks only; they are not equivalent expressions of the design.

Hierarchy rules:

- Page titles orient the workspace and may reach 64px on wide screens.
- Verdicts receive display-scale treatment because they close the decision flow.
- Supporting copy stays restrained and readable, with a maximum practical line length.
- Financial values use mono type with tight optical spacing and locale-correct formatting.
- Uppercase plus letter spacing is limited to eyebrows, column headings, and small system labels.

## Layout

Desktop pages use a maximum working width of **1220px** with fluid outer gutters.

- The sticky 72px top bar uses three stable anchors: CUTI identity, centered routes, and a live-actions group containing local time, theme control, and data freshness.
- Each route begins with a composed intro. Eyebrow, title, and supporting copy sit on the left; a compact cobalt-soft context panel sits on the right. The context panel never competes with the title.
- Assessment uses a narrow step rail beside the form workspace, preserving sequential reading without wizard chrome.
- Market controls flow from tabs to search/filters, then a labeled evidence table, then pagination. Records remain server-paginated at eight per view.
- At 767px and below, intros stack, columns collapse, route navigation moves to the bottom, and detail panels become full-width.

Whitespace establishes phases of thought. Hairline rules are used only for comparison, table rhythm, or persistent boundaries—not as containers around every element.

## Elevation & Depth

Depth is quiet and functional:

- The default canvas and white surfaces create the base layer.
- Inputs and status controls use a minimal 2px–8px shadow to show interactivity.
- Decision results, autocomplete, popovers, and detail panels use a restrained larger shadow because they sit above the active workspace.
- Selected states rely on cobalt-soft tonal contrast rather than elevation.

Avoid glassmorphism, ambient glow, stacked floating cards, heavy outlines, and large decorative shadows. Motion is short, low-distance, and disabled through reduced-motion preferences.

## Shapes

Corners use a restrained **4px–9px radius**. This removes prototype harshness while preserving a technical, serious character. The system must not drift into pill-shaped controls or bubble-card composition.

Icons use a 24x24 SVG viewBox, `currentColor`, no fill, a 1.6px stroke, and consistent rounded caps and joins. They improve scanning but never replace visible labels or accessible names.

## Components

### Top bar

Use a neutral surface with a subtle lower rule. The CUTI mark keeps its cobalt slash. Active routes use a compact cobalt-soft field; inactive routes remain quiet and gain a tonal hover state. The right side groups time, theme, and freshness without competing with primary navigation.

### Local clock and theme

The clock displays browser-local 24-hour time as `HH:mm:ss` with a compact Vietnamese date. It uses a semantic `time` element and a clock SVG. Seconds and the date may hide on compact screens, but hours and minutes remain visible. It must not use `aria-live`, because announcing every second would be disruptive.

The theme button shows sun/moon SVG plus a concise action label on desktop. It follows system preference on first visit, persists an explicit choice, and applies the selected color scheme before the app renders. Both themes preserve semantic meaning rather than swapping colors mechanically.

### Page intro

The left side carries orientation and intent. The right context panel summarizes the route's operational model—for example `INPUT → EVIDENCE → DECISION` or `8 RECORDS PER VIEW`. It uses a narrow cobalt leading rule rather than a large blue block.

### Inputs and actions

Inputs sit on white surfaces with subtle depth and a quiet lower rule. Focus changes the complete border to cobalt and adds a soft focus ring. Primary actions use cobalt; secondary actions stay white with a light border. Every interactive target is at least 44px high.

### Decision field

The result is the visual focal point: large verdict, compact save action, paired decision metrics, and a readable reason. The normal state uses a cobalt top signal. When the price gap is unfavorable, the top signal and metric surface switch to semantic red while the textual verdict remains explicit.

### Market records

Market content is a labeled evidence table, not a set of product cards. Column headings explain the comparison before the rows begin. Each page contains exactly eight records, numbered `01` through `08`, with strong titles, quiet references, aligned values, and restrained hover feedback.

### Pagination

Show only Previous, `Page X / Y · total`, and Next. Pagination remains visually subordinate to the records and never renders hundreds of page-number buttons.

### Detail panel and feedback

Details enter from the right with a soft directional shadow while preserving the list as context. Popovers, autocomplete, and toasts use tonal contrast and modest elevation. Missing values are written as `Không đủ dữ liệu` or `Không có`; never expose `null`, `NaN`, placeholder zeroes, or inferred data.

## Do's and Don'ts

- **Do** make the decision boundary visible within three seconds.
- **Do** establish hierarchy with size, weight, spacing, alignment, and tonal surfaces before adding a border.
- **Do** use cobalt for structure, selection, and primary action.
- **Do** reserve signal red for crossed boundaries or genuine exceptions.
- **Do** keep market records comparable, labeled, numbered, and limited to eight per page.
- **Do** preserve keyboard focus, 44px targets, responsive reflow, and reduced motion.
- **Do** maintain WCAG AA contrast in both themes: 4.5:1 for normal text and 3:1 for focus rings and necessary control boundaries.
- **Do** keep local time visible in compact form without crowding navigation.
- **Don't** imitate watch boutiques, auction houses, luxury e-commerce, or generic analytics dashboards.
- **Don't** turn every information group into a floating rounded card.
- **Don't** use mono type for ordinary navigation, labels, or explanatory prose.
- **Don't** add gradients, decorative charts, glossy effects, or imagery without informational value.
- **Don't** hide uncertainty behind a default number or inferred value.
- **Don't** announce the ticking clock through a live region or add a timezone chooser without a product requirement.

## Evaluation Lens

1. Can the user identify the decision boundary within three seconds?
2. Does each screen have one clear focal point and a readable secondary path?
3. Is every strong color carrying semantic work?
4. Would the product still read as CUTI with all watch-category imagery removed?
5. Do spacing and tonal surfaces carry most of the structure instead of visible boxes?
6. Does the mobile composition preserve hierarchy rather than becoming a generic stacked form?
