# ruff: noqa: ANN401, BLE001, PLR0911, PLR0912, S110
"""LLM gateway message/chunk helpers."""

from __future__ import annotations

from typing import Any


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
