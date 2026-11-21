"""Phase 2 KPI config validation tests (both-path matrix per spec §6.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finsight.core.config import Config, load_config, reset_config
from finsight.core.config.models.kpi_config import KPI_CODES, KpiConfig


def _base_config_dict() -> dict:
    """Load a base config dict for testing."""
    reset_config()
    cfg = load_config('test')
    return cfg.model_dump(mode='python', by_alias=True)


def _valid_kpi_dict(overrides: dict | None = None) -> dict:
    """Return a complete valid kpi config dict with optional overrides."""
    base = {
        'codes': list(KPI_CODES),
        'budget_vs_actual_match': 'strict',
        'estimation_methods': dict.fromkeys(KPI_CODES, 'quarterly_spread_equal'),
        'tolerances': {
            'revenue': {
                'kind': 'percent_of_expected_plus_absolute_floor',
                'percent': 0.5,
                'floor': 1000,
                'floor_unit': 'kpi_currency',
            },
            'gross_margin': {'kind': 'absolute', 'value': 0.25, 'unit': 'percentage_points'},
            'net_margin': {'kind': 'absolute', 'value': 0.25, 'unit': 'percentage_points'},
            'operating_expenses': {
                'kind': 'percent_of_expected_plus_absolute_floor',
                'percent': 0.5,
                'floor': 1000,
                'floor_unit': 'kpi_currency',
            },
            'cash_flow': {
                'kind': 'percent_of_expected_plus_absolute_floor',
                'percent': 0.5,
                'floor': 1000,
                'floor_unit': 'kpi_currency',
            },
            'burn_rate': {'kind': 'percent_of_expected', 'percent': 5},
            'runway': {'kind': 'percent_of_expected', 'percent': 5},
            'dso': {'kind': 'absolute', 'value': 3, 'unit': 'days'},
            'dpo': {'kind': 'absolute', 'value': 3, 'unit': 'days'},
            'budget_vs_actual': {'kind': 'exact_or_needs_review'},
        },
        'page_size_default': 50,
        'page_size_max': 100,
        'rebuild_batch_size': 10,
        'rebuild_priority': 'rebuilds',
    }
    if overrides:
        base.update(overrides)
    return base


class TestKpiCodes:
    """kpi.codes must be exactly the closed ten codes (ADR-0008)."""

    def test_exact_closed_ten_codes_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert frozenset(cfg.kpi.codes) == frozenset(KPI_CODES)

    def test_missing_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'codes': [c for c in KPI_CODES if c != 'revenue']})
        with pytest.raises(ValidationError, match=r'kpi\.codes must be exactly the closed set'):
            Config.model_validate(data)

    def test_extra_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'codes': [*list(KPI_CODES), 'unknown_code']})
        with pytest.raises(
            ValidationError,
            match=r"Input should be 'revenue', 'gross_margin', 'net_margin', 'operating_expenses', 'cash_flow', 'burn_rate', 'runway', 'dso', 'dpo' or 'budget_vs_actual'",
        ):
            Config.model_validate(data)

    def test_unknown_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'codes': ['unknown_code']})
        with pytest.raises(
            ValidationError,
            match=r"Input should be 'revenue', 'gross_margin', 'net_margin', 'operating_expenses', 'cash_flow', 'burn_rate', 'runway', 'dso', 'dpo' or 'budget_vs_actual'",
        ):
            Config.model_validate(data)

    def test_empty_codes_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'codes': []})
        with pytest.raises(ValidationError, match=r'kpi\.codes must be exactly the closed set'):
            Config.model_validate(data)


class TestBudgetVsActualMatch:
    """kpi.budget_vs_actual_match must be 'strict' only."""

    def test_strict_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'budget_vs_actual_match': 'strict'})
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert cfg.kpi.budget_vs_actual_match == 'strict'

    def test_non_strict_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'budget_vs_actual_match': 'lenient'})
        with pytest.raises(ValidationError, match="Input should be 'strict'"):
            Config.model_validate(data)


class TestTolerances:
    """kpi.tolerances must have four kinds with correct fields (discriminated union)."""

    def test_four_tolerance_kinds_pass(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert len(cfg.kpi.tolerances) == 10

    def test_unknown_kind_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'revenue': {'kind': 'unknown_kind', 'percent': 0.5},
                }
            }
        )
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_missing_fields_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'revenue': {'kind': 'percent_of_expected_plus_absolute_floor'},
                }
            }
        )
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_extra_fields_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'revenue': {**_valid_kpi_dict()['tolerances']['revenue'], 'extra_field': 1},
                }
            }
        )
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_percent_of_expected_plus_absolute_floor_floor_unit_validation(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'revenue': {
                        **_valid_kpi_dict()['tolerances']['revenue'],
                        'floor_unit': 'invalid_unit',
                    },
                }
            }
        )
        with pytest.raises(ValidationError, match="Input should be 'kpi_currency'"):
            Config.model_validate(data)

    def test_absolute_unit_validation(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'gross_margin': {
                        **_valid_kpi_dict()['tolerances']['gross_margin'],
                        'unit': 'invalid_unit',
                    },
                }
            }
        )
        with pytest.raises(ValidationError, match="Input should be 'percentage_points' or 'days'"):
            Config.model_validate(data)

    def test_tolerances_keys_must_match_codes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {'tolerances': {'revenue': _valid_kpi_dict()['tolerances']['revenue']}}
        )
        with pytest.raises(
            ValidationError, match=r'kpi\.tolerances keys must match kpi\.codes exactly'
        ):
            Config.model_validate(data)

    def test_tolerances_extra_keys_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'tolerances': {
                    **_valid_kpi_dict()['tolerances'],
                    'extra_code': {'kind': 'percent_of_expected', 'percent': 1},
                }
            }
        )
        with pytest.raises(
            ValidationError,
            match=r"Input should be 'revenue', 'gross_margin', 'net_margin', 'operating_expenses', 'cash_flow', 'burn_rate', 'runway', 'dso', 'dpo' or 'budget_vs_actual'",
        ):
            Config.model_validate(data)


class TestPageSize:
    """kpi.page_size_default/page_size_max positive ints with default <= max."""

    def test_positive_ints_default_le_max_pass(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'page_size_default': 50, 'page_size_max': 100})
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert cfg.kpi.page_size_default == 50
        assert cfg.kpi.page_size_max == 100

    def test_zero_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'page_size_default': 0})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_negative_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'page_size_default': -1})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_default_gt_max_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'page_size_default': 100, 'page_size_max': 50})
        with pytest.raises(
            ValidationError,
            match=r'Value error, kpi\.page_size_default must be <= kpi\.page_size_max',
        ):
            Config.model_validate(data)


class TestRebuildBatchSize:
    """kpi.rebuild_batch_size positive int."""

    def test_positive_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_batch_size': 10})
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert cfg.kpi.rebuild_batch_size == 10

    def test_zero_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_batch_size': 0})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_negative_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_batch_size': -1})
        with pytest.raises(ValidationError):
            Config.model_validate(data)


class TestRebuildPriority:
    """kpi.rebuild_priority must be 'rebuilds' or 'background' (both rank below live/upload)."""

    def test_rebuilds_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_priority': 'rebuilds'})
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert cfg.kpi.rebuild_priority == 'rebuilds'

    def test_background_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_priority': 'background'})
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert cfg.kpi.rebuild_priority == 'background'

    def test_live_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_priority': 'live'})
        with pytest.raises(ValidationError, match="Input should be 'rebuilds' or 'background'"):
            Config.model_validate(data)

    def test_upload_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_priority': 'upload'})
        with pytest.raises(ValidationError, match="Input should be 'rebuilds' or 'background'"):
            Config.model_validate(data)

    def test_unknown_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'rebuild_priority': 'unknown'})
        with pytest.raises(ValidationError, match="Input should be 'rebuilds' or 'background'"):
            Config.model_validate(data)


class TestEstimationMethods:
    """kpi.estimation_methods keys must match codes."""

    def test_all_codes_present_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {'estimation_methods': dict.fromkeys(KPI_CODES, 'quarterly_spread_equal')}
        )
        cfg = Config.model_validate(data)
        assert cfg.kpi is not None
        assert frozenset(cfg.kpi.estimation_methods.keys()) == frozenset(KPI_CODES)

    def test_missing_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'estimation_methods': {
                    c: 'quarterly_spread_equal' for c in KPI_CODES if c != 'revenue'
                }
            }
        )
        with pytest.raises(
            ValidationError, match=r'estimation_methods keys must match kpi\.codes exactly'
        ):
            Config.model_validate(data)

    def test_extra_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict(
            {
                'estimation_methods': {
                    **dict.fromkeys(KPI_CODES, 'quarterly_spread_equal'),
                    'extra': 'quarterly_spread_equal',
                }
            }
        )
        with pytest.raises(
            ValidationError,
            match=r"Input should be 'revenue', 'gross_margin', 'net_margin', 'operating_expenses', 'cash_flow', 'burn_rate', 'runway', 'dso', 'dpo' or 'budget_vs_actual'",
        ):
            Config.model_validate(data)


class TestExtraKeysForbidden:
    """extra='forbid' on all models; unknown/misspelled keys fail startup."""

    def test_unknown_top_level_key_rejected(self) -> None:
        data = _base_config_dict()
        data['unknown_section'] = {}
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_misspelled_kpi_key_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict({'budget_vs_actual_mach': 'strict'})
        with pytest.raises(ValidationError):
            Config.model_validate(data)


class TestKpiConfigModelDirectly:
    """Direct tests of KpiConfig model validation."""

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KpiConfig(unknown_field=True)  # type: ignore[call-arg]

    def test_misspelled_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KpiConfig(codes=list(KPI_CODES), budget_vs_actual_mach='strict')  # type: ignore[call-arg]
