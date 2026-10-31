"""Compatibility alias module for :class:`ExcelReader`.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

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
