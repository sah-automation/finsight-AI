"""Citation and evidence validation for generated answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.value_objects import Citation


def is_citation_valid(citation: Citation) -> bool:
    """Return True when a citation points at a real, answer-time source."""
    if not getattr(citation, 'document_id', '').strip():
        return False
    version = getattr(citation, 'document_version', None)
    if version is None or not str(version).strip():
        return False
    return not (citation.page_number is not None and citation.page_number < 1)


def answer_has_evidence(citations: Sequence[Citation]) -> bool:
    """Return True when an answer has at least one valid citation."""
    return bool(citations) and all(is_citation_valid(citation) for citation in citations)
