# Citation - Value object for source references

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """Immutable source reference linking to a specific location in a document."""

    document_id: str
    page_number: int | None = None
    chunk_id: str | None = None
    table_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None
