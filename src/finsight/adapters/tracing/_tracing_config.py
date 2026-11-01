# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
"""Config helpers for tracing adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, Mapping):
            return arg
        if hasattr(arg, 'switches') or hasattr(arg, 'observability') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return None


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _config_switches(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, Mapping):
        return config.get('switches')
    return getattr(config, 'switches', None)


def _switch_value(switches: Any, *names: str, default: Any = True) -> Any:
    for name in names:
        if isinstance(switches, Mapping):
            if name in switches and switches.get(name) is not None:
                return switches.get(name)
        elif switches is not None and hasattr(switches, name):
            value = getattr(switches, name, None)
            if value is not None:
                return value
    return default


def _observability(config: Any) -> dict[str, Any]:
    obs_obj: Any = None
    if isinstance(config, Mapping):
        obs_obj = config.get('observability')
    elif config is not None:
        obs_obj = getattr(config, 'observability', None)
    result: dict[str, Any] = {
        'service_name': 'finsight-ai',
        'otlp_endpoint': '',
        'otlp_headers': {},
        'trace_sample_rate': 1.0,
    }
    if isinstance(obs_obj, Mapping):
        if obs_obj.get('service_name') is not None:
            result['service_name'] = obs_obj.get('service_name')
        if obs_obj.get('otlp_endpoint') is not None:
            result['otlp_endpoint'] = obs_obj.get('otlp_endpoint')
        if obs_obj.get('otlp_headers') is not None:
            result['otlp_headers'] = obs_obj.get('otlp_headers')
        if obs_obj.get('trace_sample_rate') is not None:
            result['trace_sample_rate'] = obs_obj.get('trace_sample_rate')
    elif obs_obj is not None:
        if getattr(obs_obj, 'service_name', None) is not None:
            result['service_name'] = obs_obj.service_name
        if getattr(obs_obj, 'otlp_endpoint', None) is not None:
            result['otlp_endpoint'] = obs_obj.otlp_endpoint
        if getattr(obs_obj, 'otlp_headers', None) is not None:
            result['otlp_headers'] = obs_obj.otlp_headers
        if getattr(obs_obj, 'trace_sample_rate', None) is not None:
            result['trace_sample_rate'] = obs_obj.trace_sample_rate
    elif config is not None:
        if isinstance(config, Mapping):
            if config.get('service_name') is not None:
                result['service_name'] = config.get('service_name')
            if config.get('otlp_endpoint') is not None:
                result['otlp_endpoint'] = config.get('otlp_endpoint')
        else:
            if getattr(config, 'service_name', None) is not None:
                result['service_name'] = config.service_name
            if getattr(config, 'otlp_endpoint', None) is not None:
                result['otlp_endpoint'] = config.otlp_endpoint
    return result


def _resolve_switch_enabled(config: Any, raw_enabled: Any) -> bool:
    if raw_enabled is not None:
        return bool(raw_enabled)
    switches = _config_switches(config)
    value = _switch_value(
        switches,
        'detailed_tracing_enabled',
        'tracing_enabled',
        'tracing',
        default=True,
    )
    return bool(value)


def _active_switch_values(switches_or_config: Any) -> dict[str, Any]:
    """Return a plain dict of active switch values (best-effort)."""

    switches = _config_switches(switches_or_config)
    if switches is None and hasattr(switches_or_config, 'config'):
        switches = _config_switches(getattr(switches_or_config, 'config', None))
    if switches is None:
        switches = switches_or_config
    if isinstance(switches, Mapping):
        try:
            return {str(k): v for k, v in switches.items()}
        except Exception:
            return {}
    if switches is None:
        return {}
    result: dict[str, Any] = {}
    try:
        for field in getattr(switches, 'model_fields', {}) or {}:
            value = getattr(switches, field, None)
            result[str(field)] = value
    except Exception:
        pass
    return result


TRACING_ALIAS_NAMES: tuple[str, ...] = (
    'Tracing',
    'Tracer',
    'TracingService',
    'SpanTracer',
    'TraceAdapter',
    'TracerAdapter',
    'TracingPortAdapter',
    'OpenTelemetryTracing',
    'OTelTracing',
    'OtelTracing',
    'OpenTelemetryTracer',
    'OtelTracer',
    'CloudWatchTracing',
    'StructuredTracing',
    'StructuredLogTracing',
    'LoggingTracing',
    'ConsoleTracing',
    'InMemoryTracing',
    'NoOpTracing',
    'DisabledTracing',
    'ActiveTracing',
    'TracingProvider',
    'SpanEmitter',
    'TraceEmitter',
    'TracingGateway',
    'TracePortAdapter',
)


def _ensure_standard_span_attributes(
    merged: dict[str, Any],
    passed_name: Any,
    operation: Any,
    config: Any,
) -> None:
    if passed_name is not None or operation is not None:
        merged.setdefault('step', passed_name if passed_name is not None else operation)
    merged.setdefault('operation_name', merged.get('step'))
    switches = _active_switch_values(config)
    if switches:
        merged.setdefault('active_switch_values', switches)
        merged.setdefault('active_switches', switches)
        merged.setdefault('switches', switches)
    merged.setdefault('duration', merged.get('duration_ms'))
    merged.setdefault('cache_hit', merged.get('cache_hit', False))
    merged.setdefault('retry_count', merged.get('retries', 0))
    merged.setdefault('queue_wait', merged.get('queue_wait_ms'))


def _name_from_kwargs(kwargs: dict[str, Any]) -> Any:
    for key in ('name', 'span_name', 'operation', 'operation_name', 'label'):
        if kwargs.get(key) is not None:
            return kwargs.get(key)
    return None
