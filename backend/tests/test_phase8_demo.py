from __future__ import annotations

from collections import Counter

import pytest
from sqlalchemy import select

from trialsync.config import Settings
from trialsync.db.models import Screening, ScreeningChatMessage, User
from trialsync.db.session import get_session_factory
from trialsync.demo import (
    DEMO_EMAIL,
    _require_nonproduction,
    build_text_pdf,
    reset_demo_data,
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


async def test_demo_seed_is_reproducible_and_contains_mixed_outcomes() -> None:
    async with get_session_factory()() as session, session.begin():
        first = await seed_demo_data(session)
    assert first.patients == 6
    assert first.trials == 2
    assert first.screenings == 12
    assert first.chat_messages == 8

    async with get_session_factory()() as session, session.begin():
        second = await seed_demo_data(session)
    assert second == first

    async with get_session_factory()() as session:
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

    async with get_session_factory()() as session, session.begin():
        assert await reset_demo_data(session) is True
        assert await reset_demo_data(session) is False


def test_generated_demo_pdf_is_machine_readable_and_synthetic() -> None:
    extracted = extract_pdf_input(
        build_text_pdf("Patient name: Synthetic PDF Rowan\nDate of birth: 1986-04-18\nHbA1c: 7.8 %")
    )

    assert extracted.quality["extractor"] == "pypdf-6.14.2"
    assert "Synthetic PDF Rowan" in extracted.pages[0]["text"]


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
