"""Compatibility alias module for :class:`ExcelReader`."""

from __future__ import annotations

from .excel_reader import (
    Excel,
    ExcelDocumentReader,
    ExcelReader,
    SpreadsheetReader,
    XlsReader,
    XlsxDocumentReader,
    XlsxReader,
)

__all__ = [
    'Excel',
    'ExcelDocumentReader',
    'ExcelReader',
    'SpreadsheetReader',
    'XlsReader',
    'XlsxDocumentReader',
    'XlsxReader',
]
