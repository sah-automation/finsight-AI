"""Config-driven price table.

Prices live only in ``config/prices.yaml``. This module reads that file into a
typed lookup used by the metering adapter and by startup validation. Missing
prices raise :class:`PriceNotFoundError` so an unpriced call stops startup
instead of silently recording a zero cost.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .loader import ConfigError

_METADATA_KEYS = frozenset({'currency', 'price_sections', 'unit', 'unit_scales'})
_FIELD_ORDER = ('input', 'per_1k_docs', 'per_1k', 'per_unit', 'output')
_MODEL_SUFFIX = '_models'


class PriceNotFoundError(ConfigError):
    """Raised when configuration has no price for a billable item."""


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        raise InvalidOperation
    return Decimal(str(value))


def _first_price(entry: Mapping[str, Any], field: str | None = None) -> Decimal:
    names = (field,) if field is not None else _FIELD_ORDER
    for name in names:
        value = entry.get(name)
        if value is not None:
            try:
                return _as_decimal(value)
            except (InvalidOperation, TypeError, ValueError):
                continue
    if field is None:
        for value in entry.values():
            if isinstance(value, Mapping):
                continue
            try:
                return _as_decimal(value)
            except (InvalidOperation, TypeError, ValueError):
                continue
    raise PriceNotFoundError(f'No numeric price in entry: {dict(entry)!r}')


class PriceTable:
    """Read-only lookup over the configured prices."""

    def __init__(self, prices: Mapping[str, Any], *, source: str | None = None) -> None:
        self.source = source
        self.currency = str(
            (prices.get('currency') if isinstance(prices, Mapping) else None) or 'USD'
        )
        self._unit_scales: dict[str, Decimal] = {}
        self._section_scales: dict[str, str] = {}
        self._sections: dict[str, dict[str, Any]] = {}
        self._flat: dict[tuple[str, str], Decimal] = {}

        raw_scales = prices.get('unit_scales', {}) or {}
        if isinstance(raw_scales, Mapping):
            for name, value in raw_scales.items():
                try:
                    self._unit_scales[str(name)] = _as_decimal(value)
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise ConfigError(f'Invalid unit scale for {name!r}: {value!r}') from exc

        raw_sections = prices.get('price_sections', {}) or {}
        if isinstance(raw_sections, Mapping):
            for name, value in raw_sections.items():
                scale = value.get('scale') if isinstance(value, Mapping) else value
                self._section_scales[str(name)] = str(scale or 'per_unit')

        for section, entries in prices.items():
            if section in _METADATA_KEYS or not isinstance(entries, Mapping):
                continue
            self._sections[str(section)] = dict(entries)
            self._flatten(str(section), entries)

    @classmethod
    def from_file(cls, path: Path | str) -> PriceTable:
        source = Path(path)
        if not source.exists():
            raise ConfigError(f'Price table not found: {source}')
        try:
            data = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f'Invalid price table {source}: {exc}') from exc
        if not isinstance(data, Mapping):
            raise ConfigError(f'Price table {source} must contain a mapping')
        return cls(data, source=str(source))

    def _flatten(self, section: str, entries: Mapping[str, Any], prefix: str = '') -> None:
        for name, value in entries.items():
            key = f'{prefix}.{name}' if prefix else str(name)
            if isinstance(value, Mapping):
                self._flatten(section, value, key)
                continue
            try:
                self._flat[(section, key)] = _as_decimal(value)
            except (InvalidOperation, TypeError, ValueError):
                continue

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def sections(self) -> tuple[str, ...]:
        """Return the configured price section names."""
        return tuple(self._sections)

    def models(self) -> set[str]:
        """Return all configured model identifiers."""
        return {
            name
            for section, entries in self._sections.items()
            if section.endswith(_MODEL_SUFFIX)
            for name in entries
        }

    def price_for(
        self,
        name: str,
        *,
        section: str | None = None,
        field: str | None = None,
    ) -> Decimal:
        """Return the configured price for a model."""
        for candidate in self._search_sections(section, model_only=True):
            price = self._price_in(candidate, name, field=field)
            if price is not None:
                return price
        raise PriceNotFoundError(f'No price configured for model {name!r} in {self.source!r}')

    def unit_scale(self, name: str, *, section: str | None = None) -> Decimal:
        for candidate in self._search_sections(section, model_only=True):
            if name in self._sections.get(candidate, {}) or (candidate, name) in self._flat:
                return self._scale_for(candidate)
        raise PriceNotFoundError(f'No price configured for model {name!r} in {self.source!r}')

    def cost_for(
        self,
        name: str,
        units: object,
        *,
        section: str | None = None,
        field: str | None = None,
    ) -> Decimal:
        """Return the cost for a given number of units."""
        price = self.price_for(name, section=section, field=field)
        scale = self.unit_scale(name, section=section)
        if scale <= 0:
            raise PriceNotFoundError(f'Unit scale for {name!r} must be positive')
        return price * _as_decimal(units) / scale

    def service_price(self, service: str, operation: str | None = None) -> Decimal:
        """Return the configured price for a service operation."""
        name = f'{service}.{operation}' if operation else service
        for candidate in self._search_sections(None, model_only=False):
            price = self._price_in(candidate, name)
            if price is not None:
                return price
            if operation is not None:
                entry = self._sections.get(candidate, {}).get(service)
                if isinstance(entry, Mapping) and entry.get(operation) is not None:
                    return _as_decimal(entry[operation])
        raise PriceNotFoundError(f'No price configured for service {name!r} in {self.source!r}')

    def service_cost(
        self,
        service: str,
        units: object,
        operation: str | None = None,
    ) -> Decimal:
        """Return the cost for service units."""
        value = self.service_price(service, operation)
        return value * _as_decimal(units)

    def require_models(self, model_ids: Iterable[str]) -> None:
        """Raise when any configured model price is missing."""
        missing = sorted({str(model) for model in model_ids if not self._has_model(str(model))})
        if missing:
            raise PriceNotFoundError(
                f'Missing prices for models: {", ".join(missing)} (source: {self.source!r})'
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _has_model(self, name: str) -> bool:
        return any(
            self._price_in(section, name) is not None
            for section in self._search_sections(None, model_only=True)
        )

    def _search_sections(self, section: str | None, *, model_only: bool) -> list[str]:
        if section is not None:
            return [section]
        if model_only:
            models = [name for name in self._sections if name.endswith(_MODEL_SUFFIX)]
            return models or list(self._sections)
        return list(self._sections)

    def _price_in(self, section: str, name: str, field: str | None = None) -> Decimal | None:
        entry = self._sections.get(section, {}).get(name)
        if entry is not None and not isinstance(entry, Mapping):
            try:
                return _as_decimal(entry)
            except (InvalidOperation, TypeError, ValueError):
                return None
        if isinstance(entry, Mapping):
            try:
                return _first_price(entry, field)
            except PriceNotFoundError:
                return None
        return self._flat.get((section, name))

    def _scale_for(self, section: str) -> Decimal:
        scale_name = self._section_scales.get(section, 'per_unit')
        if scale_name not in self._unit_scales:
            raise PriceNotFoundError(
                f'Unit scale {scale_name!r} for section {section!r} is not configured'
            )
        value = self._unit_scales[scale_name]
        if value <= 0:
            raise PriceNotFoundError(f'Unit scale {scale_name!r} must be positive')
        return value


def _default_price_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / 'config' / 'prices.yaml'
        if candidate.exists():
            return candidate
    return Path.cwd() / 'config' / 'prices.yaml'


def load_price_table(path: Path | str | None = None) -> PriceTable:
    return PriceTable.from_file(path if path is not None else _default_price_path())


__all__ = ['PriceNotFoundError', 'PriceTable', 'load_price_table']
