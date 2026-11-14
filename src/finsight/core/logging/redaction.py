"""Sensitive-field redaction for structured logs."""

from __future__ import annotations

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


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_sensitive_fields(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_sensitive_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive field values replaced (recursively)."""
    result: dict[str, Any] = {}
    for key, value in fields.items():
        if key.lower() in SENSITIVE_FIELD_NAMES:
            result[key] = REDACTED
        else:
            result[key] = _redact_value(value)
    return result
