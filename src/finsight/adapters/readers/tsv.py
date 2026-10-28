"""Compatibility alias module for :class:`CsvReader` (TSV inputs)."""

from __future__ import annotations

from .csv_reader import CsvReader, TSVReader, TsvReader

TSV = TSVReader
Tsv = TsvReader

__all__ = ['TSV', 'CsvReader', 'TSVReader', 'Tsv', 'TsvReader']
