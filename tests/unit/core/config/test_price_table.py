"""Tests for the config-driven price table used by metering."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.core.config.price_table import (
    PriceNotFoundError,
    PriceTable,
    load_price_table,
)


class TestRepositoryPriceTable:
    def test_loads_llm_prices_and_token_scale(self) -> None:
        table = load_price_table()

        assert table.price_for('anthropic/claude-3-5-sonnet-20241022') == Decimal('3.00')
        assert table.unit_scale('anthropic/claude-3-5-sonnet-20241022') == Decimal(1_000_000)

    def test_loads_embedding_prices(self) -> None:
        table = load_price_table()

        assert table.price_for('amazon/titan-embed-text-v2:0') == Decimal('0.02')

    def test_reranker_uses_thousand_document_scale(self) -> None:
        table = load_price_table()

        assert table.unit_scale('cohere/rerank-english-v3.0') == Decimal(1_000)
        assert table.cost_for('cohere/rerank-english-v3.0', 2_000) == Decimal('2.00')

    def test_loads_nested_service_prices(self) -> None:
        table = load_price_table()

        assert table.service_price('textract', 'detect_document_text') == Decimal('0.0015')
        assert table.service_price('dynamodb', 'write_request_units') == Decimal('1.25')

    def test_missing_model_price_raises(self) -> None:
        table = load_price_table()

        with pytest.raises(PriceNotFoundError):
            table.price_for('provider/unknown-model')

    def test_require_models_reports_every_missing_price(self) -> None:
        table = load_price_table()

        with pytest.raises(PriceNotFoundError) as error:
            table.require_models(['anthropic/claude-3-5-sonnet-20241022', 'provider/missing-a'])

        assert 'provider/missing-a' in str(error.value)

    def test_require_models_accepts_configured_models(self) -> None:
        table = load_price_table()

        table.require_models(
            [
                'anthropic/claude-3-5-sonnet-20241022',
                'anthropic/claude-3-5-haiku-20241022',
                'openai/gpt-4o-mini',
                'amazon/titan-embed-text-v2:0',
            ]
        )


class TestCustomPriceTable:
    def test_scales_and_sections_come_from_config(self) -> None:
        table = PriceTable(
            {
                'unit_scales': {'per_token': 100, 'per_call': 1},
                'price_sections': {
                    'llm_models': {'scale': 'per_token'},
                    'aws_services': {'scale': 'per_call'},
                },
                'llm_models': {'vendor/model': {'input': 2}},
                'aws_services': {'custom': {'call': 0.50}},
            }
        )

        assert table.price_for('vendor/model') == Decimal(2)
        assert table.unit_scale('vendor/model') == Decimal(100)
        assert table.cost_for('vendor/model', 250) == Decimal('5')
        assert table.service_price('custom', 'call') == Decimal('0.50')

    def test_missing_section_price_raises(self) -> None:
        table = PriceTable({'llm_models': {'vendor/model': {'input': 1}}})

        with pytest.raises(PriceNotFoundError):
            table.service_price('missing-service')

    def test_cost_for_requires_a_positive_scale(self) -> None:
        table = PriceTable(
            {
                'price_sections': {'llm_models': {'scale': 'bad'}},
                'unit_scales': {'bad': 0},
                'llm_models': {'vendor/model': {'input': 1}},
            }
        )

        with pytest.raises(PriceNotFoundError):
            table.cost_for('vendor/model', 1)
