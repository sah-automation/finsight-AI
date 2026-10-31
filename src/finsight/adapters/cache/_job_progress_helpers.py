# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any

_PROGRESS_STORES: dict[str, dict[str, dict[str, Any]]] = {}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'queue') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        if hasattr(arg, 'config'):
            cfg = getattr(arg, 'config', None)
            if cfg is not None:
                return cfg
    return None


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if name in config and config.get(name) is not None:
                return config.get(name)
            for section in ('caches', 'cache', 'job_progress', 'progress', 'dynamodb'):
                sec = config.get(section)
                if isinstance(sec, dict) and sec.get(name) is not None:
                    return sec.get(name)
        else:
            val = getattr(config, name, None)
            if val is not None:
                return val
            for attr in ('caches', 'cache', 'job_progress', 'progress'):
                sec = getattr(config, attr, None)
                if sec is not None:
                    v = sec.get(name) if isinstance(sec, dict) else getattr(sec, name, None)
                    if v is not None:
                        return v
    return default


def _is_table(obj: Any) -> bool:
    return obj is not None and (
        hasattr(obj, 'put_item')
        or hasattr(obj, 'get_item')
        or hasattr(obj, 'query')
        or hasattr(obj, 'scan')
    )


async def _maybe_await(value: Any, *a: Any, **k: Any) -> Any:
    result = value(*a, **k) if callable(value) else value
    if inspect.isawaitable(result):
        return await result
    return result


def _norm(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


_ORDER_FIELDS = ('revision', 'aurora_revision', 'sequence')
_AURORA_TIME_FIELDS = ('aurora_committed_at', 'source_updated_at')
_CONDITIONAL_WRITE_ATTEMPTS = 3


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed: datetime | None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(value, UTC)
        else:
            text = str(value).strip()
            if text.endswith('Z'):
                text = f'{text[:-1]}+00:00'
            parsed = datetime.fromisoformat(text) if text else None
    except (OverflowError, OSError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _order_key(item: dict[str, Any]) -> tuple[str, int | datetime] | None:
    """Return the Aurora ordering token carried by a progress row."""
    for field in _ORDER_FIELDS:
        revision = _as_int(item.get(field))
        if revision is not None:
            return ('revision', revision)
    for field in _AURORA_TIME_FIELDS:
        committed_at = _as_datetime(item.get(field))
        if committed_at is not None:
            return ('committed_at', committed_at)
    return None


def _order_field(item: dict[str, Any]) -> str | None:
    """Return the attribute name that carried the item's ordering token."""
    for field in _ORDER_FIELDS:
        if _as_int(item.get(field)) is not None:
            return field
    for field in _AURORA_TIME_FIELDS:
        if _as_datetime(item.get(field)) is not None:
            return field
    return None


def _is_newer(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> bool:
    """Only a strictly newer Aurora ordering token may replace a view row."""
    incoming_order = _order_key(incoming)
    if incoming_order is None:
        return existing is None
    existing_order = _order_key(existing) if existing is not None else None
    if existing_order is None:
        return True
    if incoming_order[0] != existing_order[0]:
        # Mixed tokens cannot be compared safely; keep the existing row.
        return False
    incoming_value = incoming_order[1]
    existing_value = existing_order[1]
    if isinstance(incoming_value, int) and isinstance(existing_value, int):
        return incoming_value > existing_value
    if isinstance(incoming_value, datetime) and isinstance(existing_value, datetime):
        return incoming_value > existing_value
    return False


def _with_company_id(company_id: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Copy kwargs and add the positional company id when the caller omitted it."""
    copied = dict(kwargs)
    if company_id is not None and not any(
        key in copied for key in ('company_id', 'companyId', 'company')
    ):
        copied['company_id'] = company_id
    return copied


def _is_conditional_failure(exc: BaseException) -> bool:
    """Return True for a DynamoDB conditional-check failure."""
    response = getattr(exc, 'response', None)
    if not isinstance(response, dict):
        return False
    error = response.get('Error')
    return isinstance(error, dict) and error.get('Code') == 'ConditionalCheckFailedException'


class _ProgressRecord(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except Exception as exc:
            raise AttributeError(name) from exc


def _extract(
    self: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[Any, Any, dict[str, Any]]:
    company_id = kwargs.pop('company_id', None)
    if company_id is None:
        company_id = kwargs.pop('companyId', None)
    if company_id is None:
        company_id = kwargs.pop('company', None)
    if company_id is None:
        company_id = kwargs.pop('tenant_id', None)
    job_id = kwargs.pop('job_id', None)
    if job_id is None:
        job_id = kwargs.pop('jobId', None)
    if job_id is None:
        job_id = kwargs.pop('id', None)
    if job_id is None:
        job_id = kwargs.pop('job', None)
    rest = list(args)
    if company_id is None and rest and not isinstance(rest[0], dict):
        # could be job_id if only job passed? but need both; try to infer
        company_id = rest.pop(0)
    if job_id is None and rest and not isinstance(rest[0], dict):
        job_id = rest.pop(0)
    # if still None maybe swapped?
    payload: dict[str, Any] = {}
    for item in rest:
        if isinstance(item, dict):
            payload.update(item)
    for key, value in list(kwargs.items()):
        if key in {
            'company_id',
            'companyId',
            'company',
            'tenant_id',
            'job_id',
            'jobId',
            'id',
            'job',
        }:
            continue
        payload[key] = value
    # infer from payload
    if job_id is None:
        for k in ('job_id', 'jobId', 'id'):
            if k in payload and payload.get(k) is not None:
                job_id = payload.pop(k)
                break
    if company_id is None:
        for k in ('company_id', 'companyId', 'company'):
            if k in payload and payload.get(k) is not None:
                company_id = payload.pop(k)
                break
    return company_id, job_id, payload


__all__ = [
    '_AURORA_TIME_FIELDS',
    '_CONDITIONAL_WRITE_ATTEMPTS',
    '_ORDER_FIELDS',
    '_PROGRESS_STORES',
    '_ProgressRecord',
    '_as_datetime',
    '_as_int',
    '_coerce_str',
    '_config_value',
    '_extract',
    '_first',
    '_is_conditional_failure',
    '_is_newer',
    '_is_table',
    '_maybe_await',
    '_norm',
    '_order_field',
    '_order_key',
    '_resolve_config',
    '_with_company_id',
]
