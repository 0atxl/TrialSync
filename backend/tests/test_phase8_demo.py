from __future__ import annotations

import uuid
from collections import Counter

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trialsync.config import Settings
from trialsync.db.models import (
    CriterionEvaluation,
    CriterionKind,
    EvaluationResult,
    OverallState,
    Patient,
    Screening,
    ScreeningChatMessage,
    User,
    VersionStatus,
)
from trialsync.demo import (
    ADMIN_EMAIL,
    DEMO_EMAIL,
    DemoSeedSummary,
    _admin_patients,
    _admin_trials,
    _require_nonproduction,
    build_text_pdf,
    reset_demo_data,
    seed_admin_workspace,
    seed_demo_data,
)
from trialsync.evaluation import evaluate_fixture
from trialsync.imports.parser import extract_pdf_input

pytestmark = pytest.mark.anyio


def test_demo_database_commands_refuse_production() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://synthetic:synthetic@localhost/synthetic",
        environment="production",
    )

    with pytest.raises(SystemExit, match="disabled in production"):
        _require_nonproduction(settings)


async def test_demo_seed_is_reproducible_and_contains_mixed_outcomes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session, session.begin():
        first = await seed_demo_data(session)
    assert first.patients == 6
    assert first.trials == 2
    assert first.screenings == 12
    assert first.chat_messages == 8

    async with session_factory() as session, session.begin():
        second = await seed_demo_data(session)
    assert second == first

    async with session_factory() as session:
        owner_id = await session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
        assert owner_id is not None
        states = Counter(
            await session.scalars(
                select(Screening.overall_state).where(Screening.owner_id == owner_id)
            )
        )
        assert {state.value: count for state, count in states.items()} == {
            "potentially_eligible": 4,
            "likely_ineligible": 4,
            "needs_review": 4,
        }
        names = set(
            await session.scalars(select(Patient.display_name).where(Patient.owner_id == owner_id))
        )
        assert names == {
            "Synthetic Ada Mercer",
            "Synthetic Ben Carter",
            "Synthetic Cora Bennett",
            "Synthetic Dev Malik",
            "Synthetic Emi Tanaka",
            "Synthetic Finn Osei",
        }
        answer_states = Counter(
            state
            for state in await session.scalars(
                select(ScreeningChatMessage.answer_state)
                .join(Screening)
                .where(Screening.owner_id == owner_id)
            )
            if state is not None
        )
        assert answer_states == {
            "supported": 2,
            "refused": 1,
            "insufficient_evidence": 1,
        }

    async with session_factory() as session, session.begin():
        assert await reset_demo_data(session) is True
        assert await reset_demo_data(session) is False


async def test_demo_seed_can_create_an_isolated_workspace_for_another_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    mentor_email = "mentor-seed-test@trialsync.example"
    async with session_factory() as session, session.begin():
        demo = await seed_demo_data(session)
        mentor = await seed_demo_data(
            session,
            email=mentor_email,
            password="MentorSeed123!",
        )
        demo_user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        mentor_user = await session.scalar(select(User).where(User.email == mentor_email))

        assert demo == DemoSeedSummary(
            email=DEMO_EMAIL,
            patients=6,
            trials=2,
            screenings=12,
            batches=1,
            chat_messages=8,
        )
        assert mentor == DemoSeedSummary(
            email=mentor_email,
            patients=6,
            trials=2,
            screenings=12,
            batches=1,
            chat_messages=8,
        )
        assert demo_user is not None
        assert mentor_user is not None
        assert demo_user.id != mentor_user.id
        assert (
            await session.scalar(select(Patient.id).where(Patient.owner_id == mentor_user.id))
            is not None
        )


def test_generated_demo_pdf_is_machine_readable_and_synthetic() -> None:
    extracted = extract_pdf_input(
        build_text_pdf("Patient name: Synthetic PDF Rowan\nDate of birth: 1986-04-18\nHbA1c: 7.8 %")
    )

    assert extracted.quality["extractor"] == "pypdf-6.14.2"
    assert "Synthetic PDF Rowan" in extracted.pages[0]["text"]


def test_controlled_admin_builders_create_complete_non_synthetic_records() -> None:
    owner_id = uuid.uuid4()
    patients = _admin_patients(owner_id)
    trials = _admin_trials(owner_id)

    assert len(patients) == 20
    assert all(patient.owner_id == owner_id for patient in patients)
    assert all(len(patient.facts) == 21 for patient in patients)
    assert all("synthetic" not in patient.display_name.lower() for patient in patients)
    assert all(
        all("synthetic" not in fact.source_label.lower() for fact in patient.facts)
        for patient in patients
    )
    assert {fact.concept for fact in patients[0].facts} >= {
        "hba1c",
        "fasting_glucose",
        "egfr",
        "creatinine",
        "alt",
        "ast",
        "hemoglobin",
        "wbc",
        "platelets",
        "ldl",
        "triglycerides",
        "bmi",
        "systolic_bp",
        "diastolic_bp",
        "potassium",
        "albumin",
    }

    assert len(trials) == 15
    assert all(trial.owner_id == owner_id for trial in trials)
    assert all(trial.versions[0].status is VersionStatus.approved for trial in trials)
    assert all(len(trial.versions[0].criteria) == 10 for trial in trials)
    for trial in trials:
        criteria = trial.versions[0].criteria
        assert sum(item.kind is CriterionKind.inclusion for item in criteria) == 5
        assert sum(item.kind is CriterionKind.exclusion for item in criteria) == 5


async def test_controlled_admin_workspace_has_expected_history_distribution(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session, session.begin():
        summary = await seed_admin_workspace(session)
    assert summary.patients == 20
    assert summary.trials == 15
    assert summary.criteria == 150
    assert summary.screenings == 300
    assert (summary.potentially_eligible, summary.likely_ineligible, summary.needs_review) == (
        120,
        120,
        60,
    )

    async with session_factory() as session:
        admin_id = await session.scalar(select(User.id).where(User.email == ADMIN_EMAIL))
        assert admin_id is not None
        states = Counter(
            await session.scalars(
                select(Screening.overall_state).where(Screening.owner_id == admin_id)
            )
        )
        assert {state.value: count for state, count in states.items()} == {
            "potentially_eligible": 120,
            "likely_ineligible": 120,
            "needs_review": 60,
        }
        ineligible_id = await session.scalar(
            select(Screening.id).where(
                Screening.owner_id == admin_id,
                Screening.overall_state == OverallState.likely_ineligible,
            )
        )
        unknown_id = await session.scalar(
            select(Screening.id).where(
                Screening.owner_id == admin_id,
                Screening.overall_state == OverallState.needs_review,
            )
        )
        assert ineligible_id is not None
        assert unknown_id is not None
        ineligible_results = await session.scalars(
            select(CriterionEvaluation.result).where(
                CriterionEvaluation.screening_id == ineligible_id
            )
        )
        unknown_results = await session.scalars(
            select(CriterionEvaluation.result).where(CriterionEvaluation.screening_id == unknown_id)
        )
        assert sum(item is EvaluationResult.fail for item in ineligible_results) >= 5
        assert sum(item is EvaluationResult.unknown for item in unknown_results) >= 5


async def test_offline_evaluation_is_reproducible_and_fully_grounded() -> None:
    report = await evaluate_fixture(performance_iterations=2)

    assert report["synthetic_only"] is True
    assert report["network_requests"] == 0
    assert report["extraction"] == {
        "cases": 4,
        "candidate_precision": 1.0,
        "candidate_recall": 1.0,
        "exact_structure_accuracy": 1.0,
        "source_quote_validity": 1.0,
    }
    assert report["conversation"] == {
        "cases": 8,
        "answer_state_accuracy": 1.0,
        "supported_citation_validity": 1.0,
        "refusal_accuracy": 1.0,
    }
    assert all(report["acceptance"].values())
    assert report["performance"]["iterations"] == 8
    assert report["performance"]["p95_extraction_ms"] >= 0
