"""Result of diffing two versions of a document (pure domain)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeltaResult[T]:
    """Deterministic added/changed/removed/unchanged partition of identities."""

    added: tuple[T, ...] = ()
    changed: tuple[T, ...] = ()
    removed: tuple[T, ...] = ()
    unchanged: tuple[T, ...] = ()

    @property
    def has_changes(self) -> bool:
        """True when work may be needed (added, changed or removed entries)."""
        return bool(self.added or self.changed or self.removed)

    @property
    def to_process(self) -> tuple[T, ...]:
        """Identities that must be read or embedded (added then changed)."""
        return self.added + self.changed


__all__ = ['DeltaResult']
