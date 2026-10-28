"""Compatibility alias module for :class:`CsvReader` (delimited inputs)."""

from __future__ import annotations

from .csv_reader import CsvReader, DelimitedDocumentReader, DelimitedReader

__all__ = ['CsvReader', 'DelimitedDocumentReader', 'DelimitedReader']
