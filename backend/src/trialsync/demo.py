from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from trialsync.config import Settings, get_settings
from trialsync.db.models import (
    Assertion,
    Criterion,
    CriterionEvaluation,
    CriterionKind,
    FactType,
    OverallState,
    Patient,
    PatientFact,
    Screening,
    ScreeningBatch,
    ScreeningChatMessage,
    Trial,
    TrialVersion,
    User,
    VersionStatus,
)
from trialsync.db.session import get_session_factory
from trialsync.screening.service import run_and_store, snapshot_for_patient
from trialsync.security import hash_password

DEMO_EMAIL = "demo@trialsync.example"
DEMO_PASSWORD = "SyntheticDemo123!"
E2E_EMAIL = "phase8-browser@trialsync.example"
ADMIN_EMAIL = "admin@trialsync.example"
ADMIN_PASSWORD = "AdminWorkspace2026!"
DEMO_SCREENING_DATE = date(2026, 7, 16)


@dataclass(frozen=True)
class DemoSeedSummary:
    email: str
    patients: int
    trials: int
    screenings: int
    batches: int
    chat_messages: int


@dataclass(frozen=True)
class AdminWorkspaceSummary:
    email: str
    patients: int
    trials: int
    criteria: int
    screenings: int
    potentially_eligible: int
    likely_ineligible: int
    needs_review: int


def _id(name: str, *, namespace: str | None = None) -> uuid.UUID:
    prefix = f"{namespace}/" if namespace else ""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://trialsync.local/demo/{prefix}{name}")


def _fact(
    patient: Patient,
    name: str,
    fact_type: FactType,
    concept: str,
    *,
    numeric: str | None = None,
    unit: str | None = None,
    assertion: Assertion = Assertion.present,
    effective_date: date | None = None,
    source_label: str = "Synthetic Phase 8 demo fixture",
    namespace: str | None = None,
) -> PatientFact:
    return PatientFact(
        id=_id(f"fact/{name}", namespace=namespace),
        patient_id=patient.id,
        fact_type=fact_type,
        concept=concept,
        value_numeric=Decimal(numeric) if numeric is not None else None,
        unit=unit,
        assertion=assertion,
        effective_date=effective_date,
        source_label=source_label,
    )


def _patients(owner_id: uuid.UUID, *, namespace: str | None = None) -> list[Patient]:
    records = [
        Patient(
            id=_id("patient/eligible", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-001",
            display_name="Synthetic Ada Mercer",
            date_of_birth=date(1980, 1, 15),
            sex="female",
        ),
        Patient(
            id=_id("patient/inclusion-fail", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-002",
            display_name="Synthetic Ben Carter",
            date_of_birth=date(2012, 3, 10),
            sex="male",
        ),
        Patient(
            id=_id("patient/exclusion-fail", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-003",
            display_name="Synthetic Cora Bennett",
            date_of_birth=date(1988, 9, 22),
            sex="female",
        ),
        Patient(
            id=_id("patient/needs-review", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-004",
            display_name="Synthetic Dev Malik",
            date_of_birth=None,
            sex=None,
        ),
        Patient(
            id=_id("patient/type1", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-005",
            display_name="Synthetic Emi Tanaka",
            date_of_birth=date(1994, 11, 5),
            sex="female",
        ),
        Patient(
            id=_id("patient/boundary", namespace=namespace),
            owner_id=owner_id,
            external_id="SYN-P8-006",
            display_name="Synthetic Finn Osei",
            date_of_birth=date(2008, 7, 16),
            sex="male",
        ),
    ]
    recent = DEMO_SCREENING_DATE - timedelta(days=7)
    for patient in records:
        suffix = patient.external_id.lower()
        patient.facts.extend(
            [
                _fact(
                    patient,
                    f"{suffix}/hba1c",
                    FactType.observation,
                    "hba1c",
                    numeric="7.6",
                    unit="%",
                    effective_date=recent,
                    namespace=namespace,
                ),
                _fact(
                    patient,
                    f"{suffix}/pregnancy",
                    FactType.condition,
                    "pregnancy",
                    assertion=Assertion.absent,
                    namespace=namespace,
                ),
                _fact(
                    patient,
                    f"{suffix}/egfr",
                    FactType.observation,
                    "egfr",
                    numeric="72",
                    unit="mL/min/1.73m2",
                    effective_date=recent,
                    namespace=namespace,
                ),
            ]
        )
        patient.facts.append(
            _fact(
                patient,
                f"{suffix}/type2",
                FactType.condition,
                "type2_diabetes",
                namespace=namespace,
            )
        )

    records[2].facts = [
        fact
        for fact in records[2].facts
        if not (fact.fact_type is FactType.condition and fact.concept == "pregnancy")
    ]
    records[2].facts.append(
        _fact(
            records[2],
            "syn-p8-003/pregnancy-trigger",
            FactType.condition,
            "pregnancy",
            namespace=namespace,
        )
    )
    records[4].facts = [
        fact
        for fact in records[4].facts
        if not (fact.fact_type is FactType.condition and fact.concept == "type2_diabetes")
    ]
    records[4].facts.extend(
        [
            _fact(
                records[4],
                "syn-p8-005/type1",
                FactType.condition,
                "type1_diabetes",
                namespace=namespace,
            ),
            _fact(
                records[4],
                "syn-p8-005/egfr-trigger",
                FactType.observation,
                "egfr",
                numeric="28",
                unit="mL/min/1.73m2",
                effective_date=recent,
                namespace=namespace,
            ),
        ]
    )
    return records


def _admin_patients(owner_id: uuid.UUID) -> list[Patient]:
    names = [
        "Avery Brooks",
        "Jordan Chen",
        "Morgan Diaz",
        "Riley Evans",
        "Cameron Foster",
        "Taylor Grant",
        "Casey Hall",
        "Quinn Irving",
        "Parker James",
        "Rowan Kelly",
        "Reese Lawson",
        "Hayden Moore",
        "Skyler Nguyen",
        "Peyton Ortiz",
        "Devin Patel",
        "Blair Quinn",
        "Kendall Ross",
        "Drew Shah",
        "Emery Turner",
        "Logan Vega",
    ]
    records: list[Patient] = []
    for index, name in enumerate(names, 1):
        cohort = (
            "potentially_eligible"
            if index <= 8
            else "likely_ineligible"
            if index <= 16
            else "needs_review"
        )
        patient = Patient(
            id=_id(f"admin/patient/{index}"),
            owner_id=owner_id,
            external_id=f"ADM-P-{index:03d}",
            display_name=name,
            date_of_birth=(
                None
                if cohort == "needs_review"
                else date(2012, (index % 12) + 1, (index % 27) + 1)
                if cohort == "likely_ineligible"
                else date(1971 + (index % 31), (index % 12) + 1, (index % 27) + 1)
            ),
            sex="female" if index % 2 else "male",
        )
        label = "Controlled workspace entry"
        observed = DEMO_SCREENING_DATE - timedelta(days=(index % 20) + 1)
        measurements = [
            ("hba1c", f"{7.2 + (index % 7) * 0.3:.1f}", "%"),
            ("fasting_glucose", str(108 + index * 3), "mg/dL"),
            ("egfr", str(58 + (index % 9) * 5), "mL/min/1.73m2"),
            ("creatinine", f"{0.7 + (index % 6) * 0.1:.1f}", "mg/dL"),
            ("alt", str(19 + (index % 8) * 4), "U/L"),
            ("ast", str(18 + (index % 7) * 3), "U/L"),
            ("hemoglobin", f"{12.1 + (index % 6) * 0.4:.1f}", "g/dL"),
            ("wbc", f"{4.8 + (index % 8) * 0.4:.1f}", "10^9/L"),
            ("platelets", str(185 + index * 5), "10^9/L"),
            ("ldl", str(74 + (index % 10) * 7), "mg/dL"),
            ("triglycerides", str(96 + (index % 9) * 11), "mg/dL"),
            ("bmi", f"{23.0 + (index % 10) * 1.2:.1f}", "kg/m2"),
            ("systolic_bp", str(112 + (index % 11) * 3), "mmHg"),
            ("diastolic_bp", str(68 + (index % 7) * 2), "mmHg"),
            ("potassium", f"{3.8 + (index % 5) * 0.2:.1f}", "mmol/L"),
            ("albumin", f"{3.9 + (index % 5) * 0.1:.1f}", "g/dL"),
        ]
        assertion_by_concept: dict[str, Assertion] = {}
        if cohort == "likely_ineligible":
            measurements = [
                ("hba1c", "5.4", "%"),
                ("fasting_glucose", "92", "mg/dL"),
                ("egfr", "24", "mL/min/1.73m2"),
                ("creatinine", "2.4", "mg/dL"),
                ("alt", "138", "U/L"),
                ("ast", "96", "U/L"),
                ("hemoglobin", "9.4", "g/dL"),
                ("wbc", "6.2", "10^9/L"),
                ("platelets", "218", "10^9/L"),
                ("ldl", "118", "mg/dL"),
                ("triglycerides", "184", "mg/dL"),
                ("bmi", "18.4", "kg/m2"),
                ("systolic_bp", "144", "mmHg"),
                ("diastolic_bp", "88", "mmHg"),
                ("potassium", "3.0", "mmol/L"),
                ("albumin", "3.4", "g/dL"),
            ]
        elif cohort == "needs_review":
            assertion_by_concept = {
                "hba1c": Assertion.unknown,
                "egfr": Assertion.unknown,
                "bmi": Assertion.unknown,
            }
        patient.facts.extend(
            [
                _fact(
                    patient,
                    f"admin-{index}/type2",
                    FactType.condition,
                    "type2_diabetes",
                    assertion=(
                        Assertion.absent
                        if cohort == "likely_ineligible"
                        else Assertion.unknown
                        if cohort == "needs_review"
                        else Assertion.present
                    ),
                    source_label=label,
                ),
                _fact(
                    patient,
                    f"admin-{index}/hypertension",
                    FactType.condition,
                    "hypertension",
                    source_label=label,
                ),
                _fact(
                    patient,
                    f"admin-{index}/pregnancy",
                    FactType.condition,
                    "pregnancy",
                    assertion=Assertion.absent,
                    source_label=label,
                ),
                _fact(
                    patient,
                    f"admin-{index}/metformin",
                    FactType.medication,
                    "metformin",
                    source_label=label,
                ),
                _fact(
                    patient,
                    f"admin-{index}/atorvastatin",
                    FactType.medication,
                    "atorvastatin",
                    source_label=label,
                ),
            ]
        )
        patient.facts.extend(
            _fact(
                patient,
                f"admin-{index}/{concept}",
                FactType.observation,
                concept,
                numeric=value,
                unit=unit,
                assertion=assertion_by_concept.get(concept, Assertion.present),
                effective_date=observed,
                source_label=label,
            )
            for concept, value, unit in measurements
        )
        records.append(patient)
    return records


def _admin_trials(owner_id: uuid.UUID) -> list[Trial]:
    protocols = [
        ("Metabolic Outcomes", "Type 2 diabetes", "Phase 2"),
        ("Glycemic Control", "Type 2 diabetes", "Phase 3"),
        ("Renal Protection", "Chronic kidney disease", "Phase 3"),
        ("Cardiometabolic Risk", "Type 2 diabetes", "Phase 2"),
        ("Lipid Management", "Dyslipidemia", "Phase 2"),
        ("Blood Pressure Control", "Hypertension", "Phase 3"),
        ("Hepatic Safety", "Metabolic disease", "Phase 2"),
        ("Longitudinal Diabetes", "Type 2 diabetes", "Phase 4"),
        ("Renal Function", "Chronic kidney disease", "Phase 2"),
        ("Cardiovascular Prevention", "Type 2 diabetes", "Phase 3"),
        ("Glucose Monitoring", "Type 2 diabetes", "Phase 2"),
        ("Metabolic Health", "Metabolic disease", "Phase 3"),
        ("Clinical Chemistry", "Type 2 diabetes", "Phase 2"),
        ("Treatment Continuation", "Type 2 diabetes", "Phase 4"),
        ("Outcomes Registry", "Type 2 diabetes", "Phase 3"),
    ]
    trials: list[Trial] = []
    for index, (title, condition, phase) in enumerate(protocols, 1):
        trial = Trial(
            id=_id(f"admin/trial/{index}"),
            owner_id=owner_id,
            registry_id=f"ADM-T-{index:03d}",
            title=f"{title} Protocol {index:02d}",
            condition=condition,
            phase=phase,
        )
        version = TrialVersion(
            id=_id(f"admin/trial-version/{index}/1"),
            trial=trial,
            version=1,
            status=VersionStatus.approved,
            source_text=f"Controlled protocol record {index:02d}.",
        )
        minimum_hba1c = 6.5 + (index % 3) * 0.2
        maximum_hba1c = 9.8 + (index % 2) * 0.2
        minimum_egfr = 40 + (index % 3) * 5
        criteria = [
            (
                CriterionKind.inclusion,
                "Age 18 to 75 years at screening",
                {"op": "between", "fact": "demographic.age", "min": 18, "max": 75, "unit": "year"},
            ),
            (
                CriterionKind.inclusion,
                "Documented Type 2 diabetes",
                {"op": "present", "fact": "condition.type2_diabetes"},
            ),
            (
                CriterionKind.inclusion,
                f"HbA1c between {minimum_hba1c:.1f}% and {maximum_hba1c:.1f}%",
                {
                    "op": "between",
                    "fact": "observation.hba1c",
                    "min": minimum_hba1c,
                    "max": maximum_hba1c,
                    "unit": "%",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.inclusion,
                f"eGFR at least {minimum_egfr} mL/min/1.73m2",
                {
                    "op": "gte",
                    "fact": "observation.egfr",
                    "value": minimum_egfr,
                    "unit": "mL/min/1.73m2",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.inclusion,
                "Body mass index between 20 and 45 kg/m2",
                {
                    "op": "between",
                    "fact": "observation.bmi",
                    "min": 20,
                    "max": 45,
                    "unit": "kg/m2",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.exclusion,
                "Current pregnancy",
                {"op": "present", "fact": "condition.pregnancy"},
            ),
            (
                CriterionKind.exclusion,
                "eGFR below 30 mL/min/1.73m2",
                {
                    "op": "lt",
                    "fact": "observation.egfr",
                    "value": 30,
                    "unit": "mL/min/1.73m2",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.exclusion,
                "ALT above 120 U/L",
                {
                    "op": "gt",
                    "fact": "observation.alt",
                    "value": 120,
                    "unit": "U/L",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.exclusion,
                "Hemoglobin below 10 g/dL",
                {
                    "op": "lt",
                    "fact": "observation.hemoglobin",
                    "value": 10,
                    "unit": "g/dL",
                    "selection": "latest",
                },
            ),
            (
                CriterionKind.exclusion,
                "Potassium below 3.2 mmol/L",
                {
                    "op": "lt",
                    "fact": "observation.potassium",
                    "value": 3.2,
                    "unit": "mmol/L",
                    "selection": "latest",
                },
            ),
        ]
        version.criteria.extend(
            Criterion(
                id=_id(f"admin/criterion/{index}/{order}"),
                trial_version_id=version.id,
                kind=kind,
                order=order,
                source_text=source_text,
                normalized_rule=rule,
                required=True,
            )
            for order, (kind, source_text, rule) in enumerate(criteria, 1)
        )
        trials.append(trial)
    return trials


def _trials(owner_id: uuid.UUID, *, namespace: str | None = None) -> list[Trial]:
    metabolic = Trial(
        id=_id("trial/metabolic", namespace=namespace),
        owner_id=owner_id,
        registry_id="SYN-P8-METABOLIC",
        title="Synthetic metabolic eligibility study",
        condition="Synthetic metabolic condition",
        phase="Phase 2",
    )
    metabolic_version = TrialVersion(
        id=_id("trial-version/metabolic/1", namespace=namespace),
        trial=metabolic,
        version=1,
        status=VersionStatus.approved,
        source_text="Synthetic protocol used only for the Phase 8 demonstration.",
    )
    metabolic_version.criteria.extend(
        [
            Criterion(
                id=_id("criterion/metabolic/age", namespace=namespace),
                trial_version_id=metabolic_version.id,
                kind=CriterionKind.inclusion,
                order=1,
                source_text="Age 18 to 75 years at screening",
                normalized_rule={
                    "op": "between",
                    "fact": "demographic.age",
                    "min": 18,
                    "max": 75,
                    "unit": "year",
                },
                required=True,
            ),
            Criterion(
                id=_id("criterion/metabolic/type2", namespace=namespace),
                trial_version_id=metabolic_version.id,
                kind=CriterionKind.inclusion,
                order=2,
                source_text="Documented Type 2 diabetes",
                normalized_rule={"op": "present", "fact": "condition.type2_diabetes"},
                required=True,
            ),
            Criterion(
                id=_id("criterion/metabolic/hba1c", namespace=namespace),
                trial_version_id=metabolic_version.id,
                kind=CriterionKind.inclusion,
                order=3,
                source_text="HbA1c between 7.0% and 10.0%",
                normalized_rule={
                    "op": "between",
                    "fact": "observation.hba1c",
                    "min": 7.0,
                    "max": 10.0,
                    "unit": "%",
                    "selection": "latest",
                },
                required=True,
            ),
            Criterion(
                id=_id("criterion/metabolic/pregnancy", namespace=namespace),
                trial_version_id=metabolic_version.id,
                kind=CriterionKind.exclusion,
                order=4,
                source_text="Current pregnancy",
                normalized_rule={"op": "present", "fact": "condition.pregnancy"},
                required=True,
            ),
        ]
    )

    renal = Trial(
        id=_id("trial/renal", namespace=namespace),
        owner_id=owner_id,
        registry_id="SYN-P8-RENAL",
        title="Synthetic renal safety study",
        condition="Synthetic renal monitoring condition",
        phase="Phase 3",
    )
    renal_version = TrialVersion(
        id=_id("trial-version/renal/1", namespace=namespace),
        trial=renal,
        version=1,
        status=VersionStatus.approved,
        source_text="Synthetic protocol used only for the Phase 8 demonstration.",
    )
    renal_version.criteria.extend(
        [
            Criterion(
                id=_id("criterion/renal/age", namespace=namespace),
                trial_version_id=renal_version.id,
                kind=CriterionKind.inclusion,
                order=1,
                source_text="Age 21 to 68 years at screening",
                normalized_rule={
                    "op": "between",
                    "fact": "demographic.age",
                    "min": 21,
                    "max": 68,
                    "unit": "year",
                },
                required=True,
            ),
            Criterion(
                id=_id("criterion/renal/egfr", namespace=namespace),
                trial_version_id=renal_version.id,
                kind=CriterionKind.exclusion,
                order=2,
                source_text="eGFR below 30 mL/min/1.73m2 within 30 days",
                normalized_rule={
                    "op": "within_before",
                    "days": 30,
                    "arg": {
                        "op": "lt",
                        "fact": "observation.egfr",
                        "value": 30,
                        "unit": "mL/min/1.73m2",
                        "selection": "latest",
                    },
                },
                required=True,
            ),
        ]
    )
    return [metabolic, renal]


async def reset_demo_data(session: AsyncSession, email: str = DEMO_EMAIL) -> bool:
    existing = await session.scalar(select(User.id).where(User.email == email.lower()))
    if existing is None:
        return False
    await session.execute(delete(User).where(User.id == existing))
    await session.flush()
    return True


async def reset_non_demo_users(session: AsyncSession) -> None:
    """Remove every local account except the fixed demo workspace."""
    await session.execute(delete(User).where(User.email != DEMO_EMAIL))
    await session.flush()


async def seed_demo_data(
    session: AsyncSession,
    *,
    email: str = DEMO_EMAIL,
    password: str = DEMO_PASSWORD,
    namespace: str | None = None,
) -> DemoSeedSummary:
    """Replace one account with the reproducible synthetic demo workspace."""
    await reset_demo_data(session, email)
    id_namespace = namespace or (None if email.lower() == DEMO_EMAIL else email.lower())
    user = User(
        id=_id("user/phase8-demo", namespace=id_namespace),
        email=email.lower(),
        display_name="Demo Coordinator",
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.flush()
    patients = _patients(user.id, namespace=id_namespace)
    trials = _trials(user.id, namespace=id_namespace)
    session.add_all([*patients, *trials])
    await session.flush()

    snapshots = [await snapshot_for_patient(session, patient) for patient in patients]
    batch = ScreeningBatch(
        id=_id("batch/mixed-matrix", namespace=id_namespace),
        owner_id=user.id,
        label="Phase 8 mixed-outcome matrix",
        pair_count=len(snapshots) * len(trials),
    )
    session.add(batch)
    await session.flush()

    screenings: list[Screening] = []
    for snapshot in snapshots:
        for trial in trials:
            screenings.append(
                await run_and_store(
                    session,
                    owner_id=user.id,
                    snapshot=snapshot,
                    version=trial.versions[0],
                    screening_date=DEMO_SCREENING_DATE,
                    batch=batch,
                )
            )
    await session.flush()

    needs_review = next(
        item
        for item in screenings
        if item.trial_version_id == trials[0].versions[0].id
        and item.patient_snapshot_id == snapshots[3].id
    )
    age_evaluation = await session.scalar(
        select(CriterionEvaluation)
        .where(CriterionEvaluation.screening_id == needs_review.id)
        .order_by(CriterionEvaluation.criterion_order)
    )
    if age_evaluation is None:
        raise RuntimeError("The seeded needs-review screening has no criterion evaluation.")
    started = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)
    messages = [
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="user",
            content="Why does this result need review?",
            created_at=started,
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="assistant",
            content=(
                "The age criterion is unresolved because the approved snapshot has no "
                "date of birth."
            ),
            answer_state="supported",
            citations_json=[
                {
                    "criterion_id": str(age_evaluation.criterion_id),
                    "evaluation_id": str(age_evaluation.id),
                    "evidence_ids": [],
                    "label": "Age is unresolved",
                }
            ],
            provider="canonical",
            model_id="deterministic-canonical-1",
            prompt_version="screening-chat-v1",
            created_at=started + timedelta(minutes=1),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="user",
            content="What information is missing?",
            created_at=started + timedelta(minutes=2),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="assistant",
            content="A date of birth is required to calculate age at the recorded screening date.",
            answer_state="supported",
            citations_json=[
                {
                    "criterion_id": str(age_evaluation.criterion_id),
                    "evaluation_id": str(age_evaluation.id),
                    "evidence_ids": [],
                    "label": "Date of birth is missing",
                }
            ],
            provider="canonical",
            model_id="deterministic-canonical-1",
            prompt_version="screening-chat-v1",
            created_at=started + timedelta(minutes=3),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="user",
            content="Should this participant enroll?",
            created_at=started + timedelta(minutes=4),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="assistant",
            content=(
                "I cannot recommend enrollment. TrialSync only explains the stored "
                "educational pre-screening result."
            ),
            answer_state="refused",
            citations_json=[],
            provider="canonical",
            model_id="deterministic-canonical-1",
            prompt_version="screening-chat-v1",
            created_at=started + timedelta(minutes=5),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="user",
            content="What is the participant's preferred meal?",
            created_at=started + timedelta(minutes=6),
        ),
        ScreeningChatMessage(
            screening_id=needs_review.id,
            role="assistant",
            content=(
                "The screening record does not contain enough information to answer that question."
            ),
            answer_state="insufficient_evidence",
            citations_json=[],
            provider="canonical",
            model_id="deterministic-canonical-1",
            prompt_version="screening-chat-v1",
            created_at=started + timedelta(minutes=7),
        ),
    ]
    session.add_all(messages)
    await session.flush()
    return DemoSeedSummary(
        email=user.email,
        patients=len(patients),
        trials=len(trials),
        screenings=len(screenings),
        batches=1,
        chat_messages=len(messages),
    )


async def seed_admin_workspace(session: AsyncSession) -> AdminWorkspaceSummary:
    """Replace all non-demo users with the controlled admin workspace."""
    await reset_non_demo_users(session)
    demo_id = await session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
    if demo_id is None:
        await seed_demo_data(session)

    admin = User(
        id=_id("user/admin-workspace"),
        email=ADMIN_EMAIL,
        display_name="Admin Research Coordinator",
        password_hash=hash_password(ADMIN_PASSWORD),
        is_catalog_admin=True,
    )
    session.add(admin)
    await session.flush()
    patients = _admin_patients(admin.id)
    trials = _admin_trials(admin.id)
    session.add_all([*patients, *trials])
    await session.flush()
    snapshots = [await snapshot_for_patient(session, patient) for patient in patients]
    batch = ScreeningBatch(
        id=_id("admin/batch/complete-matrix"),
        owner_id=admin.id,
        label="Complete controlled screening matrix",
        pair_count=len(snapshots) * len(trials),
    )
    session.add(batch)
    await session.flush()
    screenings: list[Screening] = []
    for snapshot in snapshots:
        for trial in trials:
            screenings.append(
                await run_and_store(
                    session,
                    owner_id=admin.id,
                    snapshot=snapshot,
                    version=trial.versions[0],
                    screening_date=DEMO_SCREENING_DATE,
                    batch=batch,
                )
            )
    await session.flush()
    state_counts = {
        state: sum(item.overall_state is state for item in screenings) for state in OverallState
    }
    if state_counts != {
        OverallState.potentially_eligible: 120,
        OverallState.likely_ineligible: 120,
        OverallState.needs_review: 60,
    }:
        raise RuntimeError(
            f"Admin workspace did not produce the expected distribution: {state_counts}"
        )
    return AdminWorkspaceSummary(
        email=admin.email,
        patients=len(patients),
        trials=len(trials),
        criteria=sum(len(trial.versions[0].criteria) for trial in trials),
        screenings=len(screenings),
        potentially_eligible=state_counts[OverallState.potentially_eligible],
        likely_ineligible=state_counts[OverallState.likely_ineligible],
        needs_review=state_counts[OverallState.needs_review],
    )


async def prepare_e2e_data(session: AsyncSession) -> DemoSeedSummary:
    """Restore the fixed demo and remove the fixed browser-registration account."""
    await reset_demo_data(session, E2E_EMAIL)
    return await seed_demo_data(session)


def build_text_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = ["BT /F1 11 Tf 72 720 Td 14 TL"]
    for index, line in enumerate(escaped.splitlines()):
        commands.append(f"({line}) Tj" if index == 0 else f"T* ({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(content)


def write_pdf_fixture(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        build_text_pdf(
            "Patient name: Synthetic PDF Rowan\n"
            "Date of birth: 1986-04-18\n"
            "Sex: Female\n"
            "Condition: type2_diabetes\n"
            "HbA1c: 7.8 %"
        )
    )


def _require_nonproduction(settings: Settings) -> None:
    if settings.environment == "production":
        raise SystemExit("Demo seed/reset commands are disabled in production.")


async def _run_database_command(args: argparse.Namespace) -> None:
    settings = get_settings()
    _require_nonproduction(settings)
    async with get_session_factory()() as session, session.begin():
        if args.command == "seed":
            summary = await seed_demo_data(session)
            print(
                f"Seeded {summary.patients} patients, {summary.trials} trials, "
                f"{summary.screenings} screenings, and {summary.chat_messages} chat messages "
                f"for {summary.email}."
            )
        elif args.command == "reset":
            removed = await reset_demo_data(session)
            print(
                "Removed the Phase 8 demo account."
                if removed
                else "No Phase 8 demo account existed."
            )
        elif args.command == "prepare-e2e":
            summary = await prepare_e2e_data(session)
            print(
                f"Restored {summary.screenings} seeded screenings and removed any "
                "fixed browser-test account."
            )
        elif args.command == "seed-admin":
            admin_summary = await seed_admin_workspace(session)
            print(
                f"Created {admin_summary.patients} patient records, "
                f"{admin_summary.trials} approved trials, and "
                f"{admin_summary.criteria} criteria for {admin_summary.email}. "
                f"Saved {admin_summary.screenings} screenings: "
                f"{admin_summary.potentially_eligible} potentially eligible, "
                f"{admin_summary.likely_ineligible} likely ineligible, and "
                f"{admin_summary.needs_review} needs review."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage reproducible synthetic TrialSync demo data."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed", help="Replace and seed the bounded Phase 8 demo account.")
    reset = subparsers.add_parser(
        "reset", help="Remove only the Phase 8 demo account and its owned data."
    )
    reset.add_argument("--yes", action="store_true", help="Confirm deletion of the demo account.")
    subparsers.add_parser(
        "prepare-e2e", help="Restore the demo and remove the fixed browser-test account."
    )
    subparsers.add_parser(
        "seed-admin",
        help="Keep only the demo account, then create the controlled admin workspace.",
    )
    fixture = subparsers.add_parser(
        "write-pdf-fixture", help="Write a generated synthetic text PDF."
    )
    fixture.add_argument(
        "--output", type=Path, default=Path("/tmp/trialsync-synthetic-patient.pdf")
    )
    args = parser.parse_args()
    if args.command == "reset" and not args.yes:
        parser.error("reset requires --yes")
    if args.command == "write-pdf-fixture":
        write_pdf_fixture(args.output)
        print(f"Wrote synthetic PDF fixture to {args.output}.")
        return
    asyncio.run(_run_database_command(args))


if __name__ == "__main__":
    main()
