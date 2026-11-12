# ruff: noqa: PLR0912, PLR0915
"""LLM gateway init helper."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ._llm_gateway_config import _as_model_dict, _first, _resolve_config

_LOGGER = logging.getLogger(__name__)


_LLM_GATEWAY_MODEL_KEY = 'model_id'


def _gateway_model_id(self: Any) -> str:
    """Return the gateway's configured model id for metering and pricing.

    The default chain's primary model is the priced identity that metering
    decorators record, replacing unpriced service-name fallbacks (issue #261).
    """
    inner = self.__dict__.get('_inner')
    if inner is not None and inner is not self:
        value = getattr(inner, 'model_id', None)
        if value is not None:
            return str(value)
    chains = self.__dict__.get('chains') or {}
    chain = chains.get(self.__dict__.get('default_chain_name') or '')
    if chain is None:
        chain = next(iter(chains.values()), None)
    first = chain[0] if chain else None
    if isinstance(first, dict):
        value = first.get(_LLM_GATEWAY_MODEL_KEY)
    else:
        value = getattr(first, _LLM_GATEWAY_MODEL_KEY, None)
    if value is not None:
        return str(value)
    raise AttributeError('model_id')


def _init_llm_gateway(self: Any, *args: Any, **kwargs: Any) -> None:
    self.config = _resolve_config(*args, **kwargs)
    self.company_id_default = kwargs.get('company_id')

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
    self.instructions = instructions if instructions is not None else 'You are a helpful assistant.'

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
    self._tags = []
    self._last_trace = {}
    self.usage_rows = []
    self.last_retry_count = 0
    self._usage_lock = asyncio.Lock()

    self.chains = {}
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
