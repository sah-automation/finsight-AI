from __future__ import annotations

from collections.abc import Mapping

from pydantic import AliasChoices, Field, field_validator, model_validator

from .approved_model_config import ApprovedModelConfig
from .models_answer_config import ModelsAnswerConfig
from .models_embedding_config import ModelsEmbeddingConfig
from .models_rerank_config import ModelsRerankConfig
from .strict_base_model import StrictBaseModel

_REQUIRED_FAILOVER_CONDITIONS = {
    'timeout',
    'first_word_timeout',
    'rate_limit',
    'server_error',
}

_DEFAULT_APPROVED_MODELS = [
    {'model_id': 'gemini/gemini-1.5-pro', 'regions': ['us-east-1', 'us-west-2', 'us']},
    {'model_id': 'gemini/gemini-1.5-flash', 'regions': ['us-east-1', 'us-west-2', 'us']},
    {'model_id': 'gemini/text-embedding-004', 'regions': ['us-east-1', 'us-west-2', 'us']},
    {'model_id': 'groq/llama-3.3-70b-versatile', 'regions': ['us-east-1', 'us-west-2', 'us']},
    {'model_id': 'groq/llama-3.1-8b-instant', 'regions': ['us-east-1', 'us-west-2', 'us']},
    {
        'model_id': 'nvidia_nim/meta/llama-3.1-70b-instruct',
        'regions': ['us-east-1', 'us-west-2', 'us'],
    },
    {
        'model_id': 'nvidia_nim/meta/llama-3.1-8b-instruct',
        'regions': ['us-east-1', 'us-west-2', 'us'],
    },
    {
        'model_id': 'nvidia_nim/llama-3.2-nv-rerankqa-1b-v2',
        'regions': ['us-east-1', 'us-west-2', 'us'],
    },
    {
        'model_id': 'self_hosted/open_model_small',
        'regions': ['us-east-1', 'us-west-2', 'us', 'in-region'],
    },
    {
        'model_id': 'self_hosted/cross_encoder_small',
        'regions': ['us-east-1', 'us-west-2', 'us', 'in-region'],
    },
]


class ModelsConfig(StrictBaseModel):
    answer: ModelsAnswerConfig = Field(default_factory=ModelsAnswerConfig)
    failover_on: list[str] = Field(
        default_factory=lambda: [
            'timeout',
            'first_word_timeout',
            'rate_limit',
            'server_error',
            'provider_unavailable',
        ]
    )
    embedding: ModelsEmbeddingConfig = Field(default_factory=ModelsEmbeddingConfig)
    rerank: ModelsRerankConfig = Field(default_factory=ModelsRerankConfig)
    timeout_seconds: int = Field(ge=1, default=20)
    first_token_timeout_seconds: float = Field(ge=0.1, le=5.0, default=4.0)
    backup_request_enabled: bool = True
    backup_request_after_seconds: float = Field(ge=0.0, default=2.5)
    prompt_cache_enabled: bool = True
    max_output_tokens: int = Field(ge=1, default=1000)
    monthly_budget_per_company: int = Field(ge=0, default=50)
    approved_models: list[ApprovedModelConfig] = Field(
        default_factory=lambda: [
            ApprovedModelConfig.model_validate(item) for item in _DEFAULT_APPROVED_MODELS
        ],
        validation_alias=AliasChoices(
            'approved_models',
            'approved_model_list',
            'approved_models_list',
            'approved',
            'approved_list',
            'approved_models_per_region',
        ),
    )
    region: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            'region',
            'approved_region',
            'deployment_region',
            'model_region',
            'current_region',
        ),
    )

    @field_validator('approved_models', mode='before')
    @classmethod
    def _normalize_approved_models(cls, value: object) -> object:  # noqa: PLR0912
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if isinstance(value, Mapping):
            # Allow region -> [model] mappings, flatten into approved entries.
            flattened: list[object] = []
            for key, items in value.items():
                region = str(key)
                if isinstance(items, (list, tuple, set)):
                    for item in items:
                        if isinstance(item, Mapping):
                            entry = dict(item)
                            entry.setdefault('regions', [region])
                            flattened.append(entry)
                        else:
                            flattened.append({'model_id': item, 'regions': [region]})
                elif isinstance(items, Mapping):
                    entry = dict(items)
                    entry.setdefault('model_id', key)
                    entry.setdefault('regions', [region])
                    flattened.append(entry)
                else:
                    flattened.append({'model_id': str(items), 'regions': [region]})
            return flattened
        if not isinstance(value, (list, tuple, set)):
            value = [value]
        assert isinstance(value, (list, tuple, set))  # noqa: S101
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({'model_id': item})
            elif isinstance(item, Mapping):
                normalized.append(dict(item))
            else:
                normalized.append(item)
        return normalized

    @model_validator(mode='after')
    def validate_models(self) -> ModelsConfig:
        max_first_token_timeout = 5
        if self.first_token_timeout_seconds >= self.timeout_seconds:
            raise ValueError('first_token_timeout_seconds must be below timeout_seconds')
        if self.first_token_timeout_seconds > max_first_token_timeout:
            raise ValueError('first_token_timeout_seconds must be at most 5')
        if self.backup_request_after_seconds >= self.first_token_timeout_seconds:
            raise ValueError(
                'backup_request_after_seconds must be below first_token_timeout_seconds'
            )
        missing_failover = _REQUIRED_FAILOVER_CONDITIONS - set(self.failover_on)
        if missing_failover:
            raise ValueError('failover_on must include ' + ', '.join(sorted(missing_failover)))

        approved_ids = {item.model_id for item in self.approved_models if item.approved}
        configured = self.configured_model_ids()
        if self.approved_models:
            for model_id in configured:
                if model_id not in approved_ids:
                    raise ValueError(f'model {model_id!r} is not approved')
                matching = [item for item in self.approved_models if item.model_id == model_id]
                if matching and not any(item.is_approved_for(self.region) for item in matching):
                    region = self.region or 'configured region'
                    raise ValueError(f'model {model_id!r} is not approved for region {region!r}')
        return self

    def configured_model_ids(self) -> list[str]:
        answer = self.answer
        out: list[str] = [answer.primary]
        out.extend(answer.primary_fallbacks)
        out.extend([answer.cheap])
        out.extend(answer.cheap_fallbacks)
        out.append(self.embedding.primary)
        out.append(self.rerank.primary)
        return [str(item) for item in out]
