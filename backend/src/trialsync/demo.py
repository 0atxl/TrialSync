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
DEMO_SCREENING_DATE = date(2026, 7, 16)


@dataclass(frozen=True)
class DemoSeedSummary:
    email: str
    patients: int
    trials: int
    screenings: int
    batches: int
    chat_messages: int


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://trialsync.local/demo/{name}")


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
) -> PatientFact:
    return PatientFact(
        id=_id(f"fact/{name}"),
        patient_id=patient.id,
        fact_type=fact_type,
        concept=concept,
        value_numeric=Decimal(numeric) if numeric is not None else None,
        unit=unit,
        assertion=assertion,
        effective_date=effective_date,
        source_label="Synthetic Phase 8 demo fixture",
    )


def _patients(owner_id: uuid.UUID) -> list[Patient]:
    records = [
        Patient(
            id=_id("patient/eligible"),
            owner_id=owner_id,
            external_id="SYN-P8-001",
            display_name="Synthetic Ada Eligible",
            date_of_birth=date(1980, 1, 15),
            sex="Female",
        ),
        Patient(
            id=_id("patient/inclusion-fail"),
            owner_id=owner_id,
            external_id="SYN-P8-002",
            display_name="Synthetic Ben Inclusion Fail",
            date_of_birth=date(2012, 3, 10),
            sex="Male",
        ),
        Patient(
            id=_id("patient/exclusion-fail"),
            owner_id=owner_id,
            external_id="SYN-P8-003",
            display_name="Synthetic Cora Exclusion Trigger",
            date_of_birth=date(1988, 9, 22),
            sex="Female",
        ),
        Patient(
            id=_id("patient/needs-review"),
            owner_id=owner_id,
            external_id="SYN-P8-004",
            display_name="Synthetic Dev Needs Review",
            date_of_birth=None,
            sex=None,
        ),
        Patient(
            id=_id("patient/type1"),
            owner_id=owner_id,
            external_id="SYN-P8-005",
            display_name="Synthetic Emi Type 1 Distinction",
            date_of_birth=date(1994, 11, 5),
            sex="Female",
        ),
        Patient(
            id=_id("patient/boundary"),
            owner_id=owner_id,
            external_id="SYN-P8-006",
            display_name="Synthetic Finn Age Boundary",
            date_of_birth=date(2008, 7, 16),
            sex="Male",
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
                ),
                _fact(
                    patient,
                    f"{suffix}/pregnancy",
                    FactType.condition,
                    "pregnancy",
                    assertion=Assertion.absent,
                ),
                _fact(
                    patient,
                    f"{suffix}/egfr",
                    FactType.observation,
                    "egfr",
                    numeric="72",
                    unit="mL/min/1.73m2",
                    effective_date=recent,
                ),
            ]
        )
        patient.facts.append(
            _fact(patient, f"{suffix}/type2", FactType.condition, "type2_diabetes")
        )

    records[2].facts = [
        fact
        for fact in records[2].facts
        if not (fact.fact_type is FactType.condition and fact.concept == "pregnancy")
    ]
    records[2].facts.append(
        _fact(records[2], "syn-p8-003/pregnancy-trigger", FactType.condition, "pregnancy")
    )
    records[4].facts = [
        fact
        for fact in records[4].facts
        if not (fact.fact_type is FactType.condition and fact.concept == "type2_diabetes")
    ]
    records[4].facts.extend(
        [
            _fact(records[4], "syn-p8-005/type1", FactType.condition, "type1_diabetes"),
            _fact(
                records[4],
                "syn-p8-005/egfr-trigger",
                FactType.observation,
                "egfr",
                numeric="28",
                unit="mL/min/1.73m2",
                effective_date=recent,
            ),
        ]
    )
    return records


def _trials(owner_id: uuid.UUID) -> list[Trial]:
    metabolic = Trial(
        id=_id("trial/metabolic"),
        owner_id=owner_id,
        registry_id="SYN-P8-METABOLIC",
        title="Synthetic metabolic eligibility study",
        condition="Synthetic metabolic condition",
        phase="Phase 2",
    )
    metabolic_version = TrialVersion(
        id=_id("trial-version/metabolic/1"),
        trial=metabolic,
        version=1,
        status=VersionStatus.approved,
        source_text="Synthetic protocol used only for the Phase 8 demonstration.",
    )
    metabolic_version.criteria.extend(
        [
            Criterion(
                id=_id("criterion/metabolic/age"),
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
                id=_id("criterion/metabolic/type2"),
                trial_version_id=metabolic_version.id,
                kind=CriterionKind.inclusion,
                order=2,
                source_text="Documented Type 2 diabetes",
                normalized_rule={"op": "present", "fact": "condition.type2_diabetes"},
                required=True,
            ),
            Criterion(
                id=_id("criterion/metabolic/hba1c"),
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
                id=_id("criterion/metabolic/pregnancy"),
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
        id=_id("trial/renal"),
        owner_id=owner_id,
        registry_id="SYN-P8-RENAL",
        title="Synthetic renal safety study",
        condition="Synthetic renal monitoring condition",
        phase="Phase 3",
    )
    renal_version = TrialVersion(
        id=_id("trial-version/renal/1"),
        trial=renal,
        version=1,
        status=VersionStatus.approved,
        source_text="Synthetic protocol used only for the Phase 8 demonstration.",
    )
    renal_version.criteria.extend(
        [
            Criterion(
                id=_id("criterion/renal/age"),
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
                id=_id("criterion/renal/egfr"),
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


async def seed_demo_data(
    session: AsyncSession,
    *,
    email: str = DEMO_EMAIL,
    password: str = DEMO_PASSWORD,
) -> DemoSeedSummary:
    await reset_demo_data(session, email)
    user = User(
        id=_id("user/phase8-demo"),
        email=email.lower(),
        display_name="Phase 8 Demo Coordinator",
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.flush()
    patients = _patients(user.id)
    trials = _trials(user.id)
    session.add_all([*patients, *trials])
    await session.flush()

    snapshots = [await snapshot_for_patient(session, patient) for patient in patients]
    batch = ScreeningBatch(
        id=_id("batch/mixed-matrix"),
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
                "The screening record does not contain enough information to answer "
                "that question."
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
