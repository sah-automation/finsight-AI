# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
from typing import Any

from finsight.domain.value_objects.virus_scan_result import VirusScanResult

_CLEAN_TOKENS = {
    'clean',
    'ok',
    'okay',
    'passed',
    'pass',
    'safe',
    'no_threat',
    'no_threats',
    'none',
    'negative',
}

_INFECTED_TOKENS = {
    'infected',
    'malware',
    'virus',
    'threat',
    'threat_detected',
    'dirty',
    'positive',
    'rejected',
    'failed',
    'error',
    'unscannable',
}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _as_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode('utf-8', 'replace')
    if hasattr(value, 'read'):
        try:
            raw = value.read()
            if hasattr(value, 'seek'):
                try:
                    value.seek(0)
                except Exception:
                    pass
            if isinstance(raw, (bytes, bytearray, str)):
                return _as_bytes(raw)
        except Exception:
            return None
    if isinstance(value, dict):
        for key in ('content', 'data', 'bytes', 'body', 'file', 'payload'):
            if value.get(key) is not None:
                found = _as_bytes(value.get(key))
                if found is not None:
                    return found
    for attr in ('content', 'data', 'bytes', 'body', 'file', 'payload'):
        candidate = getattr(value, attr, None)
        if candidate is not None and candidate is not value:
            found = _as_bytes(candidate)
            if found is not None:
                return found
    return None


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is not None and (
            hasattr(arg, 'ingestion') or hasattr(arg, 'switches') or hasattr(arg, 'storage')
        ):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        cfg = getattr(arg, 'config', None)
        if cfg is not None:
            return cfg
    return None


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


def _resolve_enabled(config: Any, kwargs: dict[str, Any]) -> bool:
    # Explicit constructor knobs take precedence.
    explicit_keys = (
        'enabled',
        'virus_scan_enabled',
        'scan_enabled',
        'virus_scanning_enabled',
        'enabled_virus_scan',
    )
    for key in explicit_keys:
        if key in kwargs and kwargs.get(key) is not None:
            value = kwargs.get(key)
            try:
                return bool(value)
            except Exception:
                pass
    # Config-driven resolution.
    if config is not None:
        candidates = []
        if hasattr(config, 'ingestion'):
            candidates.append(getattr(config.ingestion, 'virus_scan_enabled', None))
        if hasattr(config, 'virus_scan_enabled'):
            candidates.append(getattr(config, 'virus_scan_enabled', None))
        if hasattr(config, 'switches'):
            switches = getattr(config, 'switches', None)
            if switches is not None and hasattr(switches, 'virus_scan_enabled'):
                candidates.append(getattr(switches, 'virus_scan_enabled', None))
        if isinstance(config, dict):
            candidates.append((config.get('ingestion') or {}).get('virus_scan_enabled'))
            candidates.append(config.get('virus_scan_enabled'))
        for candidate in candidates:
            if candidate is not None:
                try:
                    return bool(candidate)
                except Exception:  # noqa: S112
                    continue
    return True


def _coerce_result(value: Any, *, default_detail: str | None = None) -> VirusScanResult:
    if isinstance(value, VirusScanResult):
        return value

    if isinstance(value, bool):
        return VirusScanResult(clean=bool(value), detail=default_detail)

    if isinstance(value, str):
        token = value.strip().lower().replace(' ', '_').replace('-', '_')
        if token in _CLEAN_TOKENS:
            return VirusScanResult(clean=True, detail=value)
        if token in _INFECTED_TOKENS:
            return VirusScanResult(clean=False, detail=value)
        # Unknown textual result: treat non-empty as infected to stay fail-closed-ish.
        return VirusScanResult(clean=False, detail=value or default_detail)

    if isinstance(value, dict):
        clean_val = None
        for key in ('clean', 'is_clean', 'ok', 'passed', 'safe'):
            if key in value:
                clean_val = value.get(key)
                break
        infected_val = None
        for key in ('infected', 'is_infected', 'malware', 'threat', 'threat_detected'):
            if key in value:
                infected_val = value.get(key)
                break
        if clean_val is not None:
            detail = None
            for key in ('detail', 'message', 'reason', 'status', 'result'):
                if key in value and value.get(key) is not None:
                    detail = _coerce_str(value.get(key))
                    break
            return VirusScanResult(clean=bool(clean_val), detail=detail or default_detail)
        if infected_val is not None:
            detail = None
            for key in ('detail', 'message', 'reason', 'status', 'result'):
                if key in value and value.get(key) is not None:
                    detail = _coerce_str(value.get(key))
                    break
            return VirusScanResult(clean=not bool(infected_val), detail=detail or default_detail)

        # Status/result tokens.
        for key in ('status', 'result', 'verdict', 'scan_result', 'outcome', 'state'):
            if key in value and value.get(key) is not None:
                token = (
                    _coerce_str(value.get(key)).strip().lower().replace(' ', '_').replace('-', '_')
                )
                if token in _CLEAN_TOKENS:
                    detail = None
                    for dkey in ('detail', 'message', 'reason'):
                        if dkey in value and value.get(dkey) is not None:
                            detail = _coerce_str(value.get(dkey))
                            break
                    return VirusScanResult(clean=True, detail=detail or _coerce_str(value.get(key)))
                if token in _INFECTED_TOKENS:
                    detail = None
                    for dkey in ('detail', 'message', 'reason'):
                        if dkey in value and value.get(dkey) is not None:
                            detail = _coerce_str(value.get(dkey))
                            break
                    return VirusScanResult(
                        clean=False, detail=detail or _coerce_str(value.get(key))
                    )
        # Error fields.
        for key in ('error', 'exception', 'failure'):
            if key in value and value.get(key) is not None:
                return VirusScanResult(clean=False, detail=_coerce_str(value.get(key)))
        if value:
            return VirusScanResult(clean=False, detail=default_detail or 'scan result not clean')
        return VirusScanResult(clean=True, detail=default_detail)

    # Objects exposing attributes.
    for attr in ('clean', 'is_clean'):
        if hasattr(value, attr):
            try:
                return VirusScanResult(
                    clean=bool(getattr(value, attr)),
                    detail=getattr(value, 'detail', None) or getattr(value, 'message', None),
                )
            except Exception:
                pass
    for attr in ('infected', 'is_infected'):
        if hasattr(value, attr):
            try:
                return VirusScanResult(
                    clean=not bool(getattr(value, attr)),
                    detail=getattr(value, 'detail', None) or getattr(value, 'message', None),
                )
            except Exception:
                pass
    # Try common callables.
    if callable(value):
        try:
            return _coerce_result(value(), default_detail=default_detail)
        except Exception:
            pass

    return VirusScanResult(clean=False, detail=_coerce_str(value) or default_detail)


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


__all__ = [
    '_CLEAN_TOKENS',
    '_INFECTED_TOKENS',
    '_as_bytes',
    '_await_if_needed',
    '_coerce_result',
    '_coerce_str',
    '_first',
    '_resolve_config',
    '_resolve_enabled',
]
