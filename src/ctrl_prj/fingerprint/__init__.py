"""Módulo fingerprint para cálculo determinístico de hashes, status macro e deltas."""

from ctrl_prj.fingerprint.calculator import calculate_entity_fingerprint
from ctrl_prj.fingerprint.comparator import MacroStatus, compare_entity_state
from ctrl_prj.fingerprint.delta import FileDelta, compute_file_delta
from ctrl_prj.fingerprint.hasher import (
    hash_bytes,
    hash_file,
    hash_scanned_file,
    hash_scanned_files,
)
from ctrl_prj.fingerprint.models import HashedFile

__all__ = [
    "HashedFile",
    "FileDelta",
    "hash_bytes",
    "hash_file",
    "hash_scanned_file",
    "hash_scanned_files",
    "calculate_entity_fingerprint",
    "MacroStatus",
    "compare_entity_state",
    "compute_file_delta",
]
