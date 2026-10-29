"""Property-based tests for parsers, config handling, money calculations, and cache keys."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from finsight.core.config.models import AppConfig, Environment
from finsight.domain.services.cache_key import build_answer_cache_key
from finsight.domain.value_objects.currency import Currency
from finsight.domain.value_objects.money import Money
from finsight.domain.value_objects.money_units import MoneyUnits


@dataclass
class _Context:
    company_id: str
    role: str
    access_scope: list[str]


pytestmark = pytest.mark.property


class TestMoneyProperty:
    @given(
        st.decimals(min_value=Decimal('-1000000'), max_value=Decimal('1000000'), places=4),
        st.sampled_from(list(Currency)),
        st.sampled_from(list(MoneyUnits)),
    )
    def test_money_preserves_decimal_amount_currency_and_units(
        self,
        amount: Decimal,
        currency: Currency,
        units: MoneyUnits,
    ) -> None:
        money = Money(amount=amount, currency=currency, units=units)

        assert money.amount == amount
        assert money.currency is currency
        assert money.units is units
        assert isinstance(money.amount, Decimal)
        assert not isinstance(money.amount, float)

    @given(
        st.decimals(min_value=Decimal('-1000000'), max_value=Decimal('1000000'), places=4),
        st.sampled_from(list(Currency)),
        st.sampled_from(list(MoneyUnits)),
    )
    @settings(max_examples=50)
    def test_money_str_contains_currency_and_units(
        self,
        amount: Decimal,
        currency: Currency,
        units: MoneyUnits,
    ) -> None:
        rendered = str(Money(amount=amount, currency=currency, units=units))

        assert currency.value in rendered
        assert units.value in rendered


class TestCacheKeyProperty:
    @given(
        st.text(min_size=1, max_size=40),
        st.text(min_size=0, max_size=80),
        st.lists(st.text(min_size=1, max_size=20), max_size=5),
        st.text(min_size=0, max_size=40),
    )
    def test_cache_key_is_deterministic(
        self,
        company_id: str,
        question: str,
        access_scope: list[str],
        document_stamp: str,
    ) -> None:
        context = _Context(
            company_id=company_id, role='audit_compliance', access_scope=access_scope
        )
        first = build_answer_cache_key(context, question, document_stamp)
        second = build_answer_cache_key(context, question, document_stamp)

        assert first == second
        assert len(first) == 64

    @given(st.text(min_size=1, max_size=40))
    def test_cache_key_changes_when_company_changes(self, company_id: str) -> None:
        first_context = _Context(company_id=company_id, role='audit_compliance', access_scope=[])
        second_context = _Context(
            company_id=company_id + '-other', role='audit_compliance', access_scope=[]
        )

        first = build_answer_cache_key(first_context, 'question', 'stamp')
        second = build_answer_cache_key(second_context, 'question', 'stamp')

        assert first != second

    @given(st.text(min_size=0, max_size=80))
    def test_cache_key_normalizes_question_whitespace(self, question: str) -> None:
        context = _Context(company_id='company', role='audit_compliance', access_scope=[])

        normalized = ' '.join(question.split())
        assert build_answer_cache_key(context, question, 'stamp') == build_answer_cache_key(
            context, normalized, 'stamp'
        )


class TestConfigHandlingProperty:
    @given(
        st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=40
        ),
        st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pd')),
            min_size=1,
            max_size=40,
        ),
        st.sampled_from(list(Environment)),
    )
    def test_valid_app_config_round_trips(
        self, name: str, version: str, environment: Environment
    ) -> None:
        config = AppConfig(name=name, version=version, environment=environment)

        assert config.name == name
        assert config.version == version
        assert config.environment is environment

    def test_config_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(
                name='app', version='1', environment=Environment.DEVELOPMENT, unknown_field='value'
            )

    @given(
        st.text(min_size=1, max_size=40).filter(
            lambda value: value not in {item.value for item in Environment}
        )
    )
    def test_config_rejects_invalid_environment(self, environment: str) -> None:
        with pytest.raises(ValidationError):
            AppConfig(name='app', version='1', environment=environment)  # type: ignore[arg-type]
