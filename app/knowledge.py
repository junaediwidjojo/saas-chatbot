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
