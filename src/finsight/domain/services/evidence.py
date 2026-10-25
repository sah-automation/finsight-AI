"""Citation and evidence validation for generated answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.core.types import Citation


def is_citation_valid(citation: Citation) -> bool:
    """Return True when a citation points at a real source location."""
    if not citation.document_id.strip():
        return False
    return citation.page_number is None or citation.page_number >= 1


def answer_has_evidence(citations: Sequence[Citation]) -> bool:
    """Return True when an answer has at least one valid citation."""
    return bool(citations) and all(is_citation_valid(citation) for citation in citations)
