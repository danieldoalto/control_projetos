"""Módulo scanner para coleta de fatos no filesystem."""

from ctrl_prj.scanner.file_scanner import FileScanner, scan_entity_files
from ctrl_prj.scanner.models import ScannedFile
from ctrl_prj.scanner.orchestrator import (
    EntityScanSummary,
    ScanResult,
    run_scan,
)

__all__ = [
    "FileScanner",
    "scan_entity_files",
    "ScannedFile",
    "EntityScanSummary",
    "ScanResult",
    "run_scan",
]
