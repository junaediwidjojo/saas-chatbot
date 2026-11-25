"""Resolve local knowledge without importing the web application."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def knowledge_path() -> Path:
    configured = os.getenv("SAAS_KNOWLEDGE_FILE", "").strip()
    if configured:
        path = project_path(configured)
        if not path.is_file():
            raise FileNotFoundError("SAAS_KNOWLEDGE_FILE must point to an existing knowledge file.")
        return path
    local = ROOT / "knowledge" / "mock-saas.md"
    return local if local.is_file() else ROOT / "knowledge" / "mock-saas.example.md"


def manuals_catalog_path() -> Path | None:
    """Catalog in SAAS_MANUALS_DIR; unset uses the committed example, empty disables manuals."""
    configured = os.environ.get("SAAS_MANUALS_DIR")
    if configured is None:
        return ROOT / "knowledge" / "manuals" / "catalog.json"
    if not configured.strip():
        return None
    catalog = project_path(configured.strip()) / "catalog.json"
    if not catalog.is_file():
        raise FileNotFoundError("SAAS_MANUALS_DIR must contain catalog.json.")
    return catalog
