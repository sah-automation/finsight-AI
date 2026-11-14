"""Derive runtime model identity from the ``models.*`` source of truth.

``models.*`` owns model identity. Runtime sections (``llm.*`` and
``reranker.*``) own tuning only. This module copies identity into the runtime
shape before the config model validates, so approval and pricing checks always
run against the IDs the gateway actually calls.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class RuntimeModelIdentityDeriver:
    """Stateless derivation of runtime model identity from ``models.*``."""

    # ---- public API ---------------------------------------------------------

    def derive(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy of ``data`` with runtime identity copied from ``models``."""
        models = self._mapping(data.get('models'))
        if not models:
            return dict(data)

        result = dict(data)
        llm = dict(self._mapping(data.get('llm')))

        llm = self._derive_llm_identity(llm, models)
        if 'llm' in data or llm:
            result['llm'] = llm

        rerank_id = self._identity(self._mapping(models.get('rerank')).get('primary'))
        if rerank_id is not None:
            result['reranker'] = self._derive_reranker_identity(
                self._mapping(data.get('reranker')), rerank_id
            )
        return result

    def _derive_llm_identity(
        self, llm: Mapping[str, Any], models: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Derive LLM model identity from models.answer and models.embedding."""
        result = dict(llm)
        answer = self._mapping(models.get('answer'))
        embedding = self._mapping(models.get('embedding'))

        if answer:
            result = self._derive_answer_identity(result, answer)
        embedding_id = self._identity(embedding.get('primary'))
        if embedding_id is not None:
            result['embedding_model'] = self._with_identity(
                self._mapping(result.get('embedding_model')), embedding_id
            )
        return result

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _mapping(value: object) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _identity(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _identity_list(value: object) -> list[str]:
        if not isinstance(value, (list, tuple)):
            return []
        return [
            text
            for item in value
            if (text := RuntimeModelIdentityDeriver._identity(item)) is not None
        ]

    @staticmethod
    def _with_identity(entry: Mapping[str, Any], model_id: str) -> dict[str, Any]:
        result = dict(entry)
        result['model_id'] = model_id
        return result

    @staticmethod
    def _tuning_at(templates: Sequence[Mapping[str, Any]], index: int) -> Mapping[str, Any]:
        if not templates:
            return {}
        return templates[min(index, len(templates) - 1)]

    @staticmethod
    def _tuning_list(llm: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
        return [dict(item) for item in llm.get(key) or [] if isinstance(item, Mapping)]

    @classmethod
    def _build_chain(
        cls,
        templates: Sequence[Mapping[str, Any]],
        model_ids: list[str],
        default_tuning: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        tuning = templates or ([default_tuning] if default_tuning else [])
        return [
            cls._with_identity(cls._tuning_at(tuning, index), model_id)
            for index, model_id in enumerate(model_ids)
        ]

    # ---- derivation steps ---------------------------------------------------

    def _derive_answer_identity(
        self, llm: Mapping[str, Any], answer: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Copy identity from ``models.answer`` into the ``llm`` runtime section."""
        result = dict(llm)
        primary_tuning = self._mapping(result.get('primary_model'))
        fallback_tuning = self._tuning_list(result, 'fallback_models')

        result = self._apply_primary_identity(result, answer, primary_tuning, fallback_tuning)
        return self._apply_cheap_identity(result, answer, primary_tuning, fallback_tuning)

    def _apply_primary_identity(
        self,
        result: dict[str, Any],
        answer: Mapping[str, Any],
        primary_tuning: Mapping[str, Any],
        fallback_tuning: list[dict[str, Any]],
    ) -> dict[str, Any]:
        primary_id = self._identity(answer.get('primary'))
        if primary_id is not None:
            result['primary_model'] = self._with_identity(primary_tuning, primary_id)
        if 'primary_fallbacks' in answer:
            result['fallback_models'] = self._build_chain(
                fallback_tuning,
                self._identity_list(answer.get('primary_fallbacks')),
                primary_tuning,
            )
        return result

    def _apply_cheap_identity(
        self,
        result: dict[str, Any],
        answer: Mapping[str, Any],
        primary_tuning: Mapping[str, Any],
        fallback_tuning: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cheap_id = self._identity(answer.get('cheap'))
        if cheap_id is not None:
            cheap_tuning = self._mapping(result.get('cheap_model')) or primary_tuning
            result['cheap_model'] = self._with_identity(cheap_tuning, cheap_id)
        if 'cheap_fallbacks' in answer:
            result['cheap_fallback_models'] = self._build_chain(
                self._tuning_list(result, 'cheap_fallback_models') or fallback_tuning,
                self._identity_list(answer.get('cheap_fallbacks')),
                primary_tuning,
            )
        return result

    @staticmethod
    def _derive_reranker_identity(
        reranker: Mapping[str, Any], primary: str | None
    ) -> dict[str, Any]:
        result = dict(reranker)
        if primary is None:
            return result
        # ``models.rerank.primary`` is provider-qualified, while ``reranker.model``
        # keeps the provider in ``reranker.provider``. Strip the matching prefix.
        provider = RuntimeModelIdentityDeriver._identity(result.get('provider')) or ''
        prefix = f'{provider}/'
        result['model'] = (
            primary[len(prefix) :] if provider and primary.startswith(prefix) else primary
        )
        return result


# Backwards-compatible module-level function used by Config validator
def derive_runtime_model_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    return RuntimeModelIdentityDeriver().derive(data)
