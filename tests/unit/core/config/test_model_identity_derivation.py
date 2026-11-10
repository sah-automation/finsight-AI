"""Model identity derivation: ``models.*`` is the single source of truth."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.core.config import Config, load_config, reset_config

CONFIG_DIR = Path(__file__).parent.parent.parent.parent.parent / 'config'


def _loaded_config_data() -> dict:
    reset_config()
    return load_config('test').model_dump(mode='python', by_alias=True)


def test_runtime_identity_is_derived_from_models() -> None:
    config = load_config('test')
    assert config.models is not None

    models = config.models
    assert config.llm.primary_model.model_id == models.answer.primary
    assert [item.model_id for item in config.llm.fallback_models] == list(
        models.answer.primary_fallbacks
    )
    assert config.llm.embedding_model.model_id == models.embedding.primary

    assert config.llm.cheap_model is not None
    assert config.llm.cheap_model.model_id == models.answer.cheap
    assert [item.model_id for item in config.llm.cheap_fallback_models] == list(
        models.answer.cheap_fallbacks
    )

    rerank_provider = config.reranker.provider
    rerank_model = models.rerank.primary
    assert rerank_model.startswith(f'{rerank_provider}/')
    assert config.reranker.model == rerank_model.split('/', 1)[1]


def test_cheap_runtime_tuning_is_preserved() -> None:
    data = _loaded_config_data()
    data['llm']['cheap_model'] = {
        **data['llm']['primary_model'],
        'model_id': 'stale-identity',
        'max_tokens': 111,
        'temperature': 0.9,
    }

    config = Config.model_validate(data)
    assert config.models is not None
    assert config.llm.cheap_model is not None
    assert config.llm.cheap_model.model_id == config.models.answer.cheap
    assert config.llm.cheap_model.max_tokens == 111
    assert config.llm.cheap_model.temperature == 0.9


def test_gateway_chains_match_declared_models() -> None:
    config = load_config('test')
    assert config.models is not None
    gateway = LiteLLMGateway(config=config)

    declared_primary = [
        config.models.answer.primary,
        *config.models.answer.primary_fallbacks,
    ]
    declared_cheap = [
        config.models.answer.cheap,
        *config.models.answer.cheap_fallbacks,
    ]

    assert [item['model_id'] for item in gateway.chains['primary']] == declared_primary
    assert [item['model_id'] for item in gateway.chains['cheap']] == declared_cheap


def test_gateway_completes_with_the_cheap_chain() -> None:
    config = load_config('test')
    assert config.models is not None
    seen: list[str] = []

    async def _completion(*, model: str, **kwargs: object) -> object:
        seen.append(model)

        async def _chunks() -> object:
            yield {'content': 'ok', 'model': model}

        return _chunks()

    gateway = LiteLLMGateway(
        config=config,
        completion_func=_completion,
        backup_request_enabled=False,
        first_token_timeout_seconds=1.0,
    )

    result = asyncio.run(gateway.complete(company_id='co1', prompt='hi', chain='cheap'))

    assert result.content == 'ok'
    assert seen == [config.models.answer.cheap]


def test_derivation_follows_a_changed_chain() -> None:
    data = _loaded_config_data()
    changed_fallbacks = [
        'groq/openai/gpt-oss-120b',
        'nvidia_nim/google/gemma-4-31b-it',
        'self_hosted/open_model_small',
    ]
    data['models']['answer']['primary'] = 'gemini/gemini-3.6-flash'
    data['models']['answer']['primary_fallbacks'] = changed_fallbacks

    config = Config.model_validate(data)
    gateway = LiteLLMGateway(config=config)

    declared = ['gemini/gemini-3.6-flash', *changed_fallbacks]
    assert [item['model_id'] for item in gateway.chains['primary']] == declared
    assert config.llm.primary_model.model_id == 'gemini/gemini-3.6-flash'
    assert [item.model_id for item in config.llm.fallback_models] == changed_fallbacks


@pytest.mark.parametrize('fallback_count', [2, 4])
def test_answer_chain_rejects_wrong_fallback_count(fallback_count: int) -> None:
    data = _loaded_config_data()
    data['models']['answer']['primary_fallbacks'] = [
        f'gemini-3.6-flash-{index}' for index in range(fallback_count)
    ]

    with pytest.raises(ValidationError, match='exactly 3 fallbacks'):
        Config.model_validate(data)


@pytest.mark.parametrize('profile', ['schema', 'dev', 'test', 'staging', 'prod'])
def test_runtime_yaml_does_not_declare_model_identity(profile: str) -> None:
    data = yaml.safe_load((CONFIG_DIR / f'{profile}.yaml').read_text())
    llm = data.get('llm') or {}

    assert 'model_id' not in (llm.get('primary_model') or {})
    assert 'model_id' not in (llm.get('embedding_model') or {})
    for fallback in llm.get('fallback_models') or []:
        assert 'model_id' not in fallback
    assert 'model' not in (data.get('reranker') or {})
