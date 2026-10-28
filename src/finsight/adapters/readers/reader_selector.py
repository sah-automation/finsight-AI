"""Compatibility alias module for :class:."""

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
