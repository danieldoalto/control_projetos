"""Módulo discovery para identificação de entidades de projeto ou scripts."""

from ctrl_prj.discovery.explorer import ProjectExplorer, discover_entities
from ctrl_prj.discovery.heuristics import is_project_directory
from ctrl_prj.discovery.manifest import MANIFEST_FILENAME, read_manifest
from ctrl_prj.discovery.models import DiscoveredEntity, Manifest

__all__ = [
    "DiscoveredEntity",
    "Manifest",
    "MANIFEST_FILENAME",
    "read_manifest",
    "is_project_directory",
    "ProjectExplorer",
    "discover_entities",
]
