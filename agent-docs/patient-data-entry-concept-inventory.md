# Patient Data Entry Concept Inventory

**Date:** 2026-07-29  
**Phase:** PD0 baseline inventory  
**Runtime behavior changed by this document:** None

## 1. Purpose

Record every patient fact concept currently produced by checked-in seeds,
recognized deterministically from pasted text, or exercised by the screening
domain tests. This inventory is the input to the backend-owned catalog planned
for PD3.

## 2. Seed inventory

### Bounded demo workspace

| Fact type | Concepts |
|---|---|
| Condition | `type1_diabetes`, `type2_diabetes`, `pregnancy` |
| Observation | `hba1c`, `egfr` |

### Controlled admin workspace

| Fact type | Concepts |
|---|---|
| Condition | `type2_diabetes`, `hypertension`, `pregnancy` |
| Medication | `metformin`, `atorvastatin` |
| Observation | `hba1c`, `fasting_glucose`, `egfr`, `creatinine`, `alt`, `ast`, `hemoglobin`, `wbc`, `platelets`, `ldl`, `triglycerides`, `bmi`, `systolic_bp`, `diastolic_bp`, `potassium`, `albumin` |

All checked-in seed concepts are covered by the initial catalog declared in the
overhaul plan.

## 3. Deterministic pasted-text inventory

The current parser recognizes these numeric observation labels:

- `HbA1c`;
- `eGFR`;
- `BMI`;
- `creatinine`.

It also accepts unrestricted text after `condition:`, `diagnosis:`, and
`medication:`. Consequently, an imported candidate is not guaranteed to map to
the controlled catalog.

PD6 must:

1. normalize recognized observation labels to canonical lowercase concepts;
2. map known condition and medication synonyms to catalog keys;
3. retain the immutable source span;
4. mark unsupported concepts for human review;
5. prevent an unsupported candidate from silently becoming screening evidence.

PD6 completion: the import review now normalizes observation labels and matches
fact-type/concept/display-label aliases against the active database catalog. It
adds visible warnings for unmatched, incomplete, or unit-incompatible
candidates; approval writes canonical facts only when the catalog contract is
complete and otherwise creates a review-only unsupported detail while retaining
the source span.

PDF extraction is not otherwise redesigned by this patient-entry overhaul.

## 4. Screening-domain and API-test inventory

Concepts exercised outside the seeds include:

| Fact type | Concepts |
|---|---|
| Condition | `asthma` |
| Medication | `insulin`, `semaglutide` |

These concepts are included in the initial catalog so characterization and
screening tests do not depend on an unsupported manual-entry value.

Demographic rules currently consume:

- `demographic.age`, derived from date of birth at the explicit screening date;
- `demographic.sex`, derived from the patient profile and normalized by the
  screening adapter.

## 5. Unit inventory

| Concept | Canonical unit |
|---|---|
| `hba1c` | `%` |
| `fasting_glucose` | `mg/dL` |
| `egfr` | `mL/min/1.73m2` |
| `creatinine` | `mg/dL` |
| `alt` | `U/L` |
| `ast` | `U/L` |
| `hemoglobin` | `g/dL` |
| `wbc` | `10^9/L` |
| `platelets` | `10^9/L` |
| `ldl` | `mg/dL` |
| `triglycerides` | `mg/dL` |
| `bmi` | `kg/m2` |
| `systolic_bp` | `mmHg` |
| `diastolic_bp` | `mmHg` |
| `potassium` | `mmol/L` |
| `albumin` | `g/dL` |

PD3 must make these units catalog-owned rather than user-entered.

## 6. Legacy biological-sex inventory and migration contract

Checked-in seeds currently contain `Female`, `Male`, and `null`. The current API
also permits any string up to 32 characters.

PD2 migration rules:

1. trim and case-normalize recognized `male` and `female` values;
2. retain `null` as **Not recorded**;
3. run a preflight query for every other non-null value;
4. abort with a clear count if unsupported values exist;
5. never coerce an unsupported value into male, female, or null;
6. add the database constraint only after preflight succeeds.

PD2 downgrade rules:

- remove the database constraint or enum restriction;
- keep already-normalized lowercase values unchanged;
- do not rewrite immutable screening snapshots;
- keep the screening adapter case-normalization during the bounded transition.

PD0 adds no migration and changes no stored values.

## 7. Reserved error and warning codes

The executable contract reserves:

- `PATIENT_SEX_INVALID`;
- `PATIENT_DOB_IN_FUTURE`;
- `PATIENT_PREGNANCY_SEX_CONFLICT`;
- `PATIENT_FACT_DUPLICATE`;
- `PATIENT_FACT_CONFLICT`;
- `PATIENT_FACT_UNSUPPORTED`;
- `PATIENT_FACT_VALUE_INVALID`;
- `PATIENT_RECORD_STALE`;
- `PATIENT_FACT_REMOVAL_REASON_REQUIRED`;
- `PATIENT_FACT_ALREADY_REMOVED`;
- `PATIENT_FACT_RESTORE_CONFLICT`;
- `PATIENT_SEX_NOT_RECORDED_FOR_PREGNANCY` as a warning.

Later PD phases must use these identifiers instead of inventing page-specific
error strings.
