# ruff: noqa: ANN401
"""Embedding embed method helpers."""

from __future__ import annotations

from typing import Any

from ._embedding_helpers import _as_texts
from ._embedding_operations import _embed_batch, _record_usage


async def _embed(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
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

    if kwargs.get('single') is True:
        single_input = True

    all_vectors: list[list[float]] = []
    for start in range(0, len(texts), self.batch_size):
        batch = texts[start : start + self.batch_size]
        vectors = await _embed_batch(self, batch)
        if self.dimensions and any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError('Embedding dimension mismatch')
        all_vectors.extend(vectors)

    await _record_usage(self, self.model_id, company_id, len(texts))

    if single_input and len(texts) == 1:
        return all_vectors[0]
    return all_vectors


async def _embed_texts(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault('texts', args[0] if args else kwargs.get('texts'))
    return await _embed(
        self,
        company_id,
        *args,
        **{k: v for k, v in kwargs.items() if k != 'texts'} | {'texts': kwargs.get('texts')},
    )


async def _embed_text(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    if args:
        kwargs.setdefault('text', args[0])
    return await _embed(self, company_id, **{**kwargs, 'single': True})


async def _embed_batch_alias(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    if args:
        kwargs.setdefault('texts', args[0])
    kwargs['single'] = False
    return await _embed(self, company_id, **kwargs)


async def _embed_many(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    return await _embed_batch_alias(self, company_id, *args, **kwargs)
