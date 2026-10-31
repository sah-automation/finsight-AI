# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any

from ._job_progress_helpers import (
    _CONDITIONAL_WRITE_ATTEMPTS,
    _is_conditional_failure,
    _is_newer,
    _maybe_await,
    _norm,
    _order_field,
    _order_key,
    _ProgressRecord,
    _with_company_id,
)


class _JobProgressOperations:
    table: Any = None
    _memory: Any = None
    config: Any = None
    table_name: str = ''

    def _key(self, company_id: Any, job_id: Any) -> str:
        return f'{_norm(company_id)}#{_norm(job_id)}'

    def _extract(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> tuple[Any, Any, dict[str, Any]]:
        from ._job_progress_helpers import _extract as _m

        return _m(self, args, kwargs)

    def _build(self, company_id: Any, job_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        item: dict[str, Any] = {
            'company_id': _norm(company_id),
            'job_id': _norm(job_id),
            'pk': self._key(company_id, job_id),
            'sk': 'PROGRESS',
            'created_at': now,
            'updated_at': now,
        }
        alias_map = {
            'status': 'status',
            'progress': 'progress',
            'error': 'error',
            'error_message': 'error',
            'message': 'error',
            'receive_count': 'receive_count',
            'queue_position': 'queue_position',
            'queue_place': 'queue_position',
            'position': 'queue_position',
            'document_id': 'document_id',
            'document_version_id': 'document_version_id',
            'version_id': 'document_version_id',
            'version': 'document_version_id',
        }
        for src, dst in alias_map.items():
            if src in payload and payload.get(src) is not None:
                val = payload.get(src)
                if src in ('progress', 'receive_count'):
                    with contextlib.suppress(TypeError, ValueError):
                        val = int(str(val))
                item[dst] = val
        for key, val in payload.items():
            if key not in item:
                item[key] = val
        return item

    def _store_memory(self, item: dict[str, Any]) -> None:
        cid = _norm(item.get('company_id'))
        jid = _norm(item.get('job_id'))
        self._memory.setdefault(cid, {})[jid] = dict(item)

    async def _persist(self, item: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
        """Write one row, using an optimistic condition when ordering matters."""
        if self.table is None:
            self._store_memory(item)
            return

        kwargs: dict[str, Any] = {'Item': item}
        expected_field = _order_field(expected) if expected is not None else None
        if expected is not None and expected_field is not None:
            kwargs['ConditionExpression'] = 'attribute_not_exists(#order) OR #order = :expected'
            kwargs['ExpressionAttributeNames'] = {'#order': expected_field}
            kwargs['ExpressionAttributeValues'] = {':expected': expected[expected_field]}
        elif _order_key(item) is not None:
            # Creating an ordered row: never silently replace a concurrent write.
            kwargs['ConditionExpression'] = 'attribute_not_exists(#order)'
            kwargs['ExpressionAttributeNames'] = {'#order': _order_field(item)}

        await _maybe_await(self.table.put_item, **kwargs)
        self._store_memory(item)

    async def _persist_newer(self, item: dict[str, Any]) -> dict[str, Any]:
        """Persist an ordered row, retrying against concurrent newer writers."""
        cid = _norm(item.get('company_id'))
        jid = _norm(item.get('job_id'))
        for _attempt in range(_CONDITIONAL_WRITE_ATTEMPTS):
            existing = await self._fetch(cid, jid)
            if existing is not None and not _is_newer(existing, item):
                return dict(existing)
            try:
                await self._persist(item, expected=existing)
            except Exception as exc:
                if not _is_conditional_failure(exc):
                    raise
                continue
            return dict(item)
        existing = await self._fetch(cid, jid)
        if existing is not None:
            return dict(existing)
        raise RuntimeError(f'could not persist progress for job {jid!r}')

    async def _fetch(self, company_id: Any, job_id: Any) -> dict[str, Any] | None:
        cid = _norm(company_id)
        jid = _norm(job_id)
        if self.table is not None:
            for key in (
                {'job_id': jid, 'company_id': cid},
                {'pk': self._key(company_id, job_id)},
            ):
                try:
                    resp = await _maybe_await(self.table.get_item, Key=key, ConsistentRead=True)
                except Exception:  # noqa: S112
                    continue
                item = None
                if isinstance(resp, dict):
                    item = resp.get('Item', resp.get('item'))
                if isinstance(item, dict):
                    if (
                        _norm(item.get('company_id')) not in ('', None)
                        and _norm(item.get('company_id')) != cid
                    ):
                        continue
                    self._store_memory(item)
                    return dict(item)
        rec = self._memory.get(cid, {}).get(jid)
        if isinstance(rec, dict):
            if (
                _norm(rec.get('company_id')) not in ('', None)
                and _norm(rec.get('company_id')) != cid
            ):
                return None
            return dict(rec)
        return None

    async def write_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs_copy = _with_company_id(company_id, kwargs)
        cid, jid, payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '' and isinstance(company_id, str):
            cid = company_id
        if _norm(jid) == '' and len(args) > 0:
            for a in args:
                if isinstance(a, str) and a != _norm(cid):
                    # avoid reusing company_id
                    if _norm(a) == _norm(cid):
                        continue
                    jid = a
                    break
        # if still none maybe job_id in first arg different
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            raise ValueError('job_id required')
        item = self._build(cid, jid, payload)
        if _order_key(item) is not None:
            return _ProgressRecord(await self._persist_newer(item))
        await self._persist(item)
        return _ProgressRecord(item)

    async def reconcile_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        """Apply one Aurora-committed state to the rebuildable progress view.

        The row is keyed by company and job id. A strict Aurora ordering token
        (``revision``/``sequence`` or ``aurora_committed_at``) is mandatory so
        stale retries and duplicate deliveries can never overwrite a newer row.
        """
        kwargs_copy = _with_company_id(company_id, kwargs)
        cid, jid, payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '':
            cid = company_id
        if _norm(jid) == '':
            raise ValueError('job_id required')
        if _order_key(payload) is None:
            raise ValueError('revision or aurora_committed_at required to reconcile progress')
        payload.setdefault('source', 'aurora')
        return await self.write_progress(cid, jid, **payload)

    async def read_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs_copy = _with_company_id(company_id, kwargs)
        cid, jid, payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '' and isinstance(company_id, str):
            cid = company_id
        if _norm(jid) == '' and len(args) > 0:
            for a in args:
                if isinstance(a, str) and a != _norm(cid):
                    if _norm(a) == _norm(cid):
                        continue
                    jid = a
                    break
        if _norm(jid) == '':
            jid = payload.get('job_id')
            if jid is None:
                jid = payload.get('id')
            if jid is None:
                jid = payload.get('jobId')
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            raise ValueError('job_id required')
        item = await self._fetch(cid, jid)
        if item is None:
            return None
        if _norm(item.get('company_id')) not in ('', None) and _norm(
            item.get('company_id')
        ) != _norm(cid):
            return None
        return _ProgressRecord(item)

    async def list_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        cid = company_id
        if _norm(cid) == '':
            cid = kwargs.pop('company_id', None)
        results: list[Any] = []
        for c_key, jobs in self._memory.items():
            if cid is not None and _norm(c_key) != _norm(cid):
                continue
            for item in jobs.values():
                if not isinstance(item, dict):
                    continue
                if (
                    cid is not None
                    and _norm(item.get('company_id')) not in ('', None)
                    and _norm(item.get('company_id')) != _norm(cid)
                ):
                    continue
                results.append(_ProgressRecord(dict(item)))
        return results

    async def delete_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs_copy = dict(kwargs)
        if (
            company_id is not None
            and 'company_id' not in kwargs_copy
            and 'companyId' not in kwargs_copy
            and 'company' not in kwargs_copy
        ):
            kwargs_copy['company_id'] = company_id
        cid, jid, _payload = self._extract(args, kwargs_copy)
        if _norm(cid) == '' and isinstance(company_id, str):
            cid = company_id
        if _norm(cid) == '':
            raise ValueError('company_id required')
        if _norm(jid) == '':
            self._memory.pop(_norm(cid), None)
            return True
        store = self._memory.get(_norm(cid), {})
        deleted = store.pop(_norm(jid), None) is not None
        delete_errors: list[Exception] = []
        if self.table is not None:
            for key in (
                {'job_id': _norm(jid), 'company_id': _norm(cid)},
                {'pk': self._key(cid, jid)},
            ):
                try:
                    await _maybe_await(self.table.delete_item, Key=key)
                    break
                except Exception as exc:
                    delete_errors.append(exc)
            else:
                raise delete_errors[-1]
        return deleted

    async def rebuild(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def rebuild_from(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def rebuild_from_aurora(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def sync(self, *args: Any, **kwargs: Any) -> Any:
        return True

    async def refresh(self, *args: Any, **kwargs: Any) -> Any:
        return True
