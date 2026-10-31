"""Alias module for document table entity.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from .document_table import DocumentTable

__all__ = ['DocumentTable']
