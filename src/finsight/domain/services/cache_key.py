"""Tenant-scoped answer cache key composition."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import RequestContext


def build_answer_cache_key(
    context: RequestContext,
    question: str,
    document_stamp: str,
) -> str:
    """Build a deterministic cache key that always includes the tenant identity."""
    payload = {
        'company_id': context.company_id,
        'role': context.role.value,
        'access_scope': sorted(category.value for category in context.access_scope),
        'question': ' '.join(question.split()),
        'document_stamp': document_stamp,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()
