"""ReaderResult value object returned by every DocumentReader."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReaderResult:
    """Immutable result of reading a document.

    Carries the extracted text, tables, page numbers, overall confidence and
    optional citation-friendly locators. ``locators`` defaults to an empty
    list so existing builders and readers keep working unchanged.
    """

    text: str = ''
    tables: list[object] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    confidence: object = None
    locators: list[object] = field(default_factory=list)

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
        # Tolerate a missing locators value (``None``) or other collection while
        # keeping the field a list.
        if self.locators is None:
            object.__setattr__(self, 'locators', [])
        elif isinstance(self.locators, tuple):
            object.__setattr__(self, 'locators', list(self.locators))
        elif not isinstance(self.locators, list):
            raise TypeError('ReaderResult.locators must be a list or tuple')

    @property
    def effective_locators(self) -> list[object]:
        return list(self.locators or [])


__all__ = ['ReaderResult']
