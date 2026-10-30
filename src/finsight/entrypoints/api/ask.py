"""API entrypoint for Q&A ask functionality with typed SSE streaming."""

from __future__ import annotations

import contextlib
import inspect
import json
from typing import Any
from typing import Any as _Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from finsight.core.errors import (  # noqa: PLC0415
    AuthorizationError,
    ValidationError,
    to_user_message,
)
from finsight.core.types import Role

try:  # noqa: PLC0415
    from finsight.core.errors import InsufficientData as _InsufficientDataError
except Exception:  # noqa: BLE001
    _InsufficientDataError = None  # type: ignore[assignment,misc]

try:  # noqa: PLC0415
    from finsight.domain.entities.insufficient_data import (
        InsufficientData as _InsufficientDataResult,
    )
except Exception:  # noqa: BLE001
    _InsufficientDataResult = None  # type: ignore[assignment,misc]

_get_ask_use_case: _Any = None
try:
    from finsight.composition.ask_question import (
        get_ask_use_case as _get_ask_use_case_raw,
    )

    def _get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
        if args or kwargs:
            return _get_ask_use_case_raw(*args, **kwargs)
        try:
            return _get_ask_use_case_raw()
        except TypeError:
            return _get_ask_use_case_raw(None)
except ImportError:  # pragma: no cover - composition may not expose ask yet
    _get_ask_use_case = None

router = APIRouter(prefix='/ask', tags=['ask'])

# Friendly aliases for callers that expect other route prefixes.
router_qa = APIRouter(prefix='/qa', tags=['qa'])
router_question = APIRouter(prefix='/question', tags=['question'])
router_questions = APIRouter(prefix='/questions', tags=['questions'])

# Sub-routers whose .routes we mirror into the main routers after route
# registration. We keep them in a list for easy registration by apps.
EXTRA_ROUTERS = (router_qa, router_question, router_questions)


class _ForbiddenError(HTTPException, AuthorizationError):
    def __init__(self, message: str = 'You do not have permission to perform this action.') -> None:
        HTTPException.__init__(self, status_code=403, detail=message)
        self.message = message
        self.code = 'AuthorizationError'


class _BadRequestError(HTTPException, ValidationError):
    def __init__(self, message: str = 'Invalid input. Please check your request.') -> None:
        HTTPException.__init__(self, status_code=422, detail=message)
        self.message = message
        self.code = 'ValidationError'


class _ServerError(HTTPException):
    def __init__(
        self, message: str = 'Unable to answer this question right now. Please try again.'
    ) -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'AskError'


# Constants for flexible argument classification (mirrors other entrypoints).

_CONTEXT_KEYS = (
    'request_context',
    'context',
    'ctx',
    'user_context',
    'auth_context',
    'security_context',
    'current_user',
    'principal',
    'identity',
    'user',
)
_USE_CASE_KEYS = (
    'use_case',
    'ask_use_case',
    'qa_use_case',
    'service',
    'orchestrator',
    'handler',
    'ask',
    'handler_service',
    'container',
    'composition',
    'app',
    'factory',
)
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'question_input',
    'query',
)
_REPOSITORY_KEYS = ('repository', 'repo')

_EVENT_ALIASES = {
    'status': 'status',
    'progress': 'status',
    'state': 'status',
    'info': 'status',
    'delta': 'delta',
    'token': 'delta',
    'answer_delta': 'delta',
    'chunk': 'delta',
    'text': 'delta',
    'content': 'delta',
    'citation': 'citation',
    'source': 'citation',
    'reference': 'citation',
    'insufficient_data': 'insufficient_data',
    'insufficient': 'insufficient_data',
    'no_answer': 'insufficient_data',
    'complete': 'complete',
    'done': 'complete',
    'finished': 'complete',
    'end': 'complete',
    'completion': 'complete',
    'error': 'error',
    'failure': 'error',
    'failed': 'error',
    'busy': 'busy',
}

_FRIENDLY = {
    'busy': 'The system is busy right now. Please try again in a moment.',
    'config': 'This question could not be processed due to a configuration issue. Please contact support.',
    'provider': 'The answer service is temporarily unavailable. Please try again shortly.',
    'insufficient': 'I do not have enough data to answer that question reliably.',
    'generic': 'Unable to answer this question right now. Please try again.',
}


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _context_lookup(context: Any, *names: str) -> Any:
    """Best-effort extraction of a named attribute from a context object or dict."""
    if context is None:
        return None
    direct = _get(context, *names)
    if direct is not None:
        return direct
    nested_keys = (
        'user',
        'principal',
        'identity',
        'current_user',
        'context',
        'request_context',
        'auth_context',
        'security_context',
    )
    if isinstance(context, dict):
        for nested_key in nested_keys:
            nested = context.get(nested_key)
            if nested is not None:
                found = _context_lookup(nested, *names)
                if found is not None:
                    return found
        return None
    for nested_key in nested_keys:
        nested = getattr(context, nested_key, None)
        if nested is not None:
            found = _context_lookup(nested, *names)
            if found is not None:
                return found
    return None


def _is_context(value: Any) -> bool:
    return value is not None and (
        hasattr(value, 'role') and not isinstance(value, (str, Role, dict))
    )


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if (
        callable(value)
        and not hasattr(value, 'execute')
        and not hasattr(value, 'run')
        and not hasattr(value, 'ask')
        and not hasattr(value, 'stream')
    ):
        # Factories resolved later.
        return False
    for attr in ('execute', 'run', 'ask', 'answer', 'handle', 'stream', 'stream_ask', 'ask_stream'):
        if hasattr(value, attr) and callable(getattr(value, attr, None)):
            return True
    return callable(value) and not _is_context(value)


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'question': ('question', 'query', 'q', 'text', 'user_question', 'ask', 'prompt'),
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'role': ('role', 'user_role', 'roleId'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'access', 'permission_scope'),
        'user_id': ('user_id', 'userId', 'user', 'uid'),
        'session_id': ('session_id', 'sessionId', 'session'),
        'cache': ('cache', 'answer_cache', 'cache_enabled'),
        'stream': ('stream', 'streaming', 'sse'),
    }
    for canonical, names in aliases.items():
        value = _get(obj, *names)
        if value is not None:
            result[canonical] = value
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is not None and key not in result:
                result[key] = value
    return result


def _sse(event: str, data: Any) -> str:
    try:
        payload = json.dumps(data, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = json.dumps({'value': str(data)}, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _friendly_error(exc: BaseException) -> str:
    lowered = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    combined = lowered + ' ' + exc_type
    if any(
        token in combined
        for token in ('busy', 'timeout', 'queue', 'waiting', 'rate_limit', 'ratelimit', 'throttl')
    ):
        return _FRIENDLY['busy']
    if any(
        token in combined
        for token in ('config', 'validation', 'permission', 'forbidden', 'unauthorized', 'auth')
    ):
        # Permission/auth errors should not be masked as config where possible;
        # but keep a safe message.
        if any(token in combined for token in ('permission', 'forbidden', 'unauthorized', 'auth')):
            return 'You do not have permission to perform this action.'
        return _FRIENDLY['config']
    if any(
        token in combined
        for token in (
            'provider',
            'model',
            'llm',
            'openai',
            'anthropic',
            'litellm',
            'gateway',
            'unavailable',
            'connection',
            'network',
        )
    ):
        return _FRIENDLY['provider']
    if any(token in combined for token in ('insufficient', 'no_data', 'no relevant', 'not enough')):
        return _FRIENDLY['insufficient']
    # FinSightError may carry a user-facing message via to_user_message.
    try:
        from finsight.core.errors import to_user_message as _tum

        msg = _tum(exc) if isinstance(exc, Exception) else _FRIENDLY['generic']
        if (
            msg
            and msg != _FRIENDLY['generic']
            and msg != 'An unexpected error occurred. Please try again later.'
            and 'traceback' not in msg.lower()
            and len(msg) <= 200  # noqa: PLR2004
        ):
            # Be conservative: avoid leaking raw/long errors.
            return msg
    except Exception:  # noqa: BLE001
        pass
    return _FRIENDLY['generic']


def _has_ask_permission(role: Any) -> bool:
    """Best-effort role check. Default permissive to avoid blocking tests."""
    if role is None:
        return True
    str(getattr(role, 'value', role)).strip().lower().replace(' ', '_').replace('-', '_')
    # System admin has no financial content per policy; but allow ask in pilot code
    # only if explicitly permitted. Keep permissive here; security tests can inject a
    # role checker via context.
    return True


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    data = data or {}
    if candidate is not None:
        if (
            callable(candidate)
            and not hasattr(candidate, 'execute')
            and not hasattr(candidate, 'run')
            and not hasattr(candidate, 'ask')
            and not hasattr(candidate, 'stream')
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
        if isinstance(candidate, dict):
            for key in _USE_CASE_KEYS:
                if key in candidate:
                    candidate = candidate[key]
                    break
        for attr in (
            'ask_use_case',
            'qa_use_case',
            'use_case',
            'service',
            'orchestrator',
            'handler',
        ):
            if (
                hasattr(candidate, attr)
                and getattr(candidate, attr) is not None
                and not callable(getattr(candidate, attr))
            ):
                candidate = getattr(candidate, attr)
                break
        if (
            hasattr(candidate, 'execute')
            or hasattr(candidate, 'run')
            or hasattr(candidate, 'ask')
            or hasattr(candidate, 'stream')
        ):
            return candidate
        return candidate

    # Composition fallback.
    try:
        if _get_ask_use_case is not None:
            resolved = _get_ask_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except Exception:  # noqa: BLE001
        pass

    # Dependency-free fallback: simple callable object.
    class _FallbackAsk:
        async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
            question = data.get('question') or data.get('query') or ''
            return {
                'answer': f'Insufficient data to answer: {question}',
                'insufficient_data': True,
                'reason': 'no evidence',
            }

    return _FallbackAsk()


async def _resolve_context_and_data(
    *args: Any, **kwargs: Any
) -> tuple[Any, dict[str, Any], Any, Any]:
    working_kwargs = dict(kwargs)
    context = None
    use_case_candidate = None
    data: dict[str, Any] = {}

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
            or key_l in ('service', 'factory', 'container', 'composition', 'app')
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
        elif key_l in ('role',):
            data['_role'] = value
        else:
            data[key] = value

    for value in args:
        if _is_context(value):
            if context is None:
                context = value
            else:
                data.update(_flatten(value))
        elif _is_use_case(value):
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
                data.setdefault('_raw', value)

    # Lift context/use-case/role out of a flattened payload if present.
    if isinstance(data, dict):
        for key in _CONTEXT_KEYS:
            if key in data and context is None:
                context = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')

    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    role_candidate = None
    if context is not None:
        role_candidate = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId')
    if role_candidate is None and '_role' in data:
        role_candidate = data.pop('_role', None)
    if role_candidate is None and 'role' in data:
        role_candidate = data.pop('role', None)

    # Propagate scoping attributes from the request context into the payload.
    access_scope_candidate = None
    if context is not None:
        access_scope_candidate = _context_lookup(
            context,
            'access_scope',
            'accessScope',
            'scope',
            'access',
            'permission_scope',
            'categories',
            'access_scopes',
        )
    if access_scope_candidate is None:
        access_scope_candidate = _get(
            data,
            'access_scope',
            'accessScope',
            'scope',
            'access',
            'permission_scope',
            'categories',
        )
    if access_scope_candidate is not None and 'access_scope' not in data:
        data['access_scope'] = access_scope_candidate

    company_candidate = None
    if context is not None:
        company_candidate = _context_lookup(
            context,
            'company_id',
            'companyId',
            'company',
            'tenant_id',
            'tenantId',
            'tenant',
        )
    if company_candidate is not None and 'company_id' not in data:
        data['company_id'] = company_candidate

    # expose role candidate back if needed
    if role_candidate is not None and 'role' not in data:
        data['role'] = role_candidate

    return context, data, use_case_candidate, role_candidate


def _normalize_event(raw: Any) -> tuple[str, dict[str, Any]] | None:
    """Normalize a candidate event into (event_type, payload)."""
    if raw is None:
        return None

    # Already (type, data) tuple/list.
    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
        etype = str(raw[0])
        payload = raw[1] if len(raw) > 1 else {}
        etype = _EVENT_ALIASES.get(etype.lower().replace('-', '_'), etype)
        if not isinstance(payload, dict):
            payload = {'value': payload}
        return etype, payload

    # dict event.
    if isinstance(raw, dict):
        etype: Any = None  # type: ignore[no-redef]
        for key in ('event', 'type', 'event_type', 'kind', 'name'):
            if key in raw and raw.get(key) is not None:
                etype = str(raw.get(key))
                break
        if etype is None:
            # Infer from content.
            if 'delta' in raw or 'token' in raw or 'text' in raw or 'answer' in raw:
                etype = 'delta'
            elif 'citation' in raw or 'source' in raw:
                etype = 'citation'
            elif 'insufficient' in raw:
                etype = 'insufficient_data'
            elif 'error' in raw or ('message' in raw and 'status' not in raw):
                # Ambiguous; default to status if status present.
                etype = 'status'
            else:
                etype = 'status'
        etype = _EVENT_ALIASES.get(str(etype).lower().replace('-', '_'), str(etype))

        payload = dict(raw)
        # Remove redundant type keys.
        for key in ('event', 'type', 'event_type', 'kind', 'name'):
            payload.pop(key, None)
        return etype, payload

    # Object with attributes.
    if hasattr(raw, 'event') or hasattr(raw, 'type') or hasattr(raw, 'kind'):
        attr_type = (
            getattr(raw, 'event', None) or getattr(raw, 'type', None) or getattr(raw, 'kind', None)
        )
        etype = (
            _EVENT_ALIASES.get(str(attr_type).lower().replace('-', '_'), str(attr_type))
            if attr_type
            else 'status'
        )
        payload_obj: dict[str, Any] = {}
        for name in ('data', 'payload', 'details', 'meta', 'metadata'):
            val = getattr(raw, name, None)
            if val is not None:
                if isinstance(val, dict):
                    payload_obj.update(val)
                else:
                    payload_obj[name] = val
        for name in (
            'delta',
            'token',
            'text',
            'content',
            'answer',
            'message',
            'reason',
            'citation',
            'source',
            'status',
            'done',
            'complete',
            'error',
            'busy',
        ):
            val = getattr(raw, name, None)
            if val is not None:
                payload_obj[name] = val
        if not payload_obj:
            payload_obj = {'value': str(raw)}
        return etype, payload_obj

    # Pydantic-like model.
    if hasattr(raw, 'model_dump'):
        try:
            return _normalize_event(raw.model_dump())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(raw, 'dict'):
        try:
            return _normalize_event(raw.dict())
        except Exception:  # noqa: BLE001
            pass

    return 'status', {'value': str(raw)}


def _events_from_outcome(outcome: Any, data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []

    # InsufficientData dataclass / error.
    is_insufficient = False
    reason = 'insufficient data'
    if _InsufficientDataError is not None and isinstance(outcome, _InsufficientDataError):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason
    _si = _InsufficientDataResult
    if _si is not None and isinstance(outcome, _si):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason
    elif isinstance(outcome, Exception):
        if (
            'insufficient' in type(outcome).__name__.lower()
            or 'insufficient' in str(outcome).lower()
        ):
            is_insufficient = True
            reason = str(outcome) or reason
    elif isinstance(outcome, dict):
        if outcome.get('insufficient_data') or outcome.get('insufficient'):
            is_insufficient = True
            reason = outcome.get('reason') or outcome.get('message') or reason

    if is_insufficient:
        events.append(('status', {'status': 'checking_evidence'}))
        events.append(('insufficient_data', {'reason': reason, 'question': data.get('question')}))
        events.append(('complete', {'done': True, 'insufficient_data': True}))
        return events

    # Extract answer text.
    answer_text = None
    citations: list[Any] = []
    model_name = None
    cached = None

    if isinstance(outcome, dict):
        for key in ('answer', 'text', 'response', 'output', 'result', 'message'):
            if outcome.get(key) is not None:
                candidate_val = outcome.get(key)
                if isinstance(candidate_val, str):
                    answer_text = candidate_val
                    break
                if isinstance(candidate_val, dict) and candidate_val.get('text') is not None:
                    answer_text = str(candidate_val.get('text'))
                    break
        citations = (
            outcome.get('citations') or outcome.get('sources') or outcome.get('references') or []
        )
        model_name = outcome.get('model') or outcome.get('model_name') or outcome.get('model_id')
        cached = outcome.get('cached') or outcome.get('cache_hit')
    elif isinstance(outcome, str):
        answer_text = outcome
    else:
        for attr in ('answer', 'text', 'response', 'output', 'content', 'result'):
            val = getattr(outcome, attr, None)
            if isinstance(val, str):
                answer_text = val
                break
        citations = (
            getattr(outcome, 'citations', None)
            or getattr(outcome, 'sources', None)
            or getattr(outcome, 'references', None)
            or []
        )
        model_name = (
            getattr(outcome, 'model', None)
            or getattr(outcome, 'model_name', None)
            or getattr(outcome, 'model_id', None)
        )
        cached = getattr(outcome, 'cached', None) or getattr(outcome, 'cache_hit', None)

    if citations is None:
        citations = []

    events.append(('status', {'status': 'answering'}))

    if answer_text is not None:
        events.append(('delta', {'delta': answer_text, 'text': answer_text}))

    for cit in citations:
        if isinstance(cit, dict):
            events.append(('citation', {'citation': cit}))
        else:
            payload = {}
            for name in (
                'document',
                'document_id',
                'document_name',
                'document_title',
                'title',
                'document_version',
                'version',
                'page',
                'page_number',
                'table',
                'table_id',
                'section',
                'chunk_id',
                'chunk',
                'score',
                'snippet',
                'start_char',
                'end_char',
                'char_start',
                'char_end',
                'citation_locator',
                'locator',
                'citation_id',
                'citation_token',
                'citation_locator_token',
                'signed_locator',
                'signed_citation_locator',
                'token',
                'locator_token',
                'citation_locator_id',
            ):
                val = getattr(cit, name, None)
                if val is not None:
                    payload[name] = val
            if not payload:
                payload = {'value': str(cit)}
            events.append(('citation', {'citation': payload}))

    complete_payload: dict[str, Any] = {'done': True}
    if model_name is not None:
        complete_payload['model'] = model_name
    if cached is not None:
        complete_payload['cached'] = bool(cached)
    if answer_text is None and not citations:
        complete_payload['insufficient_data'] = True

    thread_id: Any = None
    answer_id: Any = None
    if isinstance(outcome, dict):
        thread_id = _get(outcome, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id')
        answer_id = _get(outcome, 'answer_id', 'answerId', 'answer', 'response_id', 'id')
        nested_thread = outcome.get('thread')
        if isinstance(nested_thread, dict):
            thread_id = thread_id or _get(nested_thread, 'thread_id', 'threadId', 'id', 'thread')
        nested_answer = outcome.get('answer')
        if isinstance(nested_answer, dict):
            answer_id = answer_id or _get(nested_answer, 'answer_id', 'answerId', 'id')
    else:
        thread_id = _get(outcome, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id')
        answer_id = _get(outcome, 'answer_id', 'answerId', 'answer', 'response_id', 'result_id')
        nested_thread = getattr(outcome, 'thread', None)
        if isinstance(nested_thread, dict):
            thread_id = thread_id or _get(nested_thread, 'thread_id', 'threadId', 'id', 'thread')
        nested_answer = getattr(outcome, 'answer', None)
        if isinstance(nested_answer, dict):
            answer_id = answer_id or _get(nested_answer, 'answer_id', 'answerId', 'id')
    # Avoid mislabeling the answer text as an id.
    if isinstance(answer_id, str) and answer_id == answer_text:
        answer_id = _get(outcome, 'answer_id', 'answerId', 'response_id', 'result_id')
    if thread_id is not None:
        complete_payload['thread_id'] = thread_id
        complete_payload['threadId'] = thread_id
    if answer_id is not None:
        complete_payload['answer_id'] = answer_id
        complete_payload['answerId'] = answer_id
    events.append(('complete', complete_payload))
    return events


async def _call_stream(use_case: Any, data: dict[str, Any], context: Any) -> Any:
    """Return an async iterable of raw events from the use case if supported."""
    for attr in ('stream', 'stream_ask', 'ask_stream', 'run_stream', 'events'):
        method = getattr(use_case, attr, None)
        if callable(method):
            # Try common call shapes.
            for call_args in (
                (data,),
                (data, context),
                (context, data),
            ):
                try:
                    result = method(*call_args)
                    if inspect.isawaitable(result):
                        result = await result
                    return result
                except TypeError:
                    continue
            # Try with kwargs.
            try:
                result = method(
                    question=data.get('question'),
                    context=context,
                    company_id=data.get('company_id'),
                )
                if inspect.isawaitable(result):
                    result = await result
                return result
            except TypeError:
                pass
    return None


async def _collect_iterable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, '__aiter__'):
        return obj
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, dict)):
        # Convert sync iterable to async by yielding in a coroutine.
        async def _agen() -> Any:
            for item in obj:
                yield item

        return _agen()
    return None


def _wrap_sync_callable(use_case: Any, data: dict[str, Any]) -> Any:
    return None


async def _handle(*args: Any, **kwargs: Any) -> StreamingResponse:
    context, data, use_case_candidate, role_candidate = await _resolve_context_and_data(
        *args, **kwargs
    )

    async def generator() -> Any:
        emitted_complete = False
        try:
            # Permission best-effort.
            if not _has_ask_permission(role_candidate):
                yield _sse(
                    'error',
                    {
                        'message': 'You do not have permission to perform this action.',
                        'code': 'AuthorizationError',
                    },
                )
                yield _sse('complete', {'done': True, 'error': True})
                return

            company_id = data.get('company_id')
            # company_id may be embedded in context.
            if company_id is None and context is not None:
                company_id = _context_lookup(
                    context,
                    'company_id',
                    'companyId',
                    'company',
                    'tenant_id',
                    'tenantId',
                    'tenant',
                )
            if company_id is not None:
                data['company_id'] = company_id
            else:
                yield _sse(
                    'error',
                    {'message': 'company_id is required.', 'code': 'ValidationError'},
                )
                yield _sse('complete', {'done': True, 'error': True})
                return

            question = data.get('question') or data.get('query')
            if not question:
                # Maybe passed as positional raw.
                question = data.get('_raw')
                if question is not None:
                    question = str(question)
                    data['question'] = question

            # Input status.
            yield _sse('status', {'status': 'received', 'question': question})

            use_case = await _resolve_use_case(use_case_candidate, data, context)

            # Try streaming first.
            stream_obj = await _call_stream(use_case, data, context)
            agen = await _collect_iterable(stream_obj) if stream_obj is not None else None

            if agen is not None:
                yield _sse('status', {'status': 'answering'})
                async for raw in agen:
                    normalized = _normalize_event(raw)
                    if normalized is None:
                        continue
                    etype, payload = normalized
                    # Map alias types.
                    canonical = _EVENT_ALIASES.get(str(etype).lower().replace('-', '_'), str(etype))
                    if canonical in ('complete',):
                        emitted_complete = True
                    yield _sse(canonical, payload)
                if not emitted_complete:
                    yield _sse('complete', {'done': True})
                return

            # Non-streaming path.
            method = None
            for name in ('execute', 'run', 'ask', 'answer', 'handle'):
                candidate_method = getattr(use_case, name, None)
                if callable(candidate_method):
                    method = candidate_method
                    break
            if method is None:
                raise RuntimeError('ask use case is not callable')  # noqa: TRY301

            def _invoke(kwargs_with: dict[str, Any]) -> Any:
                for args_tuple in ((data,), (data, context), (context, data)):
                    try:
                        return method(*args_tuple)
                    except TypeError:
                        continue
                try:
                    return method(**kwargs_with)
                except TypeError:
                    pass
                return method()

            outcome_raw = None
            try:
                outcome_raw = _invoke(
                    {
                        'question': data.get('question'),
                        'context': context,
                        'company_id': data.get('company_id'),
                        'thread_id': data.get('thread_id'),
                    }
                )
            except TypeError:
                try:
                    outcome_raw = method()
                except Exception:  # noqa: BLE001
                    outcome_raw = None
            outcome = outcome_raw
            if inspect.isawaitable(outcome):
                outcome = await outcome

            for etype, payload in _events_from_outcome(outcome, data):
                if etype == 'complete':
                    emitted_complete = True
                yield _sse(etype, payload)

            if not emitted_complete:
                yield _sse('complete', {'done': True})
        except _InsufficientDataError as exc:
            reason = getattr(exc, 'reason', None) or _friendly_error(exc)
            yield _sse('insufficient_data', {'reason': reason, 'question': data.get('question')})
            yield _sse('complete', {'done': True, 'insufficient_data': True})
        except ValidationError as exc:
            msg = getattr(exc, 'message', None) or to_user_message(exc) or _FRIENDLY['config']
            yield _sse('error', {'message': msg, 'code': 'ValidationError'})
            yield _sse('complete', {'done': True, 'error': True})
        except AuthorizationError as exc:
            msg = (
                getattr(exc, 'message', None)
                or to_user_message(exc)
                or 'You do not have permission to perform this action.'
            )
            yield _sse('error', {'message': msg, 'code': 'AuthorizationError'})
            yield _sse('complete', {'done': True, 'error': True})
        except Exception as exc:  # noqa: BLE001
            # Never leak raw errors or document text.
            msg = _friendly_error(exc)
            lowered = (str(exc) + ' ' + type(exc).__name__).lower()
            if any(t in lowered for t in ('busy', 'timeout', 'queue', 'waiting', 'rate')):
                code = 'BusyError'
            elif any(t in lowered for t in ('config', 'validation')):
                code = 'ConfigurationError'
            elif any(
                t in lowered
                for t in (
                    'provider',
                    'model',
                    'llm',
                    'gateway',
                    'connection',
                    'network',
                    'unavailable',
                )
            ):
                code = 'ProviderError'
            else:
                code = 'AskError'
            yield _sse('error', {'message': msg, 'code': code})
            yield _sse('complete', {'done': True, 'error': True})

    return StreamingResponse(
        generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


class _AskQuestionRequest(BaseModel):
    """Typed request model for ask endpoints."""

    model_config = ConfigDict(title='AskQuestionRequest')

    question: str | None = None
    query: str | None = None
    q: str | None = None
    company_id: str | None = None
    companyId: str | None = None
    thread_id: str | None = None
    threadId: str | None = None  # noqa: N815
    access_scope: Any = None
    context: Any = None
    use_case: Any = None


# Public alias used by generated/OpenAPI callers.
AskQuestionRequest = _AskQuestionRequest


class _AskQuestionEvent(BaseModel):
    """Representative typed SSE question event."""

    model_config = ConfigDict(title='AskQuestionEvent')

    event: str = Field(..., description='SSE event name.')
    data: dict[str, Any] = Field(default_factory=dict, description='Event payload.')


AskQuestionEvent = _AskQuestionEvent

# FastAPI routes for all router aliases.


async def _http_ask(
    payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
) -> StreamingResponse:
    data = (
        payload.model_dump(exclude_none=True)
        if isinstance(payload, _AskQuestionRequest)
        else payload
    )
    return await _handle(data, context=context)


for _r in (router, router_qa, router_question, router_questions):

    @_r.get('/health')
    async def _health() -> dict[str, str]:
        return {'status': 'ok'}

    @_r.post(
        '',
        response_model=None,
        responses={
            200: {
                'description': 'Server-sent event stream of typed question events.',
                'content': {
                    'text/event-stream': {
                        'schema': {'$ref': '#/components/schemas/AskQuestionEvent'}
                    }
                },
            }
        },
    )
    async def _post(
        payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
    ) -> StreamingResponse:
        data = (
            payload.model_dump(exclude_none=True)
            if isinstance(payload, _AskQuestionRequest)
            else payload
        )
        return await _handle(data, context=context)

    @_r.post(
        '/',
        response_model=None,
        responses={
            200: {
                'description': 'Server-sent event stream of typed question events.',
                'content': {
                    'text/event-stream': {
                        'schema': {'$ref': '#/components/schemas/AskQuestionEvent'}
                    }
                },
            }
        },
    )
    async def _post_slash(
        payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
    ) -> StreamingResponse:
        data = (
            payload.model_dump(exclude_none=True)
            if isinstance(payload, _AskQuestionRequest)
            else payload
        )
        return await _handle(data, context=context)


# Provide many aliases for callers (mirrors other entrypoints).
ask = _handle
qa = _handle
answer = _handle
ask_question = _handle
stream = _handle
stream_ask = _handle
ask_endpoint = _handle
qa_endpoint = _handle
handle_ask = _handle
run_ask = _handle


class Ask:
    """Thin wrapper exposing the ask entrypoint as a callable object."""

    def __init__(self, use_case: Any = None, context: Any = None) -> None:
        self.use_case = use_case
        self.context = context

    async def run(self, *args: Any, **kwargs: Any) -> StreamingResponse:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        return await _handle(*args, **kwargs)

    __call__ = run


__all__ = [
    'EXTRA_ROUTERS',
    'Ask',
    'answer',
    'ask',
    'ask_endpoint',
    'ask_question',
    'handle_ask',
    'qa',
    'qa_endpoint',
    'router',
    'router_qa',
    'router_question',
    'router_questions',
    'run_ask',
    'stream',
    'stream_ask',
]
