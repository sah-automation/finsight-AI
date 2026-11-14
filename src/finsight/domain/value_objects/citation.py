"""Citation - value object for source references (pure domain).

Pinned to the answer-time document version so it never resolves to "latest".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """Immutable source reference linking to a specific location in a document."""

    document_id: str
    document_version: str | None = None
    document_version_id: str | None = None
    version: str | None = None
    version_id: str | None = None
    document_title: str | None = None
    title: str | None = None
    chunk_id: str | None = None
    chunk: str | None = None
    table_id: str | None = None
    table: str | None = None
    page_number: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    location: str | None = None

    # Signed citation locator token aliases (all canonicalise together).
    citation_locator: str | None = None
    locator: str | None = None
    citation_id: str | None = None
    citation_token: str | None = None
    citation_locator_token: str | None = None
    signed_locator: str | None = None
    signed_citation_locator: str | None = None
    token: str | None = None
    locator_token: str | None = None
    citation_locator_id: str | None = None

    def __post_init__(self) -> None:
        version = (
            self.document_version or self.document_version_id or self.version or self.version_id
        )
        object.__setattr__(self, 'document_version', version)
        object.__setattr__(self, 'document_version_id', version)
        object.__setattr__(self, 'version', version)
        object.__setattr__(self, 'version_id', version)

        title = self.document_title if self.document_title is not None else self.title
        object.__setattr__(self, 'document_title', title)
        object.__setattr__(self, 'title', title)

        chunk = self.chunk_id if self.chunk_id is not None else self.chunk
        object.__setattr__(self, 'chunk_id', chunk)
        object.__setattr__(self, 'chunk', chunk)

        table = self.table_id if self.table_id is not None else self.table
        object.__setattr__(self, 'table_id', table)
        object.__setattr__(self, 'table', table)

        start = self.start_char if self.start_char is not None else self.char_start
        end = self.end_char if self.end_char is not None else self.char_end
        object.__setattr__(self, 'start_char', start)
        object.__setattr__(self, 'end_char', end)
        object.__setattr__(self, 'char_start', start)
        object.__setattr__(self, 'char_end', end)

        locator = (
            self.citation_locator
            or self.locator
            or self.citation_id
            or self.citation_token
            or self.citation_locator_token
            or self.signed_locator
            or self.signed_citation_locator
            or self.token
            or self.locator_token
            or self.citation_locator_id
        )
        for name in (
            'citation_locator',
            'locator',
            'citation_id',
            'citation_token',
            'citation_locator_token',
            'signed_locator',
            'signed_citation_locator',
            'token',
            'locator_token',
            'citation_locator_id',
        ):
            object.__setattr__(self, name, locator)

    def __str__(self) -> str:
        return f'Citation(document_id={self.document_id!r}, version={self.document_version!r})'


__all__ = ['Citation']
