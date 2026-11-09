"""Derive runtime model identity from the ``models.*`` source of truth.

``models.*`` owns model identity. Runtime sections (``llm.*`` and
``reranker.*``) own tuning only. This module copies identity into the runtime
shape before the config model validates, so approval and pricing checks always
run against the IDs the gateway actually calls.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _identity(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _identity_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [text for item in value if (text := _identity(item)) is not None]


def _with_identity(entry: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    result = dict(entry)
    result['model_id'] = model_id
    return result


def _tuning_at(templates: Sequence[Mapping[str, Any]], index: int) -> Mapping[str, Any]:
    if not templates:
        return {}
    return templates[min(index, len(templates) - 1)]


def _build_chain(
    templates: Sequence[Mapping[str, Any]],
    model_ids: list[str],
    default_tuning: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tuning = templates or ([default_tuning] if default_tuning else [])
    return [
        _with_identity(_tuning_at(tuning, index), model_id)
        for index, model_id in enumerate(model_ids)
    ]


def _tuning_list(llm: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in llm.get(key) or [] if isinstance(item, Mapping)]


def _derive_answer_identity(llm: Mapping[str, Any], answer: Mapping[str, Any]) -> dict[str, Any]:
    # ``models.answer`` owns identity; the runtime entries below own tuning.
    # Identity is always overwritten when declared, while any tuning already
    # present on a runtime entry is preserved.
    result = dict(llm)
    primary_tuning = _mapping(result.get('primary_model'))
    fallback_tuning = _tuning_list(result, 'fallback_models')

    primary_id = _identity(answer.get('primary'))
    if primary_id is not None:
        result['primary_model'] = _with_identity(primary_tuning, primary_id)
    if 'primary_fallbacks' in answer:
        result['fallback_models'] = _build_chain(
            fallback_tuning,
            _identity_list(answer.get('primary_fallbacks')),
            primary_tuning,
        )

    cheap_id = _identity(answer.get('cheap'))
    if cheap_id is not None:
        # Reuse cheap-specific tuning when it exists, otherwise clone the
        # primary tuning so a single identity declaration is enough.
        cheap_tuning = _mapping(result.get('cheap_model')) or primary_tuning
        result['cheap_model'] = _with_identity(cheap_tuning, cheap_id)
    if 'cheap_fallbacks' in answer:
        result['cheap_fallback_models'] = _build_chain(
            _tuning_list(result, 'cheap_fallback_models') or fallback_tuning,
            _identity_list(answer.get('cheap_fallbacks')),
            primary_tuning,
        )
    return result


def _derive_reranker_identity(reranker: Mapping[str, Any], primary: str | None) -> dict[str, Any]:
    result = dict(reranker)
    if primary is None:
        return result
    # ``models.rerank.primary`` is provider-qualified, while ``reranker.model``
    # keeps the provider in ``reranker.provider``. Strip the matching prefix.
    provider = _identity(result.get('provider')) or ''
    prefix = f'{provider}/'
    result['model'] = primary[len(prefix) :] if provider and primary.startswith(prefix) else primary
    return result


def derive_runtime_model_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with runtime identity copied from ``models``."""
    models = _mapping(data.get('models'))
    if not models:
        return dict(data)

    answer = _mapping(models.get('answer'))
    embedding = _mapping(models.get('embedding'))
    rerank = _mapping(models.get('rerank'))

    result = dict(data)
    llm = dict(_mapping(data.get('llm')))
    if answer:
        llm = _derive_answer_identity(llm, answer)
    embedding_id = _identity(embedding.get('primary'))
    if embedding_id is not None:
        llm['embedding_model'] = _with_identity(_mapping(llm.get('embedding_model')), embedding_id)
    if 'llm' in data or llm:
        # Keep the runtime section in the derived payload when it exists (or
        # gains derived identity), so nested validation sees the same shape.
        result['llm'] = llm

    rerank_id = _identity(rerank.get('primary'))
    if rerank_id is not None:
        result['reranker'] = _derive_reranker_identity(_mapping(data.get('reranker')), rerank_id)
    return result
