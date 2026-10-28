"""Compatibility alias module for :class:`TableReader`."""

from __future__ import annotations

from .table_reader import TableReader

TableLayout = TableReader
TableReaderAlias = TableReader

__all__ = ['TableLayout', 'TableReader', 'TableReaderAlias']
