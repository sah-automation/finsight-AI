"""Shared work priorities used to keep rebuild jobs behind foreground work.

The rank map lives in ``core`` so both the waiting-line adapter and startup
validation agree on the ordering without either layer reaching into the other.
A larger rank means lower priority in quick-first ordering.
"""

from __future__ import annotations

_PRIORITY_RANKS: dict[str, int] = {
    'quick': 0,
    'question': 0,
    'search': 0,
    'rerank': 0,
    'model': 0,
    'upload': 1,
    'ingestion': 1,
    'report': 2,
    'reprocess': 2,
    'rebuilds': 3,
    'background': 3,
}
_LIVE_WORK = ('question', 'search', 'model')
_UPLOAD_WORK = ('upload', 'ingestion')
_REBUILD_WORK = ('rebuilds', 'background')


def priority_rank(value: object) -> int:
    """Map a work kind or numeric priority to a quick-first rank."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = '' if value is None else str(value).strip().lower()
    return _PRIORITY_RANKS.get(text, 1)


def assert_rebuild_priority_ordering() -> None:
    """Fail loudly unless both rebuild ranks sit below live and upload work."""
    live_rank = max(priority_rank(name) for name in _LIVE_WORK)
    upload_rank = max(priority_rank(name) for name in _UPLOAD_WORK)
    highest_foreground_rank = max(live_rank, upload_rank)
    for name in _REBUILD_WORK:
        rank = priority_rank(name)
        if rank <= highest_foreground_rank:
            raise ValueError(
                f'{name} priority rank {rank} must be below live questions '
                f'(rank {live_rank}) and uploads (rank {upload_rank})'
            )


__all__ = ['assert_rebuild_priority_ordering', 'priority_rank']
