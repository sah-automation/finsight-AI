"""Unit tests for the upload entrypoint partition gate."""

from __future__ import annotations

import asyncio

from finsight.entrypoints.api.upload import _partition_exists


def test_partition_exists_returns_true_when_all_deps_none() -> None:
    async def run() -> bool:
        return await _partition_exists(None, None, None, 'company-1')

    assert asyncio.run(run()) is True
