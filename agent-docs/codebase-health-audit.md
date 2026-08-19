# TrialSync Codebase Health Audit

**Date:** 2026-08-13
**Status:** Historical repository-health snapshot after PD6, R1/R2, and codebase remediation.
It was updated for the Phase 8 review candidate; the R3 experiment dataset was subsequently
accepted for R4. This is supporting history, not current guidance or a replacement for the active
research and patient-data plans.

## Scope and measurements

The audit excludes dependencies, generated builds, caches, and local artifacts. The following
physical line counts are the preserved 2026-08-04 size snapshot and are useful only as scale
context, not as current quality metrics:

| Area | Lines |
| --- | ---: |
| Backend runtime | 9,955 |
| Frontend runtime, including CSS (tests excluded) | 7,582 |
| Alembic migrations | 1,123 |
| Backend, frontend, and browser tests | 7,387 |
| Total application code and tests | 26,047 |

For context, all tracked repository text is approximately 41,586 lines when
Markdown documentation and JSON/lock/configuration files are included. These
counts exclude dependencies, generated builds, caches, and local artifacts.

The repository is compact for its implemented scope. Raw line count is not the
primary risk; the important issue is concentration in a few large change
surfaces.

## Evidence collected

- The 2026-08-14 full backend suite contains 173 passing tests. Thirteen focused R3 tests cover 88.22%
  of `generate_r3_nemo.py`, above the enforced 75% research gate. The earlier whole-runtime audit
  measured 90% statement coverage before the R3 package entered the configured source set.
- The frontend suite contains 72 unit/component tests, and the repository keeps
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
- Strict mypy now checks 51 application/research source files, Ruff includes research code, and
  missing Data Designer dependencies can no longer silently skip R3 tests.
- The R3 artifact contract freezes seven source tables and three derived views. The accepted
  400-row artifact passes exact schema, foreign-key, immutable-snapshot, chronology, censoring,
  participant-split, and leakage checks; its 64/400 (16%) dropout prevalence is recorded as an
  observed synthetic result rather than a forced target.
- The 4,000-row experiment review candidate contains 702 synthetic dropouts (17.55%) across a
  frozen 2,800/600/600 split. Its generator validation, EDA, directional relationship checks,
  leakage audit, linkage manifest, dataset card, feature dictionary, and checksums pass.
- Dependency remediation upgraded `pypdf` to 6.15.0 and refreshed frontend `js-yaml`, `nanoid`,
  and PostCSS to patched lockfile versions. npm reports zero vulnerabilities. Python reports no
  findings except the explicitly reviewed `PYSEC-2026-3552`: Data Designer 0.8.0 and the latest
  checked 0.9.1 cap transitive `cryptography` at 49 while the fix requires 50.0.0. The non-exposed
  PKCS#7-decryption path, controls, and removal condition are recorded in
  `dependency-security-exceptions.md`.

## Cleanup completed at this checkpoint

1. Alembic revision `20260729_0009` owns a frozen initial clinical-catalog seed
   and no longer imports mutable application modules.
2. Runtime catalog code contains only database record adaptation and queries;
   obsolete in-memory lookup and response constants were removed.
3. The unreachable `FoundationPage` and `PlaceholderPage` modules were removed.
4. Migration-contract tests now prevent application imports from revisions and
   verify the frozen 25-concept seed against the approved PD0 inventory.
5. Research dependencies are declared and exercised in CI; the current Data Designer
   sampler/expression route has no API-key gate and makes zero hosted model requests.
6. Confirmed dead/unreachable generator and rule-validation paths were removed, and legacy
   persisted string enums now use `StrEnum` without a data migration.
7. The R3 machine contract records exact ordered schemas, immutable enrollment-snapshot semantics,
   `site_region`, provenance, schema fingerprints, and run metadata for future generations.
8. `make audit` and CI now check Python plus frontend dependencies at moderate-or-higher severity,
   with only the named Data Designer/cryptography exception permitted.

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
quality gate. Python and npm advisory checks are now unified under `make audit` and run in CI;
temporary ignores require a dedicated bounded exception record.

Repeat this audit when a runtime page or API module exceeds roughly 1,000 lines,
when a new dependency layer is introduced, or after the research-extension
phases materially change the module graph.
