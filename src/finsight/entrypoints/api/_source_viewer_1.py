# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, S110, S112, B004, I001, F403, F405
from __future__ import annotations
import contextlib
import inspect
from typing import Any

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


from ._source_viewer_0 import *


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    if candidate is not None:
        if (
            callable(candidate)
            and not hasattr(candidate, 'execute')
            and not hasattr(candidate, 'view_original')
            and not hasattr(candidate, '__call__')
        ):
            try:
                candidate = candidate()
            except TypeError:
                try:
                    candidate = candidate(context)
                except TypeError:
                    with contextlib.suppress(TypeError):
                        candidate = candidate(
                            **{k: v for k, v in data.items() if not str(k).startswith('_')}
                        )
        if inspect.isawaitable(candidate):
            candidate = await candidate
        if _is_repository(candidate) or _is_use_case(candidate):
            return candidate
        for attr in (
            'source_viewer_use_case',
            'source_viewer',
            'source_view_use_case',
            'source_view',
            'view_source_use_case',
            'view_source',
            'use_case',
            'service',
            'handler',
            'orchestrator',
            'repository',
            'repo',
        ):
            if hasattr(candidate, attr):
                resolved = getattr(candidate, attr)
                if resolved is not None:
                    return await _resolve_use_case(resolved, data, context)
        return candidate

    # Fallback to composition.
    for getter_name in (
        'get_source_viewer_use_case',
        'get_source_view_use_case',
        'get_view_source_use_case',
    ):
        try:
            getter = globals().get(getter_name)
            if getter is None:
                import finsight.composition.source_viewer as comp

                getter = getattr(comp, getter_name, None)
            if getter is not None:
                resolved = getter(**{k: v for k, v in data.items() if not str(k).startswith('_')})
                if inspect.isawaitable(resolved):
                    resolved = await resolved
                if resolved is not None:
                    return resolved
        except Exception:
            continue
    try:
        if get_source_viewer_use_case is not None:
            resolved = get_source_viewer_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except Exception:
        pass
    # Final fallback: build from SourceViewer directly.
    try:
        from finsight.application.source_viewer import SourceViewer

        filtered = {k: v for k, v in data.items() if not str(k).startswith('_')}
        filtered.setdefault('request_context', context)
        return SourceViewer(**filtered)
    except Exception:
        return None


def _extract_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, Any, dict[str, Any]]:
    context = None
    use_case_candidate = None
    data: dict[str, Any] = {}

    working_kwargs = dict(kwargs)
    for key in list(working_kwargs):
        value = working_kwargs.pop(key)
        key_l = key.lower()
        if key_l in _CONTEXT_KEYS:
            if context is None:
                context = value
            else:
                data.update(_flatten(value))
        elif (
            key_l in _USE_CASE_KEYS
            or key_l.endswith('use_case')
            or key_l in ('service', 'factory', 'container', 'composition', 'app', 'handler')
        ):
            if use_case_candidate is None:
                use_case_candidate = value
            else:
                data.update(_flatten(value))
        elif key_l in _PAYLOAD_KEYS:
            if isinstance(value, dict):
                data.update(value)
            else:
                data.update(_flatten(value))
        elif key_l == 'config' or key_l.endswith('_config') or key_l == 'settings':
            data['config'] = value
        elif key_l == 'role':
            data['_role'] = value
        else:
            data[key] = value

    for value in args:
        if _is_context(value):
            if context is None:
                context = value
            else:
                data.update(_flatten(value))
        elif _is_repository(value) or _is_use_case(value):
            if use_case_candidate is None:
                use_case_candidate = value
            else:
                data.update(_flatten(value))
        elif isinstance(value, dict):
            data.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                data.update(flattened)
            else:
                data.setdefault('request_key', value)

    if isinstance(data, dict):
        for key in _CONTEXT_KEYS:
            if key in data and context is None:
                context = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        if 'config' in data and 'config' not in data:
            pass
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')
        if '_repository' in data and use_case_candidate is None:
            use_case_candidate = data.pop('_repository')

    # Preserve role
    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    return context, use_case_candidate, data


def _result_status(result: Any) -> str | None:
    if isinstance(result, dict):
        value = result.get('status')
        if value is None:
            value = result.get('outcome')
        if value is None:
            value = result.get('result')
        return None if value is None else str(value)
    value = _get(result, 'status', 'outcome', 'result')
    return None if value is None else str(value)


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict', None)):
        try:
            value = result.to_dict()
            if isinstance(value, dict):
                return dict(value)
        except Exception:
            pass
    output: dict[str, Any] = {}
    for attr in (
        'status',
        'document_id',
        'document_title',
        'title',
        'document_version',
        'version',
        'version_id',
        'page_number',
        'page',
        'content_type',
        'text',
        'table',
        'tables',
        'highlight',
        'needs_review',
        'newer_version_available',
        'newer_version_id',
        'original_available',
        'original_link',
        'original_url',
        'download_url',
        'signed_original_link',
        'citation',
        'citation_locator',
        'locator',
        'company_id',
        'user_id',
        'role',
        'trace_id',
        'outcome',
        'result',
    ):
        if hasattr(result, attr):
            value = getattr(result, attr, None)
            if value is not None or attr in {'text', 'table', 'tables', 'status'}:
                output[attr] = value
    if not output:
        try:
            output = dict(result)
        except Exception:
            output = {'value': result}
    return output


__all__ = ['_extract_context_and_data', '_resolve_use_case', '_result_status', '_result_to_dict']
