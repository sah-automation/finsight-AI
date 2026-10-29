# ruff: noqa: BLE001, ANN401, PLR0911, PLR0912, PLR0915, TRY300, TRY301, S110, PLC0415
"""LiteLLM-backed embedding adapter with retries and dimension validation."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from finsight.domain.ports.embedding_provider import EmbeddingProvider as EmbeddingProviderPort

_LOGGER = logging.getLogger(__name__)

_litellm_module: Any
try:
    import litellm as _litellm_module
except Exception:  # pragma: no cover
    _litellm_module = None

_ORIGINAL_AEMBEDDING = (
    getattr(_litellm_module, 'aembedding', None) if _litellm_module is not None else None
)
aembedding = _ORIGINAL_AEMBEDDING
litellm_aembedding = _ORIGINAL_AEMBEDDING
embedding = getattr(_litellm_module, 'embedding', None) if _litellm_module is not None else None


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
    return kwargs.get('embedding_config') or kwargs.get('model_config')


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _as_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, dict):
        for key in ('texts', 'inputs', 'input', 'data', 'values'):
            if value.get(key) is not None:
                return _as_texts(value.get(key))
        return [str(value)]
    return [str(value)]


def _resolve_aembedding() -> Any:
    litellm_fn = None
    if _litellm_module is not None:
        litellm_fn = getattr(_litellm_module, 'aembedding', None)
    module_fn = aembedding
    if module_fn is not None and module_fn is not _ORIGINAL_AEMBEDDING:
        return module_fn
    try:
        import finsight.adapters.embedding.litellm_embedding as _alias_module

        alias_fn = getattr(_alias_module, 'aembedding', None)
        if alias_fn is not None and alias_fn is not _ORIGINAL_AEMBEDDING:
            return alias_fn
    except Exception:
        pass
    if litellm_fn is not None:
        return litellm_fn
    if module_fn is not None:
        return module_fn
    sync_fn = getattr(_litellm_module, 'embedding', None) if _litellm_module is not None else None
    if sync_fn is not None:

        async def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return sync_fn(*args, **kwargs)

        return _wrapped
    raise RuntimeError('litellm aembedding is unavailable')


class LiteLLMEmbedding(EmbeddingProviderPort):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = _resolve_config(*args, **kwargs)
        self.company_id_default: Any = kwargs.get('company_id')
        self.embedding_func = _first(
            kwargs, 'embedding_func', 'aembedding', 'embed_func', default=None
        )

        # Resolve embedding model config.
        embedding_cfg = _first(
            kwargs, 'embedding_model', 'embedding_config', 'model_config', default=None
        )
        if embedding_cfg is None and self.config is not None:
            llm_cfg = getattr(self.config, 'llm', None)
            if llm_cfg is None:
                llm_cfg = getattr(self.config, 'llm_config', None)
            if llm_cfg is not None:
                embedding_cfg = getattr(llm_cfg, 'embedding_model', None)
            if embedding_cfg is None and self.config is not None:
                embedding_cfg = getattr(self.config, 'embedding', None)
            if embedding_cfg is None and self.config is not None:
                embedding_cfg = getattr(self.config, 'embedding_model', None)

        model_id = _first(kwargs, 'model_id', 'model', default=None)
        if model_id is None and embedding_cfg is not None:
            model_id = getattr(embedding_cfg, 'model_id', None)
            if model_id is None and isinstance(embedding_cfg, dict):
                model_id = embedding_cfg.get('model_id') or embedding_cfg.get('model')
        if model_id is None:
            model_id = 'default-embedding'
        self.model_id = str(model_id)

        dimensions = _first(kwargs, 'dimensions', 'embedding_dimensions', default=None)
        if dimensions is None and embedding_cfg is not None:
            dimensions = getattr(embedding_cfg, 'dimensions', None)
            if dimensions is None and isinstance(embedding_cfg, dict):
                dimensions = embedding_cfg.get('dimensions')
        self.dimensions = int(dimensions) if dimensions is not None else 0

        batch_size = _first(kwargs, 'batch_size', default=None)
        if batch_size is None and embedding_cfg is not None:
            batch_size = getattr(embedding_cfg, 'batch_size', None)
            if batch_size is None and isinstance(embedding_cfg, dict):
                batch_size = embedding_cfg.get('batch_size')
        self.batch_size = int(batch_size) if batch_size is not None else 16
        self.batch_size = max(self.batch_size, 1)

        timeout = _first(kwargs, 'timeout_seconds', 'timeout', default=None)
        if timeout is None and embedding_cfg is not None:
            timeout = getattr(embedding_cfg, 'timeout_seconds', None)
            if timeout is None and isinstance(embedding_cfg, dict):
                timeout = embedding_cfg.get('timeout_seconds')
        self.timeout = int(timeout) if timeout is not None else 30

        max_retries = _first(kwargs, 'max_retries', 'retry_attempts', default=None)
        if max_retries is None and embedding_cfg is not None:
            max_retries = getattr(
                embedding_cfg, 'max_retries', getattr(embedding_cfg, 'retry_attempts', None)
            )
            if max_retries is None and isinstance(embedding_cfg, dict):
                max_retries = embedding_cfg.get('max_retries', embedding_cfg.get('retry_attempts'))
        self.max_retries = int(max_retries) if max_retries is not None else 3

        retry_wait = _first(
            kwargs,
            'retry_wait_seconds',
            'retry_base_delay_seconds',
            'retry_delay_seconds',
            default=None,
        )
        if retry_wait is None and embedding_cfg is not None:
            retry_wait = getattr(
                embedding_cfg,
                'retry_wait_seconds',
                getattr(embedding_cfg, 'retry_base_delay_seconds', None),
            )
            if retry_wait is None and isinstance(embedding_cfg, dict):
                retry_wait = embedding_cfg.get(
                    'retry_wait_seconds', embedding_cfg.get('retry_base_delay_seconds')
                )
        self.retry_wait = float(retry_wait) if retry_wait is not None else 2.0

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
        self.logger = _first(kwargs, 'logger', default=_LOGGER)
        self.usage_rows: list[dict[str, Any]] = []
        self._usage_lock = asyncio.Lock()

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        company_id = (
            company_id
            if company_id is not None
            else kwargs.get(
                'company_id',
                self.company_id_default if hasattr(self, 'company_id_default') else None,
            )
        )
        if company_id is None:
            company_id = kwargs.get('tenant_id') or kwargs.get('company') or 'unknown'

        if args:
            kwargs.setdefault('texts' if isinstance(args[0], (list, tuple)) else 'text', args[0])

        single_input = False
        texts: list[str] = []
        if (
            'text' in kwargs
            and kwargs.get('text') is not None
            and 'texts' not in kwargs
            and 'inputs' not in kwargs
            and 'input' not in kwargs
        ):
            single_input = True
            texts = _as_texts(kwargs.get('text'))
        else:
            value = kwargs.get(
                'texts', kwargs.get('inputs', kwargs.get('input', kwargs.get('documents')))
            )
            if value is None and args:
                value = args[0]
            texts = _as_texts(value)

        if not texts:
            raise ValueError('No text provided for embedding')

        # Resolve text mode: if caller explicitly asks for one embedding.
        if kwargs.get('single') is True:
            single_input = True

        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors = await self._embed_batch(batch)
            if self.dimensions and any(len(vector) != self.dimensions for vector in vectors):
                raise ValueError('Embedding dimension mismatch')
            all_vectors.extend(vectors)

        await self._record_usage(self.model_id, company_id, len(texts))

        if single_input and len(texts) == 1:
            return all_vectors[0]
        return all_vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        attempts = self.max_retries + 1
        delay = self.retry_wait
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                fn = self.embedding_func
                if not callable(fn):
                    fn = _resolve_aembedding()
                kwargs = {
                    'model': self.model_id,
                    'input': texts,
                    'timeout': self.timeout,
                }
                result = fn(**kwargs)
                if inspect.isawaitable(result):
                    result = await result
                vectors = _extract_vectors(result)
                if self.dimensions:
                    for vector in vectors:
                        if len(vector) != self.dimensions:
                            raise ValueError(
                                f'Expected {self.dimensions} dimensions, got {len(vector)}'
                            )
                return vectors
            except Exception as exc:
                last_error = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(delay)
        raise last_error if last_error is not None else RuntimeError('embedding failed')

    async def _record_usage(self, model_id: str, company_id: Any, units: int) -> None:
        row = {
            'company_id': company_id,
            'service': 'embedding',
            'units': units,
            'estimated_cost': None,
            'model': model_id,
            'model_name': model_id,
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
                service='embedding',
                model=r['model'],
                model_name=r['model'],
                units=r['units'],
                estimated_cost=r['estimated_cost'],
                usage=r,
                row=r,
            ),
            lambda m=method, r=row: m(r),
            lambda m=method, r=row: m(r['company_id'], 'embedding', r['units'], None, r['model']),
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

    # Port compatibility aliases for both single/batch callers.
    async def embed_texts(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault('texts', args[0] if args else kwargs.get('texts'))
        return await self.embed(
            company_id,
            *args,
            **{k: v for k, v in kwargs.items() if k != 'texts'} | {'texts': kwargs.get('texts')},
        )

    async def embed_text(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if args:
            kwargs.setdefault('text', args[0])
        return await self.embed(company_id, **{**kwargs, 'single': True})

    async def embed_batch(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        if args:
            kwargs.setdefault('texts', args[0])
        kwargs['single'] = False
        return await self.embed(company_id, **kwargs)

    async def embed_many(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await self.embed_batch(company_id, *args, **kwargs)


def _extract_vectors(result: Any) -> list[list[float]]:
    if result is None:
        return []
    if isinstance(result, dict):
        for key in ('data', 'embeddings', 'results'):
            value = result.get(key)
            if value is not None:
                return _extract_vectors(value)
        if 'embedding' in result:
            return [list(result['embedding'])]
    if isinstance(result, (list, tuple)):
        # Could be list of vectors or list of objects.
        if not result:
            return []
        if isinstance(result[0], (int, float)):
            return [list(result)]
        vectors: list[list[float]] = []
        for item in result:
            if isinstance(item, (list, tuple)):
                vectors.append([float(x) for x in item])
            elif isinstance(item, dict):
                emb = item.get('embedding', item.get('vector', item.get('values')))
                if emb is not None:
                    vectors.append([float(x) for x in emb])
            elif hasattr(item, 'embedding'):
                vectors.append([float(x) for x in item.embedding])
            else:
                vectors.append([float(x) for x in item])
        return vectors
    # Object with .data or .embeddings
    for attr in ('data', 'embeddings', 'results'):
        value = getattr(result, attr, None)
        if value is not None:
            return _extract_vectors(value)
    # Object with .embedding
    value = getattr(result, 'embedding', None)
    if value is not None:
        return _extract_vectors(value)
    raise TypeError('Unable to extract embeddings from result')


EmbeddingProvider = LiteLLMEmbedding
Embeddings = LiteLLMEmbedding
LiteLLMEmbeddings = LiteLLMEmbedding
EmbeddingAdapter = LiteLLMEmbedding
EmbeddingGatewayImpl = LiteLLMEmbedding

__all__ = [
    'EmbeddingAdapter',
    'EmbeddingGatewayImpl',
    'EmbeddingProvider',
    'Embeddings',
    'LiteLLMEmbedding',
    'LiteLLMEmbeddings',
]
