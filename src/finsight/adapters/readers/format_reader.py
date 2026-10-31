"""Compatibility alias module for :class:.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .format_reader_selector import (
    FormatReader,
    FormatReaderSelector,
    FormatSelector,
    ReaderSelector,
    UnknownFormatError,
    UnsupportedFormatError,
    UnsupportedReaderFormatError,
)

__all__ = [
    'FormatReader',
    'FormatReaderSelector',
    'FormatSelector',
    'ReaderSelector',
    'UnknownFormatError',
    'UnsupportedFormatError',
    'UnsupportedReaderFormatError',
]
