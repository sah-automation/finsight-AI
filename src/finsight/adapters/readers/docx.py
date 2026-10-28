"""Compatibility alias module for :class:`DocxReader`."""

from __future__ import annotations

from .docx_reader import (
    DOCX,
    Docx,
    DocxDocumentReader,
    DocxReader,
    WordDocumentReader,
    WordReader,
)

DOCXReader = DocxReader
Word = WordReader

__all__ = [
    'DOCX',
    'DOCXReader',
    'Docx',
    'DocxDocumentReader',
    'DocxReader',
    'Word',
    'WordDocumentReader',
    'WordReader',
]
