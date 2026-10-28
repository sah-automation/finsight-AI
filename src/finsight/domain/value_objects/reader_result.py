"""ReaderResult value object returned by every DocumentReader."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReaderResult:
    """Immutable result of reading a document.

    Carries the extracted text, tables, page numbers and overall confidence.
    """

    text: str = ''
    tables: list[object] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    confidence: object = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            object.__setattr__(self, 'text', str(self.text) if self.text is not None else '')
        if not isinstance(self.tables, (list, tuple)):
            raise TypeError('ReaderResult.tables must be a list or tuple')
        if not isinstance(self.page_numbers, (list, tuple)):
            raise TypeError('ReaderResult.page_numbers must be a list or tuple')
        for page in self.page_numbers:
            if isinstance(page, bool) or not isinstance(page, int):
                raise TypeError('ReaderResult.page_numbers must contain integers')


__all__ = ['ReaderResult']
