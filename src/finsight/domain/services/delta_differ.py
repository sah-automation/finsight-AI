"""Deterministic page and chunk delta diffing (pure domain, no I/O)."""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING

from .delta_result import DeltaResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from finsight.core.types import ChunkId
    from finsight.domain.entities.chunk import Chunk


def _order_key(value: object) -> tuple[int, int | str]:
    if type(value) is int:
        return (0, value)
    if type(value) is str:
        return (1, value)
    return (2, repr(value))


def _ordered[Key: Hashable](values: Iterable[Key]) -> tuple[Key, ...]:
    return tuple(sorted(values, key=_order_key))


def _diff[Key: Hashable](
    previous: Mapping[Key, str],
    current: Mapping[Key, str],
) -> DeltaResult[Key]:
    added = _ordered(key for key in current if key not in previous)
    changed = _ordered(key for key in current if key in previous and previous[key] != current[key])
    removed = _ordered(key for key in previous if key not in current)
    unchanged = _ordered(
        key for key in current if key in previous and previous[key] == current[key]
    )
    return DeltaResult(
        added=added,
        changed=changed,
        removed=removed,
        unchanged=unchanged,
    )


class DeltaDiffer:
    """Compare previous and current page/chunk fingerprints without side effects."""

    def diff_pages[PageKey: Hashable](
        self,
        previous: Mapping[PageKey, str],
        current: Mapping[PageKey, str],
    ) -> DeltaResult[PageKey]:
        """Diff page hashes keyed by page identity (usually the page number)."""
        return _diff(previous, current)

    def diff_chunks(
        self,
        previous: Iterable[Chunk],
        current: Iterable[Chunk],
    ) -> DeltaResult[ChunkId]:
        """Diff two chunk collections by stable chunk id and content hash.

        Inactive previous chunks are ignored: a chunk that was removed before
        must be treated as new work if it reappears.
        """
        previous_hashes = _active_chunk_hashes(previous)
        current_hashes = _active_chunk_hashes(current)
        return _diff(previous_hashes, current_hashes)


def _active_chunk_hashes(chunks: Iterable[Chunk]) -> dict[ChunkId, str]:
    hashes: dict[ChunkId, str] = {}
    for chunk in chunks:
        if not chunk.is_active:
            continue
        if chunk.chunk_id in hashes:
            raise ValueError(f'Duplicate chunk_id in delta input: {chunk.chunk_id!r}')
        hashes[chunk.chunk_id] = chunk.content_hash
    return hashes
