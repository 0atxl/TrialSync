from __future__ import annotations

import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER, TA_LEFT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import inch  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from trialsync.reports.assembler import (
    ScreeningReportDocument,
    ScreeningReportEvidence,
    ScreeningReportMissingInformation,
)

_INK = colors.HexColor("#203136")
_MUTED = colors.HexColor("#5D6B6F")
_LINE = colors.HexColor("#CDD8D6")
_SURFACE = colors.HexColor("#F5F8F7")
_PASS = colors.HexColor("#E5F3E9")
_FAIL = colors.HexColor("#FAE8E9")
_UNKNOWN = colors.HexColor("#F9F0D9")

_FONT_CANDIDATES = (
    (
        Path("/usr/share/fonts/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/liberation/LiberationSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ),
)


@lru_cache(maxsize=1)
def _font_names() -> tuple[str, str]:
    for regular_path, bold_path in _FONT_CANDIDATES:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("TrialSyncSans", str(regular_path)))
            pdfmetrics.registerFont(TTFont("TrialSyncSansBold", str(bold_path)))
            return "TrialSyncSans", "TrialSyncSansBold"
    return "Helvetica", "Helvetica-Bold"


def _safe_text(value: object, *, empty: str = "—") -> str:
    if value is None or value == "":
        return empty
    if isinstance(value, dict | list):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return escape(str(value)).replace("\n", "<br/>")


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe_text(value), style)


def _result_background(result: str) -> colors.Color:
    return {"pass": _PASS, "fail": _FAIL, "unknown": _UNKNOWN}.get(result, _SURFACE)


def _evidence_table(
    items: list[ScreeningReportEvidence],
    *,
    styles: dict[str, ParagraphStyle],
) -> LongTable:
    headers = ["Fact ID", "Value", "Unit", "Effective date", "Source"]
    rows: list[list[Paragraph]] = [[_paragraph(item, styles["table_header"]) for item in headers]]
    for item in items:
        value = item.value
        if value is None:
            value = "Recorded fact"
        rows.append(
            [
                _paragraph(item.fact_id, styles["table_cell"]),
                _paragraph(value, styles["table_cell"]),
                _paragraph(item.unit, styles["table_cell"]),
                _paragraph(item.effective_date, styles["table_cell"]),
                _paragraph(item.source_label, styles["table_cell"]),
            ]
        )
    table = LongTable(
        rows,
        colWidths=[0.8 * inch, 1.55 * inch, 0.7 * inch, 1.05 * inch, 2.45 * inch],
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _missing_information_table(
    items: list[ScreeningReportMissingInformation],
    *,
    styles: dict[str, ParagraphStyle],
) -> LongTable:
    headers = ["Required fact", "Reason", "What is needed"]
    rows: list[list[Paragraph]] = [[_paragraph(item, styles["table_header"]) for item in headers]]
    rows.extend(
        [
            _paragraph(item.fact, styles["table_cell"]),
            _paragraph(item.reason, styles["table_cell"]),
            _paragraph(item.detail, styles["table_cell"]),
        ]
        for item in items
    )
    table = LongTable(
        rows,
        colWidths=[1.45 * inch, 1.15 * inch, 4.0 * inch],
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _metadata_table(
    rows: list[tuple[str, object]],
    *,
    styles: dict[str, ParagraphStyle],
) -> LongTable:
    table = LongTable(
        [
            [_paragraph(label, styles["metadata_label"]), _paragraph(value, styles["table_cell"])]
            for label, value in rows
        ],
        colWidths=[1.7 * inch, 4.85 * inch],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), _SURFACE),
                ("GRID", (0, 0), (-1, -1), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _draw_page(canvas: Any, document: Any) -> None:
    regular, _ = _font_names()
    canvas.saveState()
    canvas.setStrokeColor(_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(document.leftMargin, 0.57 * inch, letter[0] - document.rightMargin, 0.57 * inch)
    canvas.setFont(regular, 8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(document.leftMargin, 0.36 * inch, "TrialSync · Canonical screening report")
    canvas.drawRightString(
        letter[0] - document.rightMargin,
        0.36 * inch,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.setTitle("TrialSync canonical screening report")
    canvas.setAuthor("TrialSync")
    canvas.setSubject("Evidence-backed synthetic screening result")
    canvas.setCreator("TrialSync")
    canvas.restoreState()


def _report_styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "report-title",
            parent=base["Title"],
            fontName=bold,
            fontSize=24,
            leading=29,
            textColor=_INK,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "report-subtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=11,
            leading=15,
            textColor=_MUTED,
            spaceAfter=12,
        ),
        "disclaimer": ParagraphStyle(
            "report-disclaimer",
            parent=base["Normal"],
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#68551C"),
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "report-section",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=14,
            leading=18,
            textColor=_INK,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "criterion": ParagraphStyle(
            "report-criterion",
            parent=base["Heading3"],
            fontName=bold,
            fontSize=11,
            leading=14,
            textColor=_INK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "report-body",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=_INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "report-small",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=11,
            textColor=_MUTED,
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "report-table-header",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "report-table-cell",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.5,
            leading=10,
            textColor=_INK,
        ),
        "metadata_label": ParagraphStyle(
            "report-metadata-label",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=7.5,
            leading=10,
            textColor=_INK,
        ),
        "result": ParagraphStyle(
            "report-result",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=10,
            leading=13,
            textColor=_INK,
            alignment=TA_CENTER,
        ),
    }



def _summary_story(report: ScreeningReportDocument, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph("TrialSync", styles["title"]),
        Paragraph("Canonical screening report", styles["subtitle"]),
        Paragraph(
            "Educational synthetic-data prototype. This report records one stored deterministic "
            "screening result; it is not clinical advice, a diagnosis, or an enrollment decision.",
            styles["disclaimer"],
        ),
        _metadata_table(
            [
                ("Screening ID", report.screening_id),
                ("Overall result", report.overall_state.replace("_", " ")),
                ("Screening date", report.screening_date),
                ("Created at", report.created_at.isoformat()),
                ("Report generated at", report.generated_at.isoformat()),
            ],
            styles=styles,
        ),
        Spacer(1, 9),
        Paragraph("Patient snapshot", styles["section"]),
        _metadata_table(
            [
                ("Display name", report.patient_snapshot.display_name),
                ("Synthetic patient ID", report.patient_snapshot.external_id),
                ("Snapshot ID", report.patient_snapshot.id),
                ("Snapshot version", report.patient_snapshot.snapshot_version),
                ("Content hash", report.patient_snapshot.content_hash),
                ("Date of birth", report.patient_snapshot.date_of_birth),
                ("Biological sex", report.patient_snapshot.sex),
                ("Snapshot as of", report.patient_snapshot.as_of_date),
            ],
            styles=styles,
        ),
        Spacer(1, 8),
        Paragraph("Trial version", styles["section"]),
        _metadata_table(
            [
                ("Registry label", report.trial.registry_id),
                ("Trial title", report.trial.title),
                ("Approved version", report.trial.version),
                ("Immutable trial version ID", report.trial.id),
            ],
            styles=styles,
        ),
        Spacer(1, 8),
        Paragraph("Engine and result summary", styles["section"]),
        _metadata_table(
            [
                ("Engine version", report.engine_version),
                ("Rule DSL version", report.dsl_version),
                ("Terminology version", report.terminology_version),
                ("Unit version", report.unit_version),
                ("Pass criteria", report.counts.pass_count),
                ("Fail criteria", report.counts.fail_count),
                ("Unknown criteria", report.counts.unknown_count),
                ("Report schema", report.schema_version),
                ("Report template", report.template_version),
            ],
            styles=styles,
        ),
        Paragraph("Criterion evidence", styles["section"]),
    ]


def _criterion_story(
    report: ScreeningReportDocument, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    story: list[Any] = []

    for criterion in report.criteria:
        result = criterion.result.replace("_", " ")
        heading = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _result_background(criterion.result)),
                ("BOX", (0, 0), (-1, -1), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
        criterion_header = LongTable(
            [
                [
                    _paragraph(
                        f"Criterion {criterion.order} · {criterion.kind}",
                        styles["criterion"],
                    ),
                    _paragraph(result, styles["result"]),
                ]
            ],
            colWidths=[5.45 * inch, 1.1 * inch],
            hAlign="LEFT",
        )
        criterion_header.setStyle(heading)
        story.extend(
            [
                criterion_header,
                _paragraph(criterion.source_text, styles["body"]),
                Paragraph(
                    f"<b>Evaluation ID:</b> {_safe_text(criterion.id)} · "
                    f"<b>Criterion ID:</b> {_safe_text(criterion.criterion_id)}",
                    styles["small"],
                ),
                Paragraph(
                    f"<b>Reason code:</b> {_safe_text(criterion.reason_code)} · "
                    f"<b>Truth:</b> {_safe_text(criterion.truth)}",
                    styles["body"],
                ),
                _paragraph(criterion.canonical_explanation, styles["body"]),
                Paragraph("Recorded evidence", styles["small"]),
            ]
        )
        if criterion.evidence:
            story.append(_evidence_table(criterion.evidence, styles=styles))
        else:
            story.append(Paragraph("No supporting evidence was recorded.", styles["small"]))
        if criterion.missing_information:
            story.append(Paragraph("Missing information", styles["small"]))
            story.append(_missing_information_table(criterion.missing_information, styles=styles))
        if criterion.rejected_evidence:
            story.append(Paragraph("Rejected or stale evidence", styles["small"]))
            story.append(_evidence_table(criterion.rejected_evidence, styles=styles))
        story.append(Spacer(1, 5))
    return story


def render_screening_report_pdf(report: ScreeningReportDocument) -> bytes:
    """Render a provider-free report document into a bounded, multi-page PDF."""

    regular, bold = _font_names()
    styles = _report_styles(regular, bold)
    story = _summary_story(report, styles)
    story.extend(_criterion_story(report, styles))

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.62 * inch,
        rightMargin=0.62 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.75 * inch,
        title="TrialSync canonical screening report",
        author="TrialSync",
    )
    document.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()
