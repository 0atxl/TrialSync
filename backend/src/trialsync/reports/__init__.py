"""Canonical report assembly and rendering for stored TrialSync screenings."""

from trialsync.reports.assembler import (
    REPORT_SCHEMA_VERSION,
    REPORT_TEMPLATE_VERSION,
    ScreeningReportCounts,
    ScreeningReportCriterion,
    ScreeningReportDocument,
    ScreeningReportEvidence,
    ScreeningReportMissingInformation,
    ScreeningReportPatientSnapshot,
    ScreeningReportTrial,
    assemble_screening_report,
)
from trialsync.reports.pdf import render_screening_report_pdf

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "REPORT_TEMPLATE_VERSION",
    "ScreeningReportCounts",
    "ScreeningReportCriterion",
    "ScreeningReportDocument",
    "ScreeningReportEvidence",
    "ScreeningReportMissingInformation",
    "ScreeningReportPatientSnapshot",
    "ScreeningReportTrial",
    "assemble_screening_report",
    "render_screening_report_pdf",
]
