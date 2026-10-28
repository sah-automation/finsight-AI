"""VirusScanResult value object returned by a VirusScanner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class VirusScanResult:
    """Result of scanning a stored object."""

    clean: bool
    detail: str | None = None

    @property
    def infected(self) -> bool:
        return not bool(self.clean)

    def __len__(self) -> int:
        return 2

    def __iter__(self) -> Iterator[object]:
        yield self.clean
        yield self.detail

    def __getitem__(self, key: object) -> object:
        if isinstance(key, str):
            if key in {'clean', 'is_clean'}:
                return self.clean
            if key in {'detail', 'message'}:
                return self.detail
            if key in {'infected', 'is_infected'}:
                return self.infected
            raise KeyError(key)
        if isinstance(key, int):
            return (self.clean, self.detail)[key]
        raise TypeError('VirusScanResult key must be str or int')

    def get(self, key: str, default: object = None) -> object:
        try:
            return self[key]
        except KeyError:
            return default


__all__ = ['VirusScanResult']
