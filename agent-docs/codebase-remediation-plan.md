# TrialSync Codebase Remediation Plan

**Date:** 2026-08-13
**Status:** Phases 1–7 complete; Phase 8 evidence complete and awaiting dataset acceptance
**Scope:** Repository health work required before freezing and generating the
4,000-enrollment R3 experiment cohort. This plan does not replace the active
research-extension plan or authorize later R4 model implementation.

## Goals

- Make the R3 generator reproducible from a clean checkout.
- Ensure CI and local quality gates exercise research code instead of silently skipping it.
- Remove confirmed dead, unreachable, misleading, and stale implementation paths.
- Bring active documentation into agreement with generated artifacts and current project scope.
- Resolve dependency advisories before final delivery.
- Preserve the reviewed `r3-nemo-btech-v3` generation probabilities unless a correctness test
  demonstrates that the data-generating logic must change.

## Phase 1 — Reproducible research toolchain

**Status:** Complete (2026-08-13)

1. Declare NVIDIA Data Designer 0.8.0 as a pinned optional research dependency.
2. Align the Ruff pin with the version required by Data Designer and used by the workspace.
3. Make `backend/research` and its configuration directory importable Python packages.
4. Define the typing boundary for Data Designer, which does not publish a `py.typed` marker.
5. Include research code in Ruff and mypy checks.
6. Install research dependencies in CI.
7. Remove test-level dependency skipping so a missing research dependency fails visibly.

Exit criteria:

- A clean CI environment installs the R3 dependency explicitly.
- R3 tests cannot silently skip because Data Designer is absent.
- Ruff and mypy inspect `backend/research`.
- The installed and declared Ruff versions agree.

Completion evidence:

- `data-designer==0.8.0` and `ruff==0.16.2` install from the declared
  `backend[dev,research]` extras.
- The installed package exposes both `trialsync` and `research`; the established direct generator
  command remains valid.
- The R3 tests import Data Designer directly and therefore fail instead of skipping when the
  dependency is missing.
- Strict mypy passes for all 49 application and research source files.
- All 165 backend tests pass, including the six R3 tests.
- The Phase 1 Ruff scope passes. The repository-wide Ruff command now reaches research code and
  reports only the nine legacy string-enum findings assigned to Phase 2.

## Phase 2 — Confirmed code cleanup

**Status:** Complete (2026-08-13)

1. Remove the unused NVIDIA API-key gate from local sampler-and-expression generation.
2. Remove the unused `_conditional_bernoulli` helper.
3. Remove or correct the unreachable rule-field branch.
4. Convert legacy database string enums to `StrEnum` for the current Ruff/Python baseline.
5. Remove imports made obsolete by these changes.

Exit criteria:

- No confirmed dead or unreachable implementation remains from the audit.
- The sampler-and-expression generator runs without provider credentials.
- The configured Ruff gate passes.

Completion evidence:

- The generator no longer reads or requires `NVIDIA_API_KEY`; a regression test removes the
  variable and proves execution reaches Data Designer construction.
- The unused `_conditional_bernoulli` helper and its obsolete implementation are removed.
- Rule-field validation now uses a generic key type, making its non-text-field branch reachable
  by construction, and a focused test covers that behavior.
- All nine database string enums use Python `StrEnum`; persisted member names and values remain
  unchanged, so no database migration is required.
- The complete `make verify` gate passes: 167 backend tests, Ruff, strict mypy over 49 source
  files, migrations, import and held-out evaluation checks, 72 frontend tests, frontend lint and
  typecheck, and the production build.

## Phase 3 — R3 characterization and export tests

**Status:** Complete (2026-08-13)

1. Assert exact schemas for the seven source tables and three derived views.
2. Exercise the complete tiny Data Designer generation path in a temporary directory.
3. Test foreign keys, chronology, censoring, splits, and day-30 feature leakage.
4. Test exclusion of hidden tiers and random draws from model-ready views.
5. Test generation and validation report contracts.
6. Clarify attempted-versus-accepted enrollment semantics.
7. Raise `generate_r3_nemo.py` coverage from the audited 47% to a practical target of at least
   75% before the experiment cohort is frozen.

Exit criteria:

- A broken final export, schema, relationship, or report fails an automated test.
- The credential-free tiny generation succeeds.

Completion evidence:

- Exact ordered column contracts now govern all seven source tables and three derived views;
  missing, unexpected, or reordered columns fail before export. The orchestrator normalizes
  Data Designer's provider-dependent output ordering to this stable Parquet contract.
- Output validation now enforces unique linkage IDs, participant/enrollment resolution,
  canonical split propagation, participant-level isolation, dropout/censoring chronology,
  event truncation, dose arithmetic, measurement ranges/missingness, and adverse-event grades.
- Model-view validation rejects hidden generator fields, sampler draws, outcome details, and
  mismatched feature cutoffs. Tests prove day-30 features ignore future events and recompute all
  affected adherence aggregates after a pre-cutoff missed-dose edit.
- Generation and validation report contracts record the installed Data Designer version, all
  table counts, split outcomes, model usage, and explicit requested/attempted/accepted/rejected/
  unfilled enrollment accounting. The current single-pass protocol designs every candidate to
  satisfy its canonical screening and does not claim bounded resampling.
- The protocol-defined 50-enrollment credential-free Data Designer smoke completed using
  sampler/expression columns only: 50 accepted enrollments, 11 dropouts (22%), 35/8/7
  train/validation/test rows, ten validated Parquet outputs, and zero model requests.
- R3 tests cover 88% of `generate_r3_nemo.py`, above the 75% gate now enforced by `make verify`.

## Phase 4 — Data-contract reconciliation

**Status:** Complete (2026-08-13)

1. Preserve the seven source tables and three derived views.
2. Treat baseline fields copied into enrollment rows as an immutable enrollment snapshot and stop
   describing the physical files as fully normalized.
3. Reconcile documented fields such as `site_id`, run identifiers, and generator metadata with
   the exported schemas.
4. Keep `r3-nemo-btech-v3` probabilities unchanged unless Phase 3 finds a correctness defect.
5. Record the observed 400-row prevalence of 16% as a generated result rather than implying an
   exact 25% requirement.

Exit criteria:

- Code, exported schemas, feature definitions, and claims agree.

Completion evidence:

- `r3-dataset-contract-v1` freezes the exact ordered columns for all seven source tables and
  three derived views, the canonical `site_region` field, forbidden model fields, hidden-tier
  probabilities, per-column provenance, and a deterministic schema fingerprint.
- The enrollment file is explicitly described and validated as an intentionally denormalized,
  immutable copy of participant baseline fields. It is no longer treated as fully normalized.
- New artifacts receive a unique generation-run ID, UTC generation timestamp, contract version,
  schema fingerprint, physical-layout declaration, and complete column-provenance map in both
  generation metadata and validation evidence where applicable.
- The accepted 400-row demo artifact passes the reconciled schema, relationship, chronology,
  leakage, split, and immutable-snapshot checks. Its 64 dropouts (16%) are recorded in
  `backend/research/reports/r3_demo_400_observed.json` as an observed stochastic result, not a
  forced 25% target or clinical estimate. Because that artifact predates run-ID metadata, the
  record leaves its run and contract identifiers null instead of inventing them retrospectively.
- The reviewed `r3-nemo-btech-v3` hidden-tier probabilities remain unchanged at 8%, 18%, 35%,
  and 55%; Phase 3 found no correctness defect requiring a value-generating version change.
- Twelve focused R3 tests pass with 88% generator coverage, and Ruff plus strict mypy pass for
  the research package.

## Phase 5 — Active documentation cleanup

**Status:** Complete (2026-08-13)

Update the README, R3 generation guide, architecture, evaluation, limitations, research plan,
and health audit to:

- record successful 20- and 400-enrollment runs;
- identify the 4,000-enrollment experiment cohort as pending at the Phase 5 checkpoint;
- describe Data Designer generation as local sampler-and-expression execution;
- remove the NVIDIA API-key instruction for the current recipe;
- remove stale conditional-Bernoulli wording;
- record current generated statistics, schemas, test counts, and audit findings.

Exit criteria:

- No active document contradicts the implementation or current R3 status.

Completion evidence:

- At the Phase 5 checkpoint, the README, R3 generation guide, architecture, evaluation,
  limitations, research plan, health audit, and feasibility note agreed that the smoke/demo
  artifacts were accepted while the experiment cohort remained pending. Phase 8 supersedes that
  historical status with the generated 4,000-row review candidate.
- The accepted results are recorded as 4/20 (20%) and 64/400 (16%), with the 400-row split counts
  of 45/280, 10/60, and 9/60. Documentation explicitly distinguishes generated prevalence from
  prediction accuracy, a forced target, and a clinical estimate.
- Active instructions now describe Data Designer 0.8.0 sampler/expression execution as local CPU
  work with zero hosted model requests and no NVIDIA API-key requirement. Stale conditional-sampler,
  approximate-25%-target, bounded-resampling, and pending-smoke wording is removed.
- The documents record the frozen seven-source-table/three-view contract, `site_region`, intentional
  immutable enrollment snapshot, Parquet outputs, run/provenance metadata, and primary day-30 view.
- The audit corrected an older overclaim: R3 invokes the pure canonical screening domain engine on
  typed synthetic inputs but does not persist matching PostgreSQL patient/trial/screening rows.
  Bounded product-link materialization remains an R5 responsibility.
- The complete `make verify` gate passes with 172 backend tests, 12 focused R3 tests at 88%
  generator coverage, 72 frontend tests, Ruff, strict mypy over 51 source files, migrations,
  Compose validation, held-out evaluation, frontend lint/typecheck, and production build.

## Phase 6 — Dependency remediation

**Status:** Complete (2026-08-13)

1. Upgrade the direct `pypdf` dependency to a compatible patched release.
2. Resolve the Data Designer transitive `cryptography` advisory when its compatibility constraint
   permits a patched release; document any temporary upstream block.
3. Refresh frontend transitive `js-yaml`, `nanoid`, and PostCSS dependencies.
4. Re-run Python and JavaScript dependency audits plus relevant regression tests.

Exit criteria:

- No unresolved high-severity advisory remains without a documented upstream constraint and
  bounded risk decision.

Completion evidence:

- Direct `pypdf` is upgraded from 6.14.2 to patched 6.15.0; 21 focused PDF/import tests pass.
- The frontend lockfile now resolves `js-yaml` 4.3.1, `nanoid` 3.3.18, and PostCSS 8.5.26. A
  clean `npm ci` succeeds and `npm audit --audit-level=moderate` reports zero vulnerabilities.
- Data Designer 0.8.0 requires `cryptography>=48.0.1,<=49`. A resolver check against the latest
  available Data Designer 0.9.1 confirms the same cap, while `PYSEC-2026-3552` requires
  `cryptography>=50.0.0`. Forcing the patched version would violate the dependency contract.
- `agent-docs/dependency-security-exceptions.md` records the exact advisory, dependency path,
  non-exposed PKCS#7-decryption attack path, audit exception, invalidation conditions, and required
  upstream recheck. `make audit` ignores only that ID and rejects all other moderate-or-higher
  npm findings and all other Python findings.
- CI now runs the shared Python/frontend `make audit` gate. The local audit reports no known Python
  vulnerabilities other than the one named exception and zero npm vulnerabilities.
- `pip check`, 12 focused R3 tests, 21 PDF/import tests, and the complete `make verify` gate pass:
  172 backend tests, 88% generator coverage, 72 frontend tests, Ruff, strict mypy, migrations,
  Compose validation, held-out evaluation, frontend lint/typecheck, and production build.

## Phase 7 — Repository verification gate

**Status:** Complete (2026-08-13)

Run backend tests, coverage, Ruff, mypy, import checks, Alembic checks, held-out evaluation,
frontend lint/typecheck/tests/build, Compose validation, and dependency/secret scans. Browser E2E
is required only if remediation changes user-visible behavior or when the final delivery gate is
run, because its setup reseeds the demo workspace.

Exit criteria:

- Every applicable check passes and generated data remains outside Git.

Completion evidence:

- Development and production Compose configurations validate. Production validation used the
  checked-in synthetic environment example rather than requiring or reading deployment secrets.
- Alembic is at revision `20260802_0012` (head), and `alembic check` reports no new upgrade
  operations.
- A tracked/source-file credential-pattern scan reports no private-key headers or common AWS,
  GitHub, NVIDIA, OpenAI, or Google credential formats. No `.env`, production environment,
  Parquet, model, MLflow, upload, or generated-artifact file is tracked.
- `artifacts/`, `models/`, `uploads/`, and now `mlruns/` are explicitly ignored. The accepted
  20/400 R3 artifacts remain local and outside Git; no artifact symlink bypass was found.
- The complete `make verify` gate passes: 172 backend tests, 12 focused R3 tests at 88% generator
  coverage, 72 frontend tests, Ruff, strict mypy over 51 source files, migrations, Compose
  validation, held-out evaluation, frontend lint/typecheck, and production build.
- Current dependency scans report zero npm vulnerabilities and no known Python vulnerabilities
  other than the single documented `PYSEC-2026-3552` Data Designer/cryptography exception.
- `git diff --check`, `pip check`, the production Compose check, and the tracked-file size/artifact
  checks pass. Browser E2E was not rerun because remediation introduced no user-visible behavior
  and this is the pre-cohort verification checkpoint rather than final project delivery; the suite's
  preparation also intentionally reseeds the demo workspace.

## Phase 8 — Freeze and generate the experiment cohort

**Status:** Review candidate complete (2026-08-14); final acceptance pending.

1. Retain `r3-nemo-btech-v3` if remediation does not change generated values.
2. Retain the accepted 400-row demo artifact if its generation contract is unchanged.
3. Generate 4,000 enrollments into a separate experiment artifact directory.
4. Produce EDA, data-quality, leakage, relationship, dataset-card, feature-dictionary, and
   checksum evidence.

Exit criteria:

- The experiment dataset is frozen and approved for R4 without test-set tuning.

Review evidence:

- The separate `artifacts/nemo/r3_experiment_4000` candidate contains 4,000 enrollments and 702
  synthetic dropouts (17.55%) across a frozen 2,800/600/600 split.
- Seven source tables and three views pass schema, linkage, immutable-snapshot, chronology,
  censoring, split, range, and leakage validation with zero model requests.
- All five reviewed directional relationships are observed; the primary view contains no hidden
  generator fields or forbidden future-outcome columns and no participant crosses splits.
- The local package contains EDA, a dataset card, a 22-predictor feature dictionary, a 4,000-row
  linkage manifest, and 626 verified SHA-256 checksums. Aggregate evidence is checked in at
  `backend/research/reports/r3_experiment_4000_observed.json`.
- The complete repository gate passes with 173 backend tests, 13 focused R3 tests at 88.22%
  generator coverage, 72 frontend tests, Ruff, strict mypy, migrations, Compose validation,
  held-out evaluation, lint/typecheck, and the production build.

## Phase 9 — R4 model-scope checkpoint

Retain the existing R4 comparison selected for the project: dummy prevalence, logistic
regression, XGBoost, and LightGBM. The mentor did not explicitly require Random Forest; do not add
it unless a later experiment needs that extra benchmark.

## Deferred maintainability work

The following findings are real but do not block R3 data generation:

- split the R3 generator into generation, validation, and view-building modules after
  characterization coverage exists;
- decompose the large patient/trial pages and API routers;
- split the monolithic frontend workflow test and demo seeder;
- refactor the deterministic rule engine only when a concrete rule change and characterization
  coverage justify the risk.
