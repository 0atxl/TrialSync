# R5A shared CSS audit

**Status:** Completed and visually accepted by the user.
**Date:** 2026-08-25
**Scope:** Shared layout foundation only. Feature-specific redesign remains staged under R5A.

## Why this audit was required

The stylesheet contained three overlapping generations of application-shell rules: the original
foundation, a Phase 5B shell override, and the R5A foundation. Page-width caps were also split
between the global page container, ordinary workspaces, Research, and Help. This made source order,
rather than intentional ownership, determine several visible layouts.

The repeated symptoms were:

- the navigation moving to the bottom after its collapse control changed position;
- unused width moving between the left and right sides when navigation collapsed;
- Research using a different workspace width from Patients, Trials, and Screenings;
- Help retaining a separate 980px content cap.

## Cleanup completed

- Consolidated the current top bar, brand, account menu, shell grid, sidebar, navigation links,
  collapse control, page container, authentication layout, and primary/secondary actions under one
  R5A shared-foundation section.
- Removed obsolete `sidebar-toggle`, `sidebar-footer`, `signout-button`, `menu-icon`, and
  `nav-glyph` declarations for components no longer rendered.
- Removed the old bottom/compact navigation media rules.
- Removed stale 1040px ordinary-workspace, 980px Help, 1240px page, and 1440px page caps that
  competed with the full workspace layout.
- Preserved intentional narrow widths for focused forms and constrained detail/error states.
- Reduced `web/src/styles.css` from 2,966 to 2,628 lines without changing feature contracts.

## Ownership after cleanup

The R5A shared-foundation section owns:

- application shell and navigation;
- full-width page/workspace behavior;
- authentication layout;
- account-menu behavior and presentation;
- shared primary/secondary actions;
- shared headers, fields, loading/error states, and technical-details disclosures.

Feature sections still own their current patient, trial, screening, import, research, and catalog
styles. Duplicate selectors inside responsive media queries are intentional overrides. Other
feature-era duplication is deferred to the stage that replaces that feature, avoiding a risky
whole-product visual rewrite before its approved redesign.

### Modular follow-up during R5A-3

The R5A-3 acceptance audit found that keeping every retained and redesigned feature in the same
file was still difficult to maintain. CSS source order is preserved through explicit imports in
`web/src/main.tsx`, while ownership is now divided into:

- `styles.css` for the original base tokens and legacy primitives still awaiting replacement;
- `styles/workflows.css` for screening, report, conversation, research, and retained import rules;
- `styles/records.css` for patient/trial record and criteria workspaces;
- `styles/foundation.css` for the current shell, authentication, actions, and shared states;
- `styles/overview.css` for the Overview dashboard; and
- `styles/ingestion.css` for unified patient/trial entry and import review.

This reduced the global `styles.css` file from 2,949 lines at the start of the R5A-3 cleanup to
1,116 lines without changing selector order.

## Verification

- ESLint passed.
- TypeScript typecheck passed.
- All 92 frontend tests passed.
- Production build passed.
- `git diff --check` passed.

Automated screenshot inspection remains unavailable because the configured browser controller
cannot initialize in the current runtime. User visual confirmation of Login, Overview, Patients,
Trials, Screenings, Research, and Help remains the review gate.

## Remaining cleanup route

- R5A-3 removes obsolete patient/trial ingestion styles as those flows converge.
- R5A-4 removes replaced record-list/detail and screening-workspace styles.
- R5A-5 removes the old research-risk and recruitment-overview presentation.
- R5A-6 replaces the current Atlas presentation styles.
- R5A-7 performs the final unused-selector and content sweep.
