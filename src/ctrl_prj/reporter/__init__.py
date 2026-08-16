"""Módulo reporter para geração de relatórios Markdown."""

from ctrl_prj.reporter.generator import (
    ReportResult,
    generate_entity_report,
    generate_index,
    generate_reports,
    sanitize_filename,
)

__all__ = [
    "ReportResult",
    "generate_reports",
    "generate_entity_report",
    "generate_index",
    "sanitize_filename",
]
