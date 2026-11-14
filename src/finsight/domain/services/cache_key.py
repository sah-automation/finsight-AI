"""Tenant-scoped answer cache key composition."""

from __future__ import annotations

import hashlib
import json


def build_answer_cache_key(
    context: object,
    question: str,
    document_stamp: str,
) -> str:
    """Build a deterministic cache key that always includes the tenant identity."""
    company_id = getattr(context, 'company_id', '')
    role = getattr(context, 'role', None)
    access_scope = getattr(context, 'access_scope', [])
    payload = {
        'company_id': company_id,
        'role': getattr(role, 'value', role),
        'access_scope': sorted(getattr(cat, 'value', cat) for cat in access_scope),
        'question': ' '.join(question.split()),
        'document_stamp': document_stamp,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()
