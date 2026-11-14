"""Extraction stack builder (moved out for size)."""

from __future__ import annotations

import importlib
from typing import Any


def _build_extraction_stack(*args: Any, **kwargs: Any) -> Any:
    from .adapter_stacks import (
        _existing,
        _stack_switch,
        build_metering,
        build_tracing,
        resolve_config,
    )

    config = None
    try:
        config = resolve_config(*args, **kwargs)
    except Exception:
        config = kwargs.get('config')
    _ext_metered = importlib.import_module('finsight.adapters.readers.metered_extraction')
    _ext_retrying = importlib.import_module('finsight.adapters.readers.retrying_extraction')
    _ext_traced = importlib.import_module('finsight.adapters.readers.traced_extraction')
    MeteredExtraction = _ext_metered.MeteredExtraction
    RetryingExtraction = _ext_retrying.RetryingExtraction
    TracedExtraction = _ext_traced.TracedExtraction
    _extra = dict(kwargs)
    for _drop in (
        'config',
        'settings',
        'configuration',
        'app_config',
        'session',
        'db_session',
        'container',
        'composition',
        'root',
        'app',
        'context',
    ):
        _extra.pop(_drop, None)
    reader = (
        _extra.pop('reader', None)
        or _extra.pop('wrapped', None)
        or _extra.pop('extractor', None)
        or _extra.pop('target', None)
    )
    metering = _extra.pop('metering', None)
    if metering is None:
        try:
            metering = _existing(_extra, 'metering', 'meter', 'metering_port')
        except Exception:
            metering = None
    if metering is None and _stack_switch(config, 'usage_metering_enabled', True):
        metering = build_metering(config=config, **_extra)
    tracing = _extra.pop('tracing', None)
    if tracing is None:
        try:
            tracing = _existing(
                _extra, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing'
            )
        except Exception:
            tracing = None
    if tracing is None and _stack_switch(config, 'detailed_tracing_enabled', True):
        tracing = build_tracing(config=config, **_extra)
    if reader is None:
        _tex = importlib.import_module('finsight.adapters.readers.textract_reader')
        TextractReader = _tex.TextractReader

        reader = TextractReader(config=config, **_extra)
    _rext = importlib.import_module('finsight.adapters.readers.retrying_extraction')
    RetryingExtraction = _rext.RetryingExtraction

    retrying = RetryingExtraction(reader)
    metered = MeteredExtraction(retrying, metering=metering)
    return TracedExtraction(metered, tracing=tracing)
