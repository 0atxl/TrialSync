# TrialSync Codebase Health Audit

**Date:** 2026-08-02
**Status:** Repository-health snapshot after PD6, the R1 report, and R2 CI; this
is supporting guidance, not an implementation phase or replacement for the active
research and patient-data plans.

## Scope and measurements

The audit excludes dependencies, generated builds, caches, and local artifacts.
Physical line counts after removing proven stale code are:

| Area | Lines |
| --- | ---: |
| Backend runtime | 9,415 |
| Frontend runtime, including CSS (tests excluded) | 7,589 |
| Alembic migrations | 1,123 |
| Backend, frontend, and browser tests | 7,082 |
| Total application code and tests | 25,209 |

For context, all tracked repository text is approximately 40,178 lines when
Markdown documentation and JSON/lock/configuration files are included. These
counts exclude dependencies, generated builds, caches, and local artifacts.

The repository is compact for its implemented scope. Raw line count is not the
primary risk; the important issue is concentration in a few large change
surfaces.

## Evidence collected

- The full backend suite contains 151 tests. The audit coverage run measured
  90% statement coverage across backend runtime modules.
- The frontend suite contains 69 unit/component tests, and the repository keeps
  a separate browser workflow for the principal synthetic-data path. The
  browser workflow was not rerun here because `make test-e2e` reseeds the demo
  workspace; the existing frontend gate was kept non-destructive while the
  user is exploring the running demo.
- Static import, lint, type-check, and route scans found no backend or frontend
  dependency cycles or orphaned runtime source modules.
- Exact cross-file duplication is limited mainly to the patient/trial catalog
  editors and their catalog-loading paths.
- Advisory complexity findings are concentrated in guided trial-criterion
  compilation, the deterministic rule engine, PDF/OCR parsing, and bounded
  provider clients rather than spread throughout the repository.
- `pip-audit --local` is clean. The transitive `brace-expansion` advisories
  reported by the initial JavaScript audit are resolved in the lockfile. npm
  still reports [the React Router RSC advisory](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)
  for the current 7.x DOM package;
  this SPA does not use the unstable RSC APIs. React Router v8.3 is the patched
  line, and [the v8 upgrade guide](https://reactrouter.com/upgrading/v7)
  documents that v8 intentionally removes the `react-router-dom` re-export package;
  the eventual migration must move ordinary imports to `react-router`,
  DOM-specific imports such as `RouterProvider` to `react-router/dom`, and raise
  React/React DOM to the v8 minimum. Keep this as a tracked migration item
  rather than forcing a failing CI gate.

## Cleanup completed at this checkpoint

1. Alembic revision `20260729_0009` owns a frozen initial clinical-catalog seed
   and no longer imports mutable application modules.
2. Runtime catalog code contains only database record adaptation and queries;
   obsolete in-memory lookup and response constants were removed.
3. The unreachable `FoundationPage` and `PlaceholderPage` modules were removed.
4. Migration-contract tests now prevent application imports from revisions and
   verify the frozen 25-concept seed against the approved PD0 inventory.

## Maintainability priorities

Address these only as separate, behavior-preserving tasks with the applicable
plan authority and full regression checks:

1. Decompose `PatientDetailPage` into profile, consistency, clinical-detail,
   and unsupported-detail regions with a focused orchestration hook.
2. Decompose `TrialDetailPage` and move guided-criterion compilation from the
   API router into a dedicated service/domain module.
3. Introduce one shared catalog-loading hook; extract shared editor primitives
   only where patient and trial semantics remain explicit.
4. Split the global stylesheet into tokens/base, shell, shared controls, and
   route-focused files while retaining the existing visual regression process.
5. Split backend and frontend API contracts by bounded context before the
   research phases add report and analytics schemas.
6. Split the monolithic frontend workflow test and demo seeder by domain without
   reducing coverage or changing deterministic fixtures.

The deterministic screening engine is complex but cohesive and strongly
tested. Refactor it only for a concrete rule change or when characterization
coverage fully protects reason codes, rejected evidence, and three-valued
logic.

## Tooling decision

No code-graph MCP, hosted reviewer, or new dependency is required at the current
repository size. Existing compiler, linter, coverage, browser, and local import
graph checks provide sufficient evidence for this checkpoint. Function-level
dead-code detection is not mechanically proven because `knip`, `vulture`,
`jscpd`, and an import-boundary checker are not maintained project gates; the
CSS and copy cleanup above is limited to confirmed unreferenced selectors and
stale wording. Add one of those tools only when its check can be maintained as a
quality gate. npm audit remains a manual review until the React Router v8 import
migration is scheduled and completed.

Repeat this audit when a runtime page or API module exceeds roughly 1,000 lines,
when a new dependency layer is introduced, or after the research-extension
phases materially change the module graph.
