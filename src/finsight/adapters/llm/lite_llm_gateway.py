# ruff: noqa: BLE001, ANN401, PLR0911, PLR0912, PLR0915, PLR2004, TRY300, S110, RUF059, RUF006, ARG004, PLC0415
"""LiteLLM-backed model gateway with failover, backup requests, and metering."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from finsight.domain.ports.llm_gateway import LLMGateway as LLMGatewayPort

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_LOGGER = logging.getLogger(__name__)

_litellm_module: Any
try:
    import litellm as _litellm_module
except Exception:  # pragma: no cover
    _litellm_module = None

_ORIGINAL_ACOMPLETION = (
    getattr(_litellm_module, 'acompletion', None) if _litellm_module is not None else None
)
acompletion = _ORIGINAL_ACOMPLETION
litellm_acompletion = _ORIGINAL_ACOMPLETION


class _GatewayStreamChunk(str):
    def __init__(self, text: str, **metadata: Any) -> None:
        super().__init__()
        self._text = text
        self._metadata = dict(metadata)
        self._metadata.setdefault('content', text)
        self._metadata.setdefault('text', text)
        self._metadata.setdefault('delta', text)
        self._metadata.setdefault('type', 'delta')

    def __new__(cls, text: str, **metadata: Any) -> _GatewayStreamChunk:
        return super().__new__(cls, text)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return self._metadata.get(key)
        return super().__getitem__(key)

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._metadata:
            return self._metadata[name]
        raise AttributeError(name)

    def get(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    @property
    def content(self) -> str:
        return str(self._metadata.get('content', self._text))

    @property
    def text(self) -> str:
        return self._text


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'switches') or hasattr(arg, 'llm') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return kwargs.get('llm_config') or kwargs.get('model_config')


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _as_model_dict(model: Any) -> dict[str, Any]:
    if isinstance(model, dict):
        return dict(model)
    if isinstance(model, str):
        return {'model_id': model}
    result: dict[str, Any] = {}
    for attr in (
        'model_id',
        'id',
        'name',
        'model',
        'provider',
        'max_tokens',
        'temperature',
        'timeout_seconds',
        'max_retries',
        'retry_base_delay_seconds',
    ):
        if hasattr(model, attr):
            value = getattr(model, attr)
            if value is not None:
                result[attr] = value
    if not result and model is not None:
        result['model_id'] = str(model)
    return result


def _resolve_acompletion() -> Callable[..., Any]:
    litellm_fn = None
    if _litellm_module is not None:
        litellm_fn = getattr(_litellm_module, 'acompletion', None)
    module_fn = acompletion
    if module_fn is not None and module_fn is not _ORIGINAL_ACOMPLETION:
        return cast('Callable[..., Any]', module_fn)
    try:
        import finsight.adapters.llm.litellm_gateway as _alias_module

        alias_fn = getattr(_alias_module, 'acompletion', None)
        if alias_fn is not None and alias_fn is not _ORIGINAL_ACOMPLETION:
            return cast('Callable[..., Any]', alias_fn)
    except Exception:
        pass
    if litellm_fn is not None:
        return cast('Callable[..., Any]', litellm_fn)
    if module_fn is not None:
        return cast('Callable[..., Any]', module_fn)
    completion_fn = getattr(_litellm_module, 'completion', None) if _litellm_module else None
    if completion_fn is not None:

        async def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return completion_fn(*args, **kwargs)

        return _wrapped
    raise RuntimeError('litellm acompletion is unavailable')


def _build_messages(**kwargs: Any) -> list[dict[str, Any]]:
    messages = kwargs.get('messages')
    if messages is not None:
        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        if isinstance(messages, (list, tuple)):
            normalized = []
            for item in messages:
                if isinstance(item, dict):
                    normalized.append(dict(item))
                else:
                    normalized.append({'role': 'user', 'content': str(item)})
            if normalized:
                return normalized
    prompt = kwargs.get('prompt')
    if prompt is None:
        prompt = kwargs.get('input', kwargs.get('text', kwargs.get('query')))
    question = kwargs.get('question')
    if question is None:
        question = prompt
    calculations = kwargs.get('calculations')
    chunks = kwargs.get('chunks')
    chunks_text = None
    if chunks is not None:
        if isinstance(chunks, (list, tuple)):
            chunks_text = '\n'.join(str(item) for item in chunks)
        else:
            chunks_text = str(chunks)
    instructions = kwargs.get('instructions')
    if instructions is None:
        instructions = kwargs.get('system_prompt')
    if instructions is None:
        instructions = 'You are a helpful assistant.'
    system = kwargs.get('system')
    parts: list[str] = [str(instructions)]
    if calculations not in (None, ''):
        parts.append(str(calculations))
    if chunks_text not in (None, ''):
        parts.append(str(chunks_text))
    if question not in (None, ''):
        parts.append(str(question))
    if system not in (None, ''):
        parts.insert(0, str(system))
    content = '\n\n'.join(part for part in parts if str(part).strip())
    if not content:
        content = str(question if question is not None else (prompt or ''))
    result_messages: list[dict[str, Any]] = []
    if system not in (None, '') and instructions and str(instructions) not in str(system):
        result_messages.append({'role': 'system', 'content': str(instructions)})
    result_messages.append({'role': 'user', 'content': content})
    return result_messages


class LiteLLMGateway(LLMGatewayPort):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)
        self.company_id_default: Any = kwargs.get('company_id')

        raw_backup_enabled = _first(
            kwargs,
            'backup_request_enabled',
            'backup_requests_enabled',
            'backup_enabled',
            default=None,
        )
        if raw_backup_enabled is None:
            switches = _first(kwargs, 'switches', default=None)
            if switches is None and self.config is not None:
                switches = getattr(self.config, 'switches', None)
            if isinstance(switches, dict):
                raw_backup_enabled = switches.get('backup_request_enabled')
            else:
                raw_backup_enabled = getattr(switches, 'backup_request_enabled', None)
        if raw_backup_enabled is None and self.config is not None:
            raw_backup_enabled = getattr(self.config, 'backup_request_enabled', None)
        self.backup_enabled = True if raw_backup_enabled is None else bool(raw_backup_enabled)

        prompt_cache = _first(kwargs, 'prompt_cache_enabled', default=None)
        if prompt_cache is None:
            switches = _first(kwargs, 'switches', default=None)
            if switches is None and self.config is not None:
                switches = getattr(self.config, 'switches', None)
            if isinstance(switches, dict):
                prompt_cache = switches.get('prompt_cache_enabled')
            elif switches is not None:
                prompt_cache = getattr(switches, 'prompt_cache_enabled', None)
        if prompt_cache is None and self.config is not None:
            prompt_cache = getattr(self.config, 'prompt_cache_enabled', True)
        self.prompt_cache_enabled = True if prompt_cache is None else bool(prompt_cache)

        timeout_default = _first(kwargs, 'timeout_seconds', 'timeout', default=None)
        if timeout_default is None and self.config is not None:
            timeout_default = getattr(self.config, 'timeout_seconds', None)
        self.timeout = int(timeout_default) if timeout_default is not None else 30

        first_timeout = _first(
            kwargs,
            'first_token_timeout_seconds',
            'first_word_timeout_seconds',
            'first_token_timeout',
            'first_word_timeout',
            default=None,
        )
        if first_timeout is None and self.config is not None:
            first_timeout = getattr(self.config, 'first_token_timeout_seconds', None)
            if first_timeout is None:
                first_timeout = getattr(self.config, 'first_word_timeout_seconds', None)
        self.first_token_timeout = float(first_timeout) if first_timeout is not None else 4.0

        backup_delay = _first(
            kwargs,
            'backup_request_after_seconds',
            'backup_request_delay_seconds',
            'backup_delay_seconds',
            'backup_after_seconds',
            default=2.5,
        )
        self.backup_delay = float(backup_delay)

        instructions = _first(kwargs, 'instructions', 'system_prompt', 'system', default=None)
        self.instructions = (
            instructions if instructions is not None else 'You are a helpful assistant.'
        )

        self.metering = _first(
            kwargs,
            'metering',
            'meter',
            'metering_service',
            'usage_meter',
            'usage_recorder',
            'record_usage',
            'metric_recorder',
            default=None,
        )
        self.on_fallback_3 = _first(
            kwargs,
            'on_fallback_3',
            'fallback_3_callback',
            'fallback_3_alert',
            'alert',
            'alert_callback',
            'notify',
            default=None,
        )
        self.logger = _first(kwargs, 'logger', default=_LOGGER)
        self.completion_func = _first(
            kwargs, 'completion_func', 'acompletion', 'completion', 'llm_func', default=None
        )
        self.fallback_3_used = False
        self._tags: list[dict[str, Any]] = []
        self._last_trace: dict[str, Any] = {}
        self.usage_rows: list[dict[str, Any]] = []
        self._usage_lock = asyncio.Lock()

        self.chains: dict[str, list[dict[str, Any]]] = {}
        models_kw = kwargs.get('models')
        if isinstance(models_kw, dict):
            for key, value in models_kw.items():
                if isinstance(value, (list, tuple)):
                    self.chains[str(key)] = [_as_model_dict(item) for item in value]
        elif isinstance(models_kw, (list, tuple)):
            self.chains['primary'] = [_as_model_dict(item) for item in models_kw]

        primary_model = _first(kwargs, 'primary_model', default=None)
        fallback_models = _first(
            kwargs, 'fallback_models', 'fallbacks', 'primary_fallbacks', default=None
        )
        if primary_model is not None:
            chain = [_as_model_dict(primary_model)]
            if isinstance(fallback_models, (list, tuple)):
                chain.extend(_as_model_dict(item) for item in fallback_models)
            self.chains.setdefault('primary', chain)

        cheap_primary = _first(kwargs, 'cheap_model', 'cheap_primary_model', default=None)
        cheap_fallbacks = _first(kwargs, 'cheap_fallback_models', 'cheap_fallbacks', default=None)
        if cheap_primary is not None:
            chain = [_as_model_dict(cheap_primary)]
            if isinstance(cheap_fallbacks, (list, tuple)):
                chain.extend(_as_model_dict(item) for item in cheap_fallbacks)
            self.chains['cheap'] = chain

        if self.config is not None:
            llm_cfg = getattr(self.config, 'llm', None)
            if llm_cfg is None:
                llm_cfg = getattr(self.config, 'llm_config', None)
            if llm_cfg is None:
                llm_cfg = self.config if hasattr(self.config, 'primary_model') else None
            if llm_cfg is not None and 'primary' not in self.chains:
                pm = getattr(llm_cfg, 'primary_model', None)
                fms = getattr(llm_cfg, 'fallback_models', None)
                if pm is not None:
                    chain = [_as_model_dict(pm)]
                    if isinstance(fms, (list, tuple)):
                        chain.extend(_as_model_dict(item) for item in fms)
                    self.chains.setdefault('primary', chain)
            if llm_cfg is not None and 'cheap' not in self.chains:
                cm = getattr(llm_cfg, 'cheap_model', None)
                cfms = getattr(llm_cfg, 'cheap_fallback_models', None)
                if cm is not None:
                    chain = [_as_model_dict(cm)]
                    if isinstance(cfms, (list, tuple)):
                        chain.extend(_as_model_dict(item) for item in cfms)
                    self.chains['cheap'] = chain

        single_model = _first(kwargs, 'model', 'model_id', default=None)
        if not self.chains and single_model is not None:
            self.chains['primary'] = [_as_model_dict(single_model)]

        if not self.chains:
            self.chains['primary'] = [
                {
                    'model_id': 'default',
                    'max_tokens': 1024,
                    'temperature': 0.0,
                    'timeout_seconds': self.timeout,
                    'max_retries': 0,
                    'retry_base_delay_seconds': 1.0,
                }
            ]

        self.default_chain_name = 'primary' if 'primary' in self.chains else next(iter(self.chains))

    def _choose_chain(self, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        chain_name = kwargs.get('chain') or kwargs.get('model_chain') or kwargs.get('chain_name')
        if chain_name is not None and str(chain_name) in self.chains:
            return list(self.chains[str(chain_name)])
        if (
            kwargs.get('cheap') or kwargs.get('use_cheap') or kwargs.get('cheap_mode')
        ) and 'cheap' in self.chains:
            return list(self.chains['cheap'])
        has_calculation = bool(kwargs.get('has_calculation') or kwargs.get('calculation_intent'))
        if has_calculation and 'primary' in self.chains:
            return list(self.chains['primary'])
        estimated_size = kwargs.get('estimated_input_tokens') or kwargs.get('input_size')
        if (
            isinstance(estimated_size, (int, float))
            and estimated_size > 4000
            and 'primary' in self.chains
        ):
            return list(self.chains['primary'])
        route = kwargs.get('route') or kwargs.get('model_route')
        if isinstance(route, str) and route in self.chains:
            return list(self.chains[route])
        return list(self.chains.get(self.default_chain_name, next(iter(self.chains.values()))))

    def _extract_company_id(self, value: Any, kwargs: dict[str, Any]) -> Any:
        if value is not None:
            return value
        if kwargs.get('company_id') is not None:
            return kwargs.get('company_id')
        if self.company_id_default is not None:
            return self.company_id_default
        return kwargs.get('tenant_id') or kwargs.get('company') or 'unknown'

    async def _record_usage(
        self, model_id: str, company_id: Any, trace_id: Any = None, units: int = 1
    ) -> None:
        row = {
            'company_id': company_id,
            'service': 'llm',
            'units': units,
            'estimated_cost': None,
            'model': model_id,
            'model_name': model_id,
            'trace_id': trace_id,
            'trace': trace_id,
        }
        async with self._usage_lock:
            self.usage_rows.append(row)
        await self._invoke_metering(row)

    async def _invoke_metering(self, row: dict[str, Any]) -> None:
        target = self.metering
        if target is None:
            return
        if (
            callable(target)
            and not hasattr(target, 'record_usage')
            and not hasattr(target, 'record')
        ):
            try:
                result = target(row)
                if inspect.isawaitable(result):
                    await result
                return
            except Exception:
                _LOGGER.debug('metering callable failed', exc_info=True)
        method = None
        for name in (
            'record_usage',
            'record',
            'usage',
            'track_usage',
            'write_usage',
            'meter',
            'meter_call',
            'on_usage',
        ):
            candidate = getattr(target, name, None)
            if callable(candidate):
                method = candidate
                break
        if method is None:
            return
        attempts = [
            lambda m=method, r=row: m(
                company_id=r['company_id'],
                service='llm',
                model=r['model'],
                model_name=r['model'],
                units=r['units'],
                estimated_cost=r['estimated_cost'],
                trace_id=r['trace_id'],
                trace=r['trace_id'],
                usage=r,
                row=r,
            ),
            lambda m=method, r=row: m(r),
            lambda m=method, r=row: m(
                r['company_id'], 'llm', r['units'], None, r['model'], r['trace_id']
            ),
        ]
        for attempt in attempts:
            try:
                result = attempt()  # type: ignore[no-untyped-call]
                if inspect.isawaitable(result):
                    await result
                return
            except TypeError:
                continue
            except Exception:
                _LOGGER.debug('metering method failed', exc_info=True)
                return

    def _alert_fallback_3(self, model_id: str, company_id: Any) -> None:
        self.fallback_3_used = True
        self._last_trace['fallback_3_used'] = True
        self._last_trace['fallback_3_model'] = model_id
        self._tags.append({'tag': 'fallback_3_used', 'model': model_id})
        callback = self.on_fallback_3
        if callable(callback):
            try:
                result = callback(model_id, company_id=company_id, tag='fallback_3_used')
                if inspect.isawaitable(result):
                    asyncio.ensure_future(result)
            except Exception:
                _LOGGER.debug('fallback 3 alert callback failed', exc_info=True)
            return
        try:
            self.logger.warning(
                'Fallback 3 used: %s', model_id, extra={'tag': 'fallback_3_used', 'model': model_id}
            )
        except Exception:
            _LOGGER.warning('Fallback 3 used: %s', model_id)

    async def _open_stream(
        self, model: dict[str, Any], messages: list[dict[str, Any]], params: dict[str, Any]
    ) -> tuple[dict[str, Any], AsyncIterator[Any] | None, Any, Exception | None]:
        retries = int(model.get('max_retries', 0) or 0)
        delay = float(model.get('retry_base_delay_seconds', 1.0) or 0.0)
        timeout = float(model.get('timeout_seconds', self.timeout) or self.timeout)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                fn = self.completion_func
                if not callable(fn):
                    fn = _resolve_acompletion()
                kwargs: dict[str, Any] = {
                    'model': model.get('model_id') or model.get('model'),
                    'messages': messages,
                    'stream': True,
                    'max_tokens': model.get('max_tokens'),
                    'temperature': model.get('temperature'),
                    'timeout': timeout,
                }
                if self.prompt_cache_enabled:
                    kwargs.setdefault('stream_options', {'include_usage': True})
                result = (
                    fn(**kwargs)
                    if not params
                    else fn(**{**kwargs, **{k: v for k, v in params.items() if k not in kwargs}})
                )
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, (list, tuple)):

                    async def _from_list(items: list[Any]) -> AsyncIterator[Any]:
                        for item in items:
                            yield item

                    stream = _from_list(list(result))
                elif hasattr(result, '__aiter__') or hasattr(result, '__anext__'):
                    stream = result
                else:

                    async def _single(value: Any) -> AsyncIterator[Any]:
                        yield value

                    stream = _single(result)
                first = await asyncio.wait_for(stream.__anext__(), timeout=self.first_token_timeout)
                return model, stream, first, None
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    await asyncio.sleep(delay)
        return (
            model,
            None,
            None,
            (last_error if last_error is not None else RuntimeError('unknown error')),
        )

    async def _attempt_step(
        self,
        primary_model: dict[str, Any],
        backup_model: dict[str, Any] | None,
        messages: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], AsyncIterator[Any], Any] | None:
        loop_start = time.monotonic()
        primary_task = asyncio.create_task(self._open_stream(primary_model, messages, params))
        backup_task: asyncio.Task[Any] | None = None
        if backup_model is not None and self.backup_enabled:

            async def delayed_backup() -> Any:
                await asyncio.sleep(self.backup_delay)
                return await self._open_stream(backup_model, messages, params)

            backup_task = asyncio.create_task(delayed_backup())
        tasks: dict[asyncio.Task[Any], tuple[str, dict[str, Any]]] = {
            primary_task: ('primary', primary_model)
        }
        if backup_task is not None:
            tasks[backup_task] = ('backup', backup_model)  # type: ignore[assignment]
        winner_model: dict[str, Any] | None = None
        winner_stream: AsyncIterator[Any] | None = None
        winner_first: Any = None
        while tasks:
            remaining = self.first_token_timeout - (time.monotonic() - loop_start)
            if remaining <= 0:
                for task in list(tasks):
                    task.cancel()
                break
            done, pending = await asyncio.wait(
                set(tasks), timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                for task in list(tasks):
                    task.cancel()
                break
            for task in done:
                label, model = tasks.pop(task)
                try:
                    _, stream, first, error = task.result()
                except asyncio.CancelledError:
                    error = RuntimeError('cancelled')
                    stream = None
                    first = None
                except Exception as exc:
                    error = exc
                    stream = None
                    first = None
                if error is None and stream is not None:
                    winner_model = model
                    winner_stream = stream
                    winner_first = first
                    for other in list(tasks):
                        other.cancel()
                    tasks.clear()
                    break
            if winner_model is not None:
                break
        for task in list(tasks):
            task.cancel()
        if winner_model is not None and winner_stream is not None:
            return winner_model, winner_stream, winner_first
        return None

    @staticmethod
    def _to_chunk(chunk: Any, model_id: str) -> _GatewayStreamChunk:
        return _GatewayStreamChunk(
            _extract_text(chunk), model=model_id, model_name=model_id, raw=chunk
        )

    async def _stream_chain(
        self,
        chain: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        params: dict[str, Any],
        company_id: Any,
        trace_id: Any,
    ) -> AsyncIterator[_GatewayStreamChunk]:
        for _index, primary_model in enumerate(chain):
            backup_model = chain[1] if (len(chain) > 1 and primary_model is chain[0]) else None
            if backup_model is primary_model:
                backup_model = None
            result = await self._attempt_step(primary_model, backup_model, messages, params)
            if result is None:
                continue
            chosen_model, rest_stream, first_chunk = result
            model_id = str(chosen_model.get('model_id') or chosen_model.get('model'))
            if len(chain) >= 3 and model_id == str(
                chain[-1].get('model_id') or chain[-1].get('model')
            ):
                self._alert_fallback_3(model_id, company_id)
            await self._record_usage(model_id, company_id, trace_id=trace_id, units=1)
            yield self._to_chunk(first_chunk, model_id)
            try:
                async for chunk in rest_stream:
                    yield self._to_chunk(chunk, model_id)
            except Exception:
                pass
            return
        unavailable = 'We are temporarily unavailable. Please try again.'
        yield _GatewayStreamChunk(
            unavailable, model='unavailable', model_name='unavailable', type='error'
        )

    async def stream(  # type: ignore[override]
        self, company_id: object = None, *args: object, **kwargs: object
    ) -> object:
        company_id = self._extract_company_id(company_id, kwargs)
        if args:
            if isinstance(args[0], (list, tuple, str)):
                kwargs.setdefault(
                    'messages' if isinstance(args[0], (list, tuple)) else 'prompt', args[0]
                )
            else:
                kwargs.setdefault('prompt', args[0])
        trace_id = kwargs.get('trace_id') or kwargs.get('trace')
        chain = self._choose_chain(kwargs)
        messages = _build_messages(
            **{
                k: v
                for k, v in kwargs.items()
                if k
                in {
                    'prompt',
                    'messages',
                    'system',
                    'instructions',
                    'calculations',
                    'chunks',
                    'question',
                }
            }
        )
        params: dict[str, Any] = {}
        for key in (
            'max_tokens',
            'temperature',
            'top_p',
            'stop',
            'response_format',
            'tools',
            'tool_choice',
            'extra_headers',
        ):
            if key in kwargs:
                params[key] = kwargs[key]
        async for item in self._stream_chain(chain, messages, params, company_id, trace_id):
            yield item

    async def complete(self, company_id: object = None, *args: object, **kwargs: object) -> object:
        text_parts: list[str] = []
        model_name = 'unavailable'
        stream_obj = self.stream(company_id, *args, **kwargs)
        async for chunk in stream_obj:  # type: ignore[attr-defined]
            piece = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if piece:
                text_parts.append(str(piece))
            model_name = getattr(chunk, 'model', None) or getattr(chunk, 'model_name', model_name)  # type: ignore[assignment]
        text = ''.join(text_parts)
        response = _GatewayStreamChunk(
            text, model=model_name, model_name=model_name, type='completion'
        )
        response._metadata['content'] = text
        response._metadata['text'] = text
        return response

    async def generate(self, company_id: object = None, *args: object, **kwargs: object) -> object:
        return await self.complete(company_id, *args, **kwargs)

    async def chat(self, company_id: object = None, *args: object, **kwargs: object) -> object:
        return await self.complete(company_id, *args, **kwargs)

    async def generate_text(
        self, company_id: object = None, *args: object, **kwargs: object
    ) -> object:
        return await self.complete(company_id, *args, **kwargs)

    async def stream_complete(
        self, company_id: object = None, *args: object, **kwargs: object
    ) -> object:
        return self.stream(company_id, *args, **kwargs)

    async def stream_text(
        self, company_id: object = None, *args: object, **kwargs: object
    ) -> object:
        return self.stream(company_id, *args, **kwargs)


def _extract_text(chunk: Any) -> str:
    if chunk is None:
        return ''
    if isinstance(chunk, str):
        return chunk
    try:
        choices = getattr(chunk, 'choices', None)
        if choices:
            delta = getattr(choices[0], 'delta', None)
            if delta is not None:
                content = getattr(delta, 'content', None)
                if content is not None:
                    return str(content)
            message = getattr(choices[0], 'message', None)
            if message is not None:
                content = getattr(message, 'content', None)
                if content is not None:
                    return str(content)
            text = getattr(choices[0], 'text', None)
            if text is not None:
                return str(text)
    except Exception:
        pass
    if isinstance(chunk, dict):
        for key in ('content', 'text', 'delta', 'output'):
            value = chunk.get(key)
            if value is not None:
                if isinstance(value, dict):
                    inner = value.get('content') or value.get('text')
                    if inner is not None:
                        return str(inner)
                return str(value)
        choices = chunk.get('choices')
        if isinstance(choices, list) and choices:
            delta = choices[0].get('delta') if isinstance(choices[0], dict) else None
            if isinstance(delta, dict):
                content = delta.get('content')
                if content is not None:
                    return str(content)
    return '' if chunk is None else str(chunk)


LLMGateway = LiteLLMGateway
LiteLLM = LiteLLMGateway
ModelGateway = LiteLLMGateway
LLMAdapter = LiteLLMGateway
Gateway = LiteLLMGateway

__all__ = [
    'Gateway',
    'GatewayStreamChunk',
    'LLMAdapter',
    'LLMGateway',
    'LiteLLM',
    'LiteLLMGateway',
    'ModelGateway',
    '_GatewayStreamChunk',
]

GatewayStreamChunk = _GatewayStreamChunk
