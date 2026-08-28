from __future__ import annotations

import base64
import uuid
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pypdf import PdfWriter
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trialsync.db.models import User
from trialsync.imports.parser import extract_pdf_input

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    prefix = f"phase6-{uuid.uuid4()}"
    yield prefix
    async with session_factory() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Import Reviewer",
            "password": "CorrectHorse123",
        },
    )


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def text_pdf(text: str) -> bytes:
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


def pdf_payload(content: bytes, **overrides: object) -> dict[str, object]:
    return {
        "kind": "patient",
        "source_type": "pdf",
        "content_base64": base64.b64encode(content).decode(),
        "filename": "synthetic.pdf",
        "mime_type": "application/pdf",
        **overrides,
    }


async def test_patient_text_import_is_reviewed_edited_and_then_approved(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    analyzed = await api.post(
        "/api/v1/imports",
        headers=headers,
        json={
            "kind": "patient",
            "source_type": "text",
            "text": (
                "Patient name: Synthetic Import Ada\n"
                "Date of birth: 1985-05-14\nSex: Female\n"
                "Condition: Synthetic metabolic condition\nHbA1c: 8.2 %\nHbA1c: 7.9 %"
            ),
        },
    )
    assert analyzed.status_code == 201, analyzed.text
    review = analyzed.json()
    assert review["status"] == "needs_review"
    assert review["approved_resource_id"] is None
    assert "Conflicting extracted values" in review["warnings"][0]
    assert review["candidates"]["facts"][0]["source"]["span_id"]
    assert (await api.get("/api/v1/patients", headers=headers)).json() == []

    candidates = review["candidates"]
    candidates["profile"]["display_name"] = "Synthetic Edited Ada"
    condition = next(item for item in candidates["facts"] if item["fact_type"] == "condition")
    condition["concept"] = "Synthetic edited condition"
    observations = [item for item in candidates["facts"] if item["fact_type"] == "observation"]
    observations[0]["effective_date"] = "2026-07-29"
    observations[1]["selected"] = False
    updated = await api.put(
        f"/api/v1/imports/{review['id']}",
        headers=headers,
        json={"candidates": candidates},
    )
    assert updated.status_code == 200, updated.text
    saved_condition = next(
        item for item in updated.json()["candidates"]["facts"] if item["fact_type"] == "condition"
    )
    assert saved_condition["concept"] == "Synthetic edited condition"
    assert saved_condition["source"]["text"].startswith("Condition:")
    assert any("active clinical catalog" in warning for warning in saved_condition["warnings"])

    approved = await api.post(
        f"/api/v1/imports/{review['id']}/approve", headers=headers, json={}
    )
    assert approved.status_code == 200, approved.text
    patient = await api.get(
        f"/api/v1/patients/{approved.json()['resource_id']}", headers=headers
    )
    assert patient.json()["display_name"] == "Synthetic Edited Ada"
    assert patient.json()["sex"] == "female"
    stored_observation = next(
        item for item in patient.json()["facts"] if item["fact_type"] == "observation"
    )
    assert stored_observation["concept"] == "hba1c"
    assert stored_observation["unit"] == "%"
    assert stored_observation["source_label"] == "Imported document p.1"
    assert not any(
        item["concept"] == "Synthetic edited condition" for item in patient.json()["facts"]
    )
    unsupported = next(
        item
        for item in patient.json()["unsupported_details"]
        if item["label"] == "Synthetic edited condition"
    )
    assert "active clinical catalog" in unsupported["context"]
    activity = await api.get(
        f"/api/v1/patients/{patient.json()['id']}/activity", headers=headers
    )
    assert activity.status_code == 200
    activity_types = [item["event_type"] for item in activity.json()]
    assert "patient_created" in activity_types
    assert "fact_created" in activity_types
    immutable = await api.put(
        f"/api/v1/imports/{review['id']}", headers=headers, json={"candidates": candidates}
    )
    assert immutable.status_code == 409


async def test_patient_import_replaces_catalog_warnings_after_a_reviewer_fix(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}-warning-fix@example.com")
    headers = auth(account)
    analyzed = await api.post(
        "/api/v1/imports",
        headers=headers,
        json={
            "kind": "patient",
            "source_type": "text",
            "text": (
                "Patient name: Synthetic Warning Ada\n"
                "Date of birth: 1985-05-14\n"
                "Condition: Unmapped synthetic condition"
            ),
        },
    )
    assert analyzed.status_code == 201, analyzed.text
    review = analyzed.json()
    original_fact = review["candidates"]["facts"][0]
    assert any("active clinical catalog" in warning for warning in original_fact["warnings"])

    candidates = review["candidates"]
    candidates["facts"][0]["concept"] = "Hypertension"
    saved = await api.put(
        f"/api/v1/imports/{review['id']}", headers=headers, json={"candidates": candidates}
    )
    assert saved.status_code == 200, saved.text
    saved_fact = saved.json()["candidates"]["facts"][0]
    assert not any("active clinical catalog" in warning for warning in saved_fact["warnings"])
    assert not any(warning.startswith("Catalog review:") for warning in saved.json()["warnings"])


async def test_patient_import_maps_common_catalog_aliases(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}-aliases@example.com")
    headers = auth(account)
    analyzed = await api.post(
        "/api/v1/imports",
        headers=headers,
        json={
            "kind": "patient",
            "source_type": "text",
            "text": (
                "Patient name: Synthetic Alias Ada\n"
                "Condition: Type II diabetes mellitus\n"
                "Medication: Metformin hydrochloride"
            ),
        },
    )
    assert analyzed.status_code == 201, analyzed.text
    review = analyzed.json()
    assert not any(
        "active clinical catalog" in warning for warning in review["warnings"]
    )
    approved = await api.post(
        f"/api/v1/imports/{review['id']}/approve", headers=headers, json={}
    )
    assert approved.status_code == 200, approved.text
    patient = await api.get(
        f"/api/v1/patients/{approved.json()['resource_id']}", headers=headers
    )
    assert {
        (item["fact_type"], item["concept"])
        for item in patient.json()["facts"]
    } == {("condition", "type2_diabetes"), ("medication", "metformin")}


async def test_trial_import_requires_manual_rule_review_and_creates_a_draft(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    analyzed = await api.post(
        "/api/v1/imports",
        headers=headers,
        json={
            "kind": "trial",
            "source_type": "text",
            "text": (
                "Title: Synthetic import protocol\nCondition: Synthetic condition\nPhase: Phase 2\n"
                "Inclusion Criteria:\n- Age 18 to 75 years\n"
                "- HbA1c greater than or equal to 7.0 %\n"
                "Exclusion Criteria:\n- Investigator judgment"
            ),
        },
    )
    review = analyzed.json()
    assert [item["parse_state"] for item in review["candidates"]["criteria"]] == [
        "parsed",
        "parsed",
        "needs_manual_rule",
    ]
    assert review["candidates"]["criteria"][1]["normalized_rule"] == {
        "op": "gte",
        "fact": "observation.hba1c",
        "value": 7.0,
        "unit": "%",
    }
    incomplete = await api.post(
        f"/api/v1/imports/{review['id']}/approve", headers=headers, json={}
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["error"]["code"] == "IMPORT_REVIEW_INCOMPLETE"

    candidates = review["candidates"]
    candidates["criteria"][0]["source_text"] = "Edited age 18 to 75 years"
    candidates["criteria"][2]["selected"] = False
    saved = await api.put(
        f"/api/v1/imports/{review['id']}", headers=headers, json={"candidates": candidates}
    )
    assert saved.status_code == 200
    approved = await api.post(
        f"/api/v1/imports/{review['id']}/approve", headers=headers, json={}
    )
    assert approved.status_code == 200, approved.text
    trial = await api.get(f"/api/v1/trials/{approved.json()['resource_id']}", headers=headers)
    assert trial.json()["versions"][0]["status"] == "draft"
    assert trial.json()["versions"][0]["criteria"][0]["source_text"] == (
        "Edited age 18 to 75 years"
    )


async def test_trial_import_rejects_a_malformed_edited_rule(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}-invalid-rule@example.com")
    headers = auth(account)
    analyzed = await api.post(
        "/api/v1/imports",
        headers=headers,
        json={
            "kind": "trial",
            "source_type": "text",
            "text": (
                "Title: Synthetic invalid rule protocol\n"
                "Condition: Synthetic condition\n"
                "Inclusion Criteria:\n- Age 18 to 75 years"
            ),
        },
    )
    assert analyzed.status_code == 201, analyzed.text
    review = analyzed.json()
    candidates = review["candidates"]
    candidates["criteria"][0]["normalized_rule"]["op"] = "presnet"
    saved = await api.put(
        f"/api/v1/imports/{review['id']}",
        headers=headers,
        json={"candidates": candidates},
    )
    assert saved.status_code == 422, saved.text
    assert saved.json()["error"]["code"] == "IMPORT_RULE_INVALID"
    assert '"presnet"' in saved.json()["error"]["message"]


async def test_text_pdf_preserves_page_text_and_pdf_failures_are_explicit(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    valid = await api.post(
        "/api/v1/imports",
        headers=headers,
        json=pdf_payload(
            text_pdf(
                "Patient name: Synthetic PDF Ada\nDate of birth: 1990-01-01\nHbA1c: 7.4 %"
            )
        ),
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["pages"][0]["page"] == 1
    assert "Synthetic PDF Ada" in valid.json()["pages"][0]["text"]
    assert valid.json()["quality"]["extractor"] == "pypdf-6.14.2"

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    scan = BytesIO()
    writer.write(scan)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "trialsync.imports.parser._extract_with_tesseract",
            lambda content, page_count: [
                "Patient name: Synthetic OCR Ada\nDate of birth: 1990-01-01\nHbA1c: 7.4 %"
            ],
        )
        ocr_input = extract_pdf_input(scan.getvalue())
    assert ocr_input.pages[0]["text"].startswith("Patient name: Synthetic OCR Ada")
    assert ocr_input.quality["extractor"] == "tesseract-ocr"
    assert ocr_input.quality["ocr"]["engine"] == "tesseract"

    scan_like = await api.post(
        "/api/v1/imports", headers=headers, json=pdf_payload(scan.getvalue())
    )
    assert scan_like.status_code == 422
    assert scan_like.json()["error"]["code"] == "OCR_NO_TEXT"

    empty_writer = PdfWriter()
    empty = BytesIO()
    empty_writer.write(empty)
    empty_pdf = await api.post(
        "/api/v1/imports", headers=headers, json=pdf_payload(empty.getvalue())
    )
    assert empty_pdf.status_code == 422
    assert empty_pdf.json()["error"]["code"] == "PDF_EMPTY"

    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=612, height=792)
    encrypted_writer.encrypt("synthetic-password")
    encrypted = BytesIO()
    encrypted_writer.write(encrypted)
    encrypted_response = await api.post(
        "/api/v1/imports", headers=headers, json=pdf_payload(encrypted.getvalue())
    )
    assert encrypted_response.status_code == 422
    assert encrypted_response.json()["error"]["code"] == "PDF_ENCRYPTED"

    failures = [
        (b"", "IMPORT_EMPTY"),
        (b"not a pdf", "IMPORT_WRONG_TYPE"),
        (b"%PDF-malformed", "PDF_MALFORMED"),
        (b"%PDF-" + b"x" * 5_000_001, "IMPORT_TOO_LARGE"),
    ]
    for content, code in failures:
        response = await api.post(
            "/api/v1/imports", headers=headers, json=pdf_payload(content)
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == code
    assert (await api.get("/api/v1/patients", headers=headers)).json() == []


async def test_import_ownership_and_provenance_cannot_be_replaced(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    created = await api.post(
        "/api/v1/imports",
        headers=auth(first),
        json={
            "kind": "patient",
            "source_type": "text",
            "text": "Patient name: Synthetic Owner\nHbA1c: 8.0 %",
        },
    )
    review = created.json()
    assert (
        await api.get(f"/api/v1/imports/{review['id']}", headers=auth(second))
    ).status_code == 404
    review["candidates"]["facts"][0]["source"]["span_id"] = str(uuid.uuid4())
    invalid = await api.put(
        f"/api/v1/imports/{review['id']}",
        headers=auth(first),
        json={"candidates": review["candidates"]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "IMPORT_PROVENANCE_INVALID"
