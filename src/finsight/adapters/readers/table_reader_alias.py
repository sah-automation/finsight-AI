"""Compatibility alias module for :class:`TableReader`.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .table_reader import (
    LayoutTableReader,
    Table,
    TableDocumentReader,
    TableLayoutReader,
    TableReader,
)

__all__ = [
    'LayoutTableReader',
    'Table',
    'TableDocumentReader',
    'TableLayoutReader',
    'TableReader',
]
