"""Sensitive-field redaction for structured logs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        'answer',
        'answer_text',
        'api_key',
        'chunk_text',
        'document_text',
        'password',
        'pii',
        'prompt',
        'question',
        'question_text',
        'raw_text',
        'secret',
        'token',
    }
)

REDACTED = '[REDACTED]'


def redact_sensitive_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive field values replaced."""
    return {
        key: REDACTED if key.lower() in SENSITIVE_FIELD_NAMES else value
        for key, value in fields.items()
    }
