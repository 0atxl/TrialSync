# XGBoost-06 Cross-Clone Handoff

**Recorded:** 2026-08-28
**Remediation workspace:** `/home/rinzler/nothing/TrialSync`
**Stable integration workspace:** `/home/rinzler/Projects/TrialSync`

## Purpose

The temporary clone under `/home/rinzler/nothing/TrialSync` contains an uncommitted XGBoost-06,
Docker, pagination, baseline-editing, and Cohort Atlas implementation produced during a separate
research session. That clone is the only workspace in which the remediation should be performed.

The stable workspace must remain the integration destination. Once the temporary clone passes all
required checks, its source commits will be pushed and pulled into the stable workspace. Generated
artifacts, environment configuration, and database contents require separate handling because Git
does not transfer them.

## Verified XGBoost-06 bundle

The source bundle is retained at:

`/home/rinzler/Downloads/trialsync_v2_bundle.zip`

The bundle was compared directly with the package mounted by the healthy production Compose stack
on 2026-08-28. The deployed model and feature schema match the ZIP exactly.

| Item | SHA-256 |
| --- | --- |
| Source ZIP | `155a0549ddf92277f9ade0daa67934d4eddf59c3696d37f8ec3daf1f121c89f0` |
| XGBoost pipeline | `81cd6cd0836f3d6735ecc4173c88da6bf7c6f1fadda8fc827e2056e92ad9cb15` |
| Feature schema | `e49a3276ee50c9e86e595a72ab6fd1a9de6ced9b3067881caa74c68fdd4a7b13` |
| Synthetic day-30 dataset | `a2eb65e5a0396553366808dbc1bcd93f86dfe5f282bac0c522e762c3d961ba3d` |

The accepted package identity is:

- model ID: `dropout-xgboost-06-v1`;
- candidate ID: `xgboost-06`;
- feature schema: `r4-day30-features-v2`;
- threshold: `0.445`;
- prediction horizon: day 90.

The recorded held-out results—AUROC `0.88735`, AUPRC `0.74440`, Brier score `0.11818`, and F1
`0.68657`—describe only the controlled synthetic task. They are not evidence of clinical calibration
or real-world validity. The model must not be retrained during the integration work.

## Workspace responsibilities

### Temporary remediation clone

Use `/home/rinzler/nothing/TrialSync` only to:

1. preserve the existing modified and untracked work;
2. repair snapshot immutability and prediction integrity;
3. align runtime storage with the v2 feature contract;
4. stop inventing missed-dose and missed-visit streaks;
5. replace the silent metabolic fallback for unsupported conditions;
6. simplify and test the enrollment-update API contract;
7. update focused tests and clear Ruff and mypy;
8. perform frontend and backend verification;
9. produce clean, reviewable source commits and push them.

Do not use that session for subsequent research-extension features. Its scope ends when the audited
implementation is corrected, verified, documented, and pushed.

### Stable integration clone

Use `/home/rinzler/Projects/TrialSync` after remediation to:

1. pull the verified source commits;
2. restore the ignored runtime artifacts and active configuration;
3. deliberately reuse or recreate development database state;
4. repeat the verification suite in the final workspace;
5. continue the remaining research-extension roadmap.

## Required remediation outcome

The temporary clone must not be integrated until all of the following are true:

- historical research follow-up snapshots and predictions remain append-only;
- every prediction references the exact unchanged feature snapshot used for inference;
- a database integrity query reports zero prediction/follow-up hash mismatches;
- enrollment and follow-up rows use `r4-day30-features-v2` when they contain v2 features;
- consecutive missed-event streaks are explicitly supplied or validly derived, never guessed from
  aggregate totals;
- unsupported condition categories are reported transparently instead of becoming `metabolic`;
- deterministic eligibility remains unchanged;
- focused and relevant backend tests pass;
- frontend tests, lint, typecheck, and production build pass;
- Ruff and strict mypy pass;
- Compose configuration and direct XGBoost-06 inference checks pass;
- desktop visual QA covers screening detail, dropout prediction, dropout worklist, and Cohort Atlas.

## Git and artifact transfer procedure

1. Commit and push only reviewed source, tests, migrations, and accurate documentation from the
   remediation clone.
2. Do not commit `trialsync_v2_bundle.zip`, generated datasets, fitted model artifacts,
   `.env.production`, credentials, or database volumes.
3. Pull the source commits into the stable clone without overwriting unrelated local work.
4. Restore the complete packaged directory—not only the raw model file—at:

   `artifacts/r5/dropout-xgboost-06-v1/`

   It must contain the packaged `model.joblib`, `feature_schema.json`, and `manifest.json` whose
   checksums agree with this document.
5. Preserve or separately restore the accepted R6 artifact run:

   `r6-v3-6091f06c-542d-5b00-8bdc-6fbd782c9510`
6. Reapply the active R5 model and R6 run through the stable clone's local environment file. Do not
   overwrite unrelated environment values.
7. Database contents do not move through Git. Decide explicitly whether to reuse the existing
   Compose volume or recreate development data, then run migrations and integrity checks.
8. Run the complete verification suite again from the stable clone before continuing feature work.

## Preservation rules

- Keep `/home/rinzler/Downloads/trialsync_v2_bundle.zip` unchanged as the verified source bundle.
- Do not run `git clean`, destructive resets, or broad artifact deletion in either clone.
- Do not copy the temporary clone over the stable clone directory.
- Do not treat a healthy container or passing frontend suite as proof that research history is
  internally consistent.
- Update this handoff if the final artifact identity, migration strategy, or transfer procedure
  changes during remediation.
