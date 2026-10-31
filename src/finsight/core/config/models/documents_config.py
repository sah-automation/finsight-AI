from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .reader_names import _KNOWN_READER_NAMES_LOWER, _KNOWN_READER_NAMES_NORMALIZED
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    _MIN_ANSWER_CACHE_TTL_SECONDS,
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    _MIN_ROLE_CACHE_TTL_SECONDS,
    StrictBaseModel,
)


class DocumentsConfig(StrictBaseModel):
    reader: str = 'pdfplumber'
    scan_reader: str = 'tesseract'
    table_reader: str = 'pdfplumber'
    per_company_override: dict[str, dict[str, Any]] = Field(default_factory=dict)
    categories: list[str] = Field(
        default_factory=lambda: [
            'invoice',
            'bank_statement',
            'financial_statement',
            'budget',
            'contract',
            'board_report',
        ]
    )
    upload_types: list[str] = Field(default_factory=lambda: ['new', 'update'])
    delta_tracking: bool = True
    duplicate_check: bool = True
    version_retention_days: int = Field(ge=1, default=365)
    deleted_retention_days: int = Field(ge=1, default=30)
    source_original_link_ttl_seconds: int = Field(default=300, ge=60, le=900)
    source_viewer_signing_key: str = ''

    @field_validator('source_viewer_signing_key')
    @classmethod
    def validate_source_viewer_signing_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError('SOURCE_VIEWER_SIGNING_KEY must be configured')
        return value

    @property
    def source_viewer_secret(self) -> str:
        return self.source_viewer_signing_key

    @property
    def signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def citation_signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def source_viewer_key(self) -> str:
        return self.source_viewer_signing_key

    @field_validator('upload_types')
    @classmethod
    def validate_upload_types(cls, v: list[str]) -> list[str]:
        if set(v) != {'new', 'update'}:
            raise ValueError('upload_types must be exactly [new, update]')
        return v

    @staticmethod
    def _normalize_reader_name(value: object) -> str:
        return str(value).strip().lower().replace('_', '')

    @field_validator('reader', 'table_reader')
    @classmethod
    def validate_reader_name(cls, v: object) -> object:
        if v is None:
            raise ValueError('reader must resolve to a registered adapter')
        normalized = cls._normalize_reader_name(v)
        _none_values = {'none', 'null', 'off', 'false', 'disabled'}
        if normalized in _none_values:
            raise ValueError(f'Unknown reader name: {v!r}')
        if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
            raise ValueError(f'Unknown reader name: {v!r}')
        return v

    @field_validator('scan_reader')
    @classmethod
    def validate_scan_reader_name(cls, v: object) -> object:
        if v is None:
            return v
        normalized = cls._normalize_reader_name(v)
        _none_values = {'none', 'null', 'off', 'false', 'disabled'}
        if normalized in _none_values:
            return v
        if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
            raise ValueError(f'Unknown reader name: {v!r}')
        return v

    @model_validator(mode='after')
    def validate_per_company_reader_overrides(self) -> DocumentsConfig:
        overrides = self.per_company_override or {}
        if not isinstance(overrides, dict):
            raise TypeError('per_company_override must be a mapping')
        scan_none_values = {'none', 'null', 'off', 'false', 'disabled'}
        for company, override in overrides.items():
            if not isinstance(override, dict):
                raise TypeError(f'per-company override for {company!r} must be a mapping')
            targets = [override]
            nested = override.get('documents')
            if isinstance(nested, dict):
                targets.append(nested)
            for target in targets:
                for key, allow_none in (
                    ('reader', False),
                    ('scan_reader', True),
                    ('table_reader', False),
                ):
                    if key not in target:
                        continue
                    value = target.get(key)
                    if value is None:
                        if key == 'scan_reader' and allow_none:
                            continue
                        raise ValueError(f'Unknown reader name: {value!r}')
                    normalized = self._normalize_reader_name(value)
                    if allow_none and normalized in scan_none_values:
                        continue
                    if normalized in scan_none_values and not allow_none:
                        raise ValueError(f'Unknown reader name: {value!r}')
                    if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
                        raise ValueError(f'Unknown reader name: {value!r}')
        return self
