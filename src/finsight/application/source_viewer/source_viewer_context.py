"""Mutable context carried through the source-viewer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceViewerContext:
    """Freely mutable context carrying a single source-view run's state."""

    # Inputs
    company_id: Any = None
    user_id: Any = None
    role: Any = None
    trace_id: Any = None
    permissions: Any = None
    access_scope: Any = None
    category: Any = None
    citation_input: Any = None
    document_id: Any = None
    version_id: Any = None
    chunk_id: Any = None
    storage_key: Any = None
    page: Any = None
    ttl: Any = None
    original_requested: Any = None

    # Intermediates
    signing_key: Any = None
    secret: Any = None
    version_obj: Any = None
    document_obj: Any = None
    document_title: Any = None
    chunk_obj: Any = None
    table_payload: Any = None
    tables: list[Any] = field(default_factory=list)
    text: Any = None
    needs_review: Any = None
    content_type: Any = None
    highlight: Any = None
    newer_available: Any = None
    newer_id: Any = None
    original_available: Any = None
    signed_original_link: Any = None
    locator_token: Any = None
    locator_payload: Any = None
    locator: Any = None

    # Output
    result_obj: Any = None
    outcome: Any = None

    # Extras carried for compatibility
    extras: dict[str, Any] = field(default_factory=dict)


__all__ = ['SourceViewerContext']
