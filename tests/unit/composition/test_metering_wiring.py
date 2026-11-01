"""Tests that the metering adapter is wired through the composition root."""

from __future__ import annotations

from finsight.adapters.metering.dynamo_metering import DynamoMetering
from finsight.composition import build_container, build_metering
from finsight.core.config.loader import load_config


def test_build_metering_selects_the_dynamo_adapter() -> None:
    assert isinstance(build_metering(), DynamoMetering)


def test_metering_adapter_uses_the_configured_table_and_prices() -> None:
    config = load_config('test')

    metering = build_metering(config=config)

    assert isinstance(metering, DynamoMetering)
    assert metering.table_name == config.metering.table_name
    assert metering.price_table is not None
    metering.price_table.require_models(
        [
            config.llm.primary_model.model_id,
            config.llm.embedding_model.model_id,
        ]
    )


def test_container_exposes_the_metering_adapter() -> None:
    container = build_container(config=load_config('test'))

    assert isinstance(container.metering, DynamoMetering)
    assert container.meter is container.metering
    assert container.metering_port is container.metering
    assert container['metering'] is container.metering
    assert container.adapters['metering'] is container.metering


def test_injected_metering_adapter_is_preserved() -> None:
    metering = DynamoMetering(table_name='injected-metering')

    container = build_container(config=load_config('test'), metering=metering)

    assert container.metering is metering
