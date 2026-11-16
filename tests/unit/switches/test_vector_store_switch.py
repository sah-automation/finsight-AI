"""Switch test for vector_store."""

from __future__ import annotations

import pytest

from finsight.adapters.vector_store.aurora_pg_vector_write import AuroraPgVectorWrite
from finsight.adapters.vector_store.neon_pg_vector_write import NeonPgVectorWrite
from finsight.composition import build_vector_write
from finsight.core.config.models import SwitchesConfig


@pytest.mark.switch
class TestVectorStoreSwitch:
    """Tests for vector_store switch."""

    @pytest.mark.switch
    def test_vector_store_neon_on(self) -> None:
        switches = SwitchesConfig(vector_store='neon_pgvector')
        adapter = build_vector_write(config={'switches': switches})
        assert isinstance(adapter, NeonPgVectorWrite)

    @pytest.mark.switch
    def test_vector_store_aurora_on(self) -> None:
        switches = SwitchesConfig(vector_store='aurora_pgvector')
        adapter = build_vector_write(config={'switches': switches})
        assert isinstance(adapter, AuroraPgVectorWrite)

    @pytest.mark.switch
    def test_vector_store_invalid_off(self) -> None:
        with pytest.raises(ValueError):
            SwitchesConfig(vector_store='invalid_store')  # type: ignore[arg-type]
