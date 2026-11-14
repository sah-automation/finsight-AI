"""Deterministic document stamp for cache invalidation (pure domain)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

JsonObject = dict[str, object]


def _require_text(value: object, name: str) -> str:
    text = '' if value is None else str(value).strip()
    if not text:
        raise ValueError(f'{name} is required to compute a document stamp')
    return text


def _fingerprint(company_id: str, generation: int, document_versions: Mapping[str, str]) -> str:
    payload: JsonObject = {
        'company_id': company_id,
        'generation': generation,
        'documents': dict(document_versions),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DocumentStamp:
    """Fingerprint of a company's committed document versions.

    The stamp changes whenever the relevant state changes, and on every update
    because ``updated_for`` advances ``generation``. Cache keys include the
    stamp, so a changed stamp makes older cached answers unaddressable.
    """

    company_id: CompanyId
    value: str
    generation: int = 0
    updated_at: datetime | None = None

    @classmethod
    def initial(cls, company_id: CompanyId, *, updated_at: datetime | None = None) -> DocumentStamp:
        """Return the empty stamp created when a company is onboarded."""
        return cls.from_versions(company_id, {}, updated_at=updated_at)

    @classmethod
    def from_versions(
        cls,
        company_id: CompanyId,
        document_versions: Mapping[str, str] | None = None,
        *,
        generation: int = 0,
        updated_at: datetime | None = None,
    ) -> DocumentStamp:
        """Build a stamp from a deterministic mapping of document id to version marker."""
        company_key = _require_text(company_id, 'company_id')
        if generation < 0:
            raise ValueError('generation must not be negative')
        versions = {
            _require_text(document_id, 'document_id'): _require_text(marker, 'version marker')
            for document_id, marker in (document_versions or {}).items()
        }
        return cls(
            company_id=CompanyId(company_key),
            value=_fingerprint(company_key, generation, versions),
            generation=generation,
            updated_at=updated_at,
        )

    def updated_for(
        self,
        document_versions: Mapping[str, str],
        *,
        updated_at: datetime | None = None,
    ) -> DocumentStamp:
        """Return the next stamp for an update, always advancing ``generation``."""
        return type(self).from_versions(
            self.company_id,
            document_versions,
            generation=self.generation + 1,
            updated_at=updated_at,
        )


__all__ = ['DocumentStamp']
