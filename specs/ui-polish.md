# CUTI UI polish — 2026-08-28

Status: scoped implementation complete; local typecheck/build and existing offline
verify pass. Full visual/keyboard browser acceptance remains pending.

## Outcome and authority

Make the existing interface compact, coherent, professional, and recognizably CUTI.
Use `DESIGN.md`, `GLOBAL_UX_RULES.md`, `RESPONSIVE_CONTRACT.md`, and
`MOTION_CONTRACT.md` for the existing visual and interaction requirements.
This is a bounded correction of the current interface, not a new product flow.
Preserve all four current routes, existing fields/actions, backend calculations,
pricing configuration behavior, saved state contracts, and source imagery.

## Accepted scope

1. Align existing CSS tokens with the authored CUTI palette. Keep IBM Plex Sans
   for prose/controls and Mono for evidence/numbers. Remove decorative gradient,
   glow, and blur; reduce repeated card borders/shadows without removing content.
2. Keep the decision result as the principal focal region. Preserve its reading
   order: verdict, buying limit, price gap, reason, detailed evidence. Use spacing,
   alignment, tonal surfaces, and table rules to organize supporting content.
3. Preserve complete mobile content. Supply labels for stacked market values,
   use mobile input text of at least 16px, and retain 44px interactive targets.
4. Complete existing autocomplete, tab, dialog, and popover keyboard/focus/ARIA
   behavior using Vue and native browser facilities. Preserve explicit product
   selection and existing context/focus restoration.
5. Distinguish loading, error, empty data, and no matching results. Give errors a
   relevant retry/next action. Do not display a fallback zero when data is missing;
   retain genuine backend zeroes. Do not add requests or infer market data.
6. Keep route/tab/panel motion within the existing contract and retain reduced
   motion. No animation dependency or decorative motion.

## Boundaries

- No new runtime/development dependency, framework migration, registry/adapter
  development, backend/schema/API change, business calculation, or large refactor.
- Reuse existing components/styles; change pricing settings only if needed for
  shared visual consistency, without altering preview/apply/revision semantics.
- Preserve unrelated working-tree changes. Capture the starting source outside
  the repo so this task can be reviewed separately from pre-existing work.
- Do not modify or add acceptance test source under the repository's handoff rule.
  Existing tests and reproducible diagnostic probes may be run; probes are not
  presented as permanent acceptance coverage.

## Resolver decision

The audit's `inspect_project` identified Vue 3/TypeScript/Vite/plain CSS.
`find_components` returned no compatible candidates for the requested app/table
and accessible interaction groups, both with and without offline restriction.
Keep the existing implementation. Do not force an incompatible component install
or change frameworks to fit the tool. Registry expansion is outside this change.

## Implementation and verification plan

1. Capture baseline source and run existing frontend typecheck/build. Identify a
   safe isolated local QA environment; do not use the real data/profile directory.
2. Apply the focused CSS/template/interaction changes in existing frontend files.
3. Run typecheck/build and relevant existing offline verification. If available,
   inspect the real UI at 1440, 1024, 768, 390, and 320px, light/dark, reduced motion,
   and keyboard flows. Check both loaded and missing/error states and overflow.
4. Preserve raw output, commands, exit codes, and environment metadata. Save UI
   render text/measurements as fixtures and replay diagnostic assertions where
   possible. Do not claim clean-machine/full live acceptance from narrower checks.
5. Review the task-specific diff for unnecessary complexity; update `notion.md`
   with precise evidence and any unverified items before handoff.

## Lean plan review (Lead)

- KEEP: visual consistency, readable hierarchy, mobile parity, keyboard/focus,
  meaningful data states, and proportional verification.
- SIMPLIFY: edit the current Vue/CSS implementation; do not build a new component
  framework, token generator, design gallery, or route/state abstraction.
- DEFER: third-party primitives, a Vue resolver adapter, and a broad redesign.
- DO NOT CUT: source data semantics, pricing safeguards, accessibility, reduced
  motion, mobile actions, or verification of existing user flows.
- Decision needed: none for implementation. Browser availability/authority and
  missing handoff metadata must be reported rather than invented.

## Implementation result and evidence

- Changed only `frontend/src/App.vue` and `frontend/src/styles.css` in application
  source. `PricingSettingsPage.vue`, backend, API/schema, dependencies, and test
  source were not changed by this task.
- Existing Vue/CSS now uses the CUTI palette, quieter form/record styling, semantic
  range colors, mobile field labels, 16px base inputs, and contract route timings.
- Added keyboard/ARIA handling to the existing autocomplete and tabs; named the
  detail dialog, contained focus, and made background navigation/content inert.
  Existing toast feedback remains available. Empty/error/loading states are
  separated, and missing coverage is not rendered as a default zero.
- Local checks: `docs/evidence/ui-polish/final2-typecheck-20260828.log` exit 0;
  `final2-build-20260828.log` exit 0; `final-verify-script-20260828.log` records
  361 tests and verify exit 0. `final-source-hashes-20260828.log` identifies the
  frozen source. See the current `notion.md` section for scope and limitations.
- No clean-machine claim, new acceptance-test coverage, full live checklist,
  multi-viewport screenshots, or visual quality sign-off is made.

## Lean result review (Lead)

Lean already for the implemented scope: retain the local state/keyboard handlers,
focus containment, accessible labels, empty/error guards, and CSS token changes.
They directly serve the accepted requirements; no new framework, dependency,
generic component system, or speculative configuration was introduced.

Protected behavior: existing data/calculation contracts, pricing settings,
explicit product selection, tab context, mobile actions, error feedback,
focus restoration, and reduced motion. No simplification is accepted that removes
those safeguards. Verification follow-up for simplification: none. Browser
acceptance is still required before claiming the visual/interaction gate complete.
