# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from finsight.domain.services.cache_key import build_answer_cache_key

from ._answer_cache_helpers import (
    _LIFECYCLE_CLEAR_EVENTS,
    _LOGGER,
    _as_sequence,
    _CacheContext,
    _decode_value,
    _encode_value,
    _maybe_await,
    _stamp_value,
    _text,
)


class _AnswerCacheOperations:
    table: Any = None
    resource: Any = None
    _memory: Any = None
    config: Any = None
    enabled: bool = True
    answer_cache_enabled: bool = True
    table_name: str = ''
    key_prefix: str = ''
    ttl_seconds: int = 3600
    max_entry_size_bytes: int = 1024 * 1024

    def _build_key(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> str:
        if key is not None and str(key).strip():
            explicit = str(key).strip()
            if explicit.startswith(self.key_prefix):
                return explicit
            return f'{self.key_prefix}{explicit}'
        context = _CacheContext(company_id, role, access_scope)
        digest = build_answer_cache_key(
            context,
            question or '',
            _stamp_value(document_stamp),
        )
        return f'{self.key_prefix}{digest}'

    def build_key(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> str:
        """Return the cache key that would be used for this lookup."""
        return self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )

    key_for = build_key

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> object:
        if not self.enabled:
            return None
        cache_key = self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )
        item = await self._fetch(_text(company_id), cache_key)
        if item is None or self._expired(item):
            return None
        return _decode_value(item.get('value'), item.get('encoding'))

    async def set(self, *args: Any, **kwargs: Any) -> Any:
        return await self._set_impl(*args, **kwargs)

    async def _set_impl(
        self,
        company_id: object,
        value: object,
        *,
        key: str | None = None,
        ttl_seconds: int | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> None:
        if not self.enabled:
            return
        cache_key = self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )
        payload, encoding = _encode_value(value)
        if (
            self.max_entry_size_bytes > 0
            and len(payload.encode('utf-8')) > self.max_entry_size_bytes
        ):
            raise ValueError(
                f'answer cache entry is {len(payload.encode("utf-8"))} bytes, '
                f'limit is {self.max_entry_size_bytes}'
            )
        ttl = self.ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        now = datetime.now(UTC)
        item: dict[str, Any] = {
            'pk': _text(company_id),
            'sk': cache_key,
            'company_id': _text(company_id),
            'cache_key': cache_key,
            'value': payload,
            'encoding': encoding,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'document_stamp': _stamp_value(document_stamp),
            'role': _text(getattr(role, 'value', role)),
            'access_scope': [
                _text(getattr(entry, 'value', entry)) for entry in _as_sequence(access_scope)
            ],
            'question': question or '',
        }
        if ttl > 0:
            item['ttl'] = int(now.timestamp()) + ttl
        await self._persist(item)

    async def clear(self, company_id: object, **kwargs: object) -> None:
        company = _text(company_id)
        self._memory.pop(company, None)
        if self.table is None:
            return
        await self._delete_remote_company(company)

    async def delete(
        self,
        company_id: object,
        key: str | None = None,
        **kwargs: Any,
    ) -> bool:
        if key is None:
            await self.clear(company_id, **kwargs)
            return True
        cache_key = self._build_key(company_id, key=key, **kwargs)
        company = _text(company_id)
        store = self._memory.setdefault(company, {})
        existed = store.pop(cache_key, None) is not None
        if self.table is not None:
            try:
                await _maybe_await(
                    self.table.delete_item,
                    Key={'pk': company, 'sk': cache_key},
                )
                existed = True
            except Exception as exc:
                _LOGGER.debug('answer cache delete failed: %s', exc)
        return existed

    # ------------------------------------------------------------------
    # Lifecycle invalidation
    # ------------------------------------------------------------------

    async def clear_on_upload(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_update(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_delete(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_reprocess(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def handle_change_event(
        self,
        company_id: object,
        event: object,
        **kwargs: object,
    ) -> bool:
        """Clear cached answers when a document lifecycle event is published."""
        event_company = _text(getattr(event, 'company_id', company_id))
        if event_company and event_company != _text(company_id):
            raise ValueError('change event company_id must match the cache tenant')
        event_type = _text(getattr(event, 'event_type', '')).strip().lower()
        if event_type in _LIFECYCLE_CLEAR_EVENTS:
            await self.clear(company_id, **kwargs)
            return True
        return False

    on_change_event = handle_change_event
    clear_for_event = handle_change_event

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _expired(item: dict[str, Any]) -> bool:
        ttl = item.get('ttl')
        try:
            return ttl is not None and int(str(ttl)) <= int(time.time())
        except (TypeError, ValueError):
            return False

    async def _fetch(self, company_id: str, cache_key: str) -> dict[str, Any] | None:
        item = self._memory.get(company_id, {}).get(cache_key)
        if isinstance(item, dict):
            return dict(item)
        if self.table is None:
            return None
        try:
            response = await _maybe_await(
                self.table.get_item,
                Key={'pk': company_id, 'sk': cache_key},
                ConsistentRead=True,
            )
        except Exception as exc:
            _LOGGER.debug('answer cache read failed: %s', exc)
            return None
        remote = response.get('Item') if isinstance(response, dict) else None
        if not isinstance(remote, dict):
            return None
        if _text(remote.get('company_id')) not in ('', company_id):
            return None
        self._memory.setdefault(company_id, {})[cache_key] = dict(remote)
        return dict(remote)

    async def _persist(self, item: dict[str, Any]) -> None:
        company = _text(item.get('company_id'))
        cache_key = _text(item.get('sk'))
        self._memory.setdefault(company, {})[cache_key] = dict(item)
        if self.table is None:
            return
        try:
            await _maybe_await(self.table.put_item, Item=item)
        except Exception as exc:
            _LOGGER.warning('answer cache write failed: %s', exc)

    async def _delete_remote_company(self, company_id: str) -> None:
        from ._answer_cache_helpers import _delete_remote_company as _m

        return await _m(self, company_id)
