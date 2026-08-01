# TrialSync Codebase Health Audit

**Date:** 2026-08-01
**Status:** Repository-health snapshot after the clinical-catalog cleanup; this is
supporting guidance, not an implementation phase or replacement for the active
research and patient-data plans.

## Scope and measurements

The audit excludes dependencies, generated builds, caches, and local artifacts.
Physical line counts after removing proven stale code are:

| Area | Lines |
| --- | ---: |
| Backend runtime | 8,137 |
| Frontend runtime, including CSS | 7,441 |
| Alembic migrations | 1,039 |
| Backend, frontend, and browser tests | 6,612 |
| Total code and tests | 23,229 |

The repository is compact for its implemented scope. Raw line count is not the
primary risk; the important issue is concentration in a few large change
surfaces.

## Evidence collected

- The full backend suite contains 144 tests. The audit coverage run measured
  90% statement coverage across backend runtime modules.
- The frontend suite contains 66 tests, with browser coverage for the principal
  synthetic-data workflow.
- Static import analysis found no backend or frontend dependency cycles.
- After cleanup, no orphaned backend or frontend source modules remain.
- Exact cross-file duplication is limited mainly to the patient/trial catalog
  editors and their catalog-loading paths.
- Advisory complexity findings are concentrated in guided trial-criterion
  compilation, the deterministic rule engine, PDF/OCR parsing, and bounded
  provider clients rather than spread throughout the repository.

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
graph checks provide sufficient evidence for this checkpoint. A focused
CodeRabbit or equivalent diff review may be useful for a future large
structural refactor, while tools such as `knip`, `vulture`, `jscpd`, or an import
boundary checker should be added only if their checks will become maintained
quality gates.

Repeat this audit when a runtime page or API module exceeds roughly 1,000 lines,
when a new dependency layer is introduced, or after the research-extension
phases materially change the module graph.
