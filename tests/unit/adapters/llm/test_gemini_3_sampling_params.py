"""Gemini 3+ sampling-parameter behavior at the LLM gateway boundary (issue #262).

Gemini 3+ model ids must reach the provider call without the deprecated
``temperature``/``top_p``/``top_k`` parameters, with determinism guidance
folded into the system instructions instead. Every other model family keeps
receiving the configured parameters unchanged.
"""

from __future__ import annotations

import asyncio
import warnings
from typing import Any

import pytest

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway

GUIDANCE_FRAGMENT = 'answer deterministically'
_ANSWER_MEMORY_SYSTEM = 'Answer only from provided data. Cite sources.'


def _capture_completion(calls: list[dict[str, Any]]) -> Any:
    async def _completion(**kwargs: Any) -> list[dict[str, Any]]:
        calls.append(kwargs)
        return [{'choices': [{'delta': {'content': 'ok'}}]}]

    return _completion


def _gateway(model_id: str, temperature: float = 0.0) -> LiteLLMGateway:
    """Build a gateway whose primary chain serves ``model_id``."""
    return LiteLLMGateway(
        models={
            'primary': [
                {
                    'model_id': model_id,
                    'max_tokens': 128,
                    'temperature': temperature,
                    'timeout_seconds': 5,
                    'max_retries': 0,
                }
            ]
        }
    )


def _complete(model_id: str, temperature: float = 0.0, **call_kwargs: Any) -> dict[str, Any]:
    """Run one complete() and capture the (single) provider call kwargs."""
    calls: list[dict[str, Any]] = []
    gateway = _gateway(model_id, temperature=temperature)
    gateway.completion_func = _capture_completion(calls)

    messages = [
        {'role': 'system', 'content': _ANSWER_MEMORY_SYSTEM},
        {'role': 'user', 'content': 'How is revenue trending?'},
    ]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        asyncio.run(gateway.complete('company-a', messages=messages, **call_kwargs))

    assert len(calls) == 1, 'completion_func must be called exactly once'
    assert not [
        warning for warning in caught if issubclass(warning.category, DeprecationWarning)
    ], 'no DeprecationWarning may be emitted for this path'
    return calls[0]


def _system_content(call: dict[str, Any]) -> str:
    for message in call['messages']:
        if message.get('role') == 'system':
            return str(message.get('content'))
    return ''


@pytest.mark.parametrize(
    ('model_id', 'temperature'),
    [('gemini-3.8-flash', 0.0), ('gemini-3.6-flash', 0.2)],
)
def test_gemini_3_provider_call_omits_deprecated_sampling_params(
    model_id: str, temperature: float
) -> None:
    call = _complete(model_id, temperature=temperature, top_p=0.9)

    assert call['model'] == model_id
    assert call['messages'][1]['content'] == 'How is revenue trending?'
    assert 'temperature' not in call
    assert 'top_p' not in call
    assert 'top_k' not in call


@pytest.mark.parametrize(
    'model_id', ['gemini-3.8-flash', 'gemini-3.6-flash', 'vertex_ai/gemini-3.4-pro']
)
def test_gemini_3_system_instructions_carry_determinism_guidance(model_id: str) -> None:
    call = _complete(model_id)

    content = _system_content(call)
    assert GUIDANCE_FRAGMENT in content
    assert _ANSWER_MEMORY_SYSTEM in content
    assert content.index(_ANSWER_MEMORY_SYSTEM) < content.index(GUIDANCE_FRAGMENT)


@pytest.mark.parametrize(
    ('model_id', 'temperature'),
    [('groq/llama-3.3-70b-versatile', 0.2), ('self_hosted/open_model_small', 0.0)],
)
def test_non_gemini_provider_call_keeps_configured_sampling_params(
    model_id: str, temperature: float
) -> None:
    call = _complete(model_id, temperature=temperature, top_p=0.9)

    assert call['model'] == model_id
    assert call['temperature'] == temperature
    assert call['top_p'] == 0.9
    assert 'top_k' not in call


@pytest.mark.parametrize('model_id', ['groq/llama-3.3-70b-versatile', 'groq/llama-3.1-8b-instant'])
def test_non_gemini_system_instructions_are_unchanged(model_id: str) -> None:
    call = _complete(model_id)

    assert _system_content(call) == _ANSWER_MEMORY_SYSTEM
