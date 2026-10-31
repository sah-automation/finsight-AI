# ruff: noqa: ANN401
"""LLM gateway public method helpers."""

from __future__ import annotations

from typing import Any

from ._llm_gateway_messages import _build_messages
from ._llm_gateway_stream import _stream_chain
from ._llm_gateway_usage import _choose_chain, _extract_company_id


async def _stream(
    self: Any,
    company_id: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    stream_chunk_cls: Any,
) -> Any:
    company_id = _extract_company_id(self, company_id, kwargs)
    if args:
        if isinstance(args[0], (list, tuple, str)):
            kwargs.setdefault(
                'messages' if isinstance(args[0], (list, tuple)) else 'prompt', args[0]
            )
        else:
            kwargs.setdefault('prompt', args[0])
    trace_id = kwargs.get('trace_id') or kwargs.get('trace')
    chain = _choose_chain(self, kwargs)
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
    async for item in _stream_chain(
        self, chain, messages, params, company_id, trace_id, stream_chunk_cls
    ):
        yield item


async def _complete(
    self: Any, company_id: Any, args: tuple[Any, ...], kwargs: dict[str, Any], stream_chunk_cls: Any
) -> Any:
    text_parts: list[str] = []
    model_name = 'unavailable'
    stream_obj = _stream(self, company_id, args, kwargs, stream_chunk_cls)
    async for chunk in stream_obj:
        piece = chunk.content if hasattr(chunk, 'content') else str(chunk)
        if piece:
            text_parts.append(str(piece))
        model_name = getattr(chunk, 'model', None) or getattr(chunk, 'model_name', model_name)  # type: ignore[assignment]
    text = ''.join(text_parts)
    response = stream_chunk_cls(text, model=model_name, model_name=model_name, type='completion')
    response._metadata['content'] = text
    response._metadata['text'] = text
    return response
