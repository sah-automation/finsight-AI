"""Compatibility alias module for :class:`SelfHostedLayoutReader`.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .self_hosted_layout_reader import (
    Layout,
    LayoutDocumentReader,
    LayoutReader,
    SelfHosted,
    SelfHostedDocumentReader,
    SelfHostedLayout,
    SelfHostedLayoutReader,
    SelfHostedReader,
)

__all__ = [
    'Layout',
    'LayoutDocumentReader',
    'LayoutReader',
    'SelfHosted',
    'SelfHostedDocumentReader',
    'SelfHostedLayout',
    'SelfHostedLayoutReader',
    'SelfHostedReader',
]
