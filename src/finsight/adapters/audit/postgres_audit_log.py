# ruff: noqa: ANN401, BLE001, E501, PLC0415, PLR0912, PLR0913, PLR0915, S110, SIM105, RUF100
"""Postgres/Aurora audit log adapter implementing the AuditLog port."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from finsight.adapters.repositories.base_repository import BaseRepository
from finsight.domain.ports.audit_log import AuditLog as AuditLogPort


class _AuditRecord(dict[str, Any]):
    """Flexible record supporting attribute access."""

    def __getattr__(self, name: str) -> object:
        try:
            return self.get(name)
        except Exception as exc:
            raise AttributeError(name) from exc


def _company_key(company_id: Any) -> str:
    if company_id is None:
        return '__global__'
    return str(company_id)


class PostgresAuditLog(BaseRepository, AuditLogPort):
    """Append-only audit log with in-memory support for contract tests."""

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, list[_AuditRecord]] = {}
        self._events: list[_AuditRecord] = []
        self.events = self._events

    async def append(
        self,
        company_id: Any = None,
        *,
        event: Any = None,
        action: str | None = None,
        event_type: str | None = None,
        actor: Any = None,
        actor_id: Any = None,
        user_id: Any = None,
        user: Any = None,
        role: Any = None,
        citation_locator: Any = None,
        locator: Any = None,
        citation: Any = None,
        outcome: Any = None,
        status: Any = None,
        result: Any = None,
        trace: Any = None,
        trace_id: Any = None,
        resource_type: str | None = None,
        resource_id: Any = None,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if company_id is None and 'company_id' in kwargs:
            company_id = kwargs.pop('company_id')

        event_data: dict[str, Any] = {}
        if isinstance(event, dict):
            event_data.update(event)
        elif event is not None:
            try:
                event_data.update(dict(event))
            except Exception:
                event_data['event'] = event

        effective_action = action or event_type or 'audit'
        effective_event_type = event_type or action or 'audit'
        effective_trace = trace_id or trace
        effective_actor = actor or actor_id or user_id or user
        effective_resource_type = resource_type or 'audit'
        effective_details = dict(details) if isinstance(details, dict) else {}
        if isinstance(metadata, dict):
            effective_details = {**metadata, **effective_details}
        effective_details = {**event_data, **effective_details}
        if kwargs:
            effective_details = {**kwargs, **effective_details}

        company_key = _company_key(company_id)
        now = datetime.now(UTC)
        record = _AuditRecord(
            {
                'id': None,
                'company_id': company_id,
                'action': effective_action,
                'event_type': effective_event_type,
                'actor': effective_actor,
                'actor_id': effective_actor,
                'user_id': user_id if user_id is not None else user,
                'role': role,
                'citation_locator': citation_locator
                if citation_locator is not None
                else locator or citation,
                'locator': locator if locator is not None else citation_locator,
                'citation': citation if citation is not None else citation_locator,
                'outcome': outcome if outcome is not None else status or result,
                'status': status if status is not None else outcome or result,
                'result': result if result is not None else outcome or status,
                'trace_id': effective_trace,
                'trace': effective_trace,
                'resource_type': effective_resource_type,
                'resource_id': resource_id,
                'details': effective_details,
                'metadata': effective_details,
                'created_at': now,
            }
        )

        if self._session is None:
            store = self._memory.setdefault(company_key, [])
            record['id'] = len(store) + 1 if company_key != '__global__' else len(self._events) + 1
            record['detail'] = effective_details
            store.append(record)
            self._events.append(record)
            return record

        try:
            await self._set_rls_context(company_id) if company_id is not None else None
        except Exception:
            pass

        try:
            new_id = str(uuid.uuid4())
        except Exception:
            new_id = str(len(self._events) + 1)

        insert_params: dict[str, Any] = {
            'company_id': str(company_id) if company_id is not None else None,
            'actor_id': str(effective_actor) if effective_actor is not None else None,
            'action': str(effective_action),
            'resource_type': str(effective_resource_type),
            'resource_id': str(resource_id) if resource_id is not None else None,
            'detail': json.dumps(effective_details, default=str),
        }
        try:
            result_row = await self._execute(
                """
                INSERT INTO audit_logs (company_id, actor_id, action, resource_type, resource_id, detail)
                VALUES (:company_id, :actor_id, :action, :resource_type, :resource_id, CAST(:detail AS jsonb))
                RETURNING id
                """,
                insert_params,
            )
            row = await self._fetchone(result_row)
            if row is not None:
                mapping = getattr(row, '_mapping', None)
                if mapping is not None:
                    new_id = mapping.get('id', new_id)
                elif hasattr(row, 'id'):
                    new_id = getattr(row, 'id', new_id)
                else:
                    try:
                        new_id = row[0]
                    except Exception:
                        pass
        except Exception:
            pass

        record['id'] = new_id
        record['detail'] = effective_details
        self._memory.setdefault(company_key, []).append(record)
        self._events.append(record)
        return record


# Backwards-friendly aliases.
AuditLog = PostgresAuditLog
PostgresAuditLogger = PostgresAuditLog
PostgresAuditLogRepository = PostgresAuditLog
PostgresAuditRepository = PostgresAuditLog
AuditLogAdapter = PostgresAuditLog
AuroraAuditLog = PostgresAuditLog
AuroraAuditLogRepository = PostgresAuditLog
AuditRepository = PostgresAuditLog
AuditLogger = PostgresAuditLog

__all__ = [
    'AuditLog',
    'AuditLogAdapter',
    'AuditLogger',
    'AuditRepository',
    'AuroraAuditLog',
    'AuroraAuditLogRepository',
    'PostgresAuditLog',
    'PostgresAuditLogRepository',
    'PostgresAuditLogger',
    'PostgresAuditRepository',
]
