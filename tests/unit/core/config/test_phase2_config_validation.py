"""Phase 2 config validation tests (both-path matrix per spec §6.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finsight.core.config import Config, load_config, reset_config
from finsight.core.config.models.charts_config import ChartsConfig
from finsight.core.config.models.dashboard_config import (
    DashboardConfig,
)
from finsight.core.config.models.golden_set_config import GoldenSetConfig
from finsight.core.config.models.kpi_config import KPI_CODES, KpiConfig
from finsight.core.config.models.vercel_config import VercelConfig


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


def _valid_charts_dict(overrides: dict | None = None) -> dict:
    """Return a complete valid charts config dict with optional overrides."""
    base = {
        'specs': {
            'revenue_trend': {
                'chart_id': 'revenue_trend',
                'chart_type': 'trend_line',
                'kpi_codes': ['revenue'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'higher_is_better',
            },
            'margin_trend': {
                'chart_id': 'margin_trend',
                'chart_type': 'trend_line',
                'kpi_codes': ['gross_margin', 'net_margin'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'higher_is_better',
            },
            'cash_flow_comparison': {
                'chart_id': 'cash_flow_comparison',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['cash_flow'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'higher_is_better',
            },
            'expense_comparison': {
                'chart_id': 'expense_comparison',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['operating_expenses'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'lower_is_better',
            },
            'burn_comparison': {
                'chart_id': 'burn_comparison',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['burn_rate'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'lower_is_better',
            },
            'runway_comparison': {
                'chart_id': 'runway_comparison',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['runway'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'higher_is_better',
            },
            'collection_periods': {
                'chart_id': 'collection_periods',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['dso', 'dpo'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': False,
                'polarity': 'lower_is_better',
            },
            'budget_variance': {
                'chart_id': 'budget_variance',
                'chart_type': 'comparison_bar',
                'kpi_codes': ['budget_vs_actual'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': [],
                'diverging': True,
                'polarity': 'neutral',
            },
            'revenue_breakdown': {
                'chart_id': 'revenue_breakdown',
                'chart_type': 'breakdown_bar',
                'kpi_codes': ['revenue'],
                'supported_periods': [4, 6, 8],
                'periods_selectable': [2, 3, 4],
                'breakdown_keys': ['document_category'],
                'diverging': False,
                'polarity': 'higher_is_better',
            },
        },
        'export_formats': ['png', 'pdf'],
    }
    if overrides:
        base.update(overrides)
    return base


def _valid_dashboard_dict(overrides: dict | None = None) -> dict:
    """Return a complete valid dashboard config dict with optional overrides."""
    base = {
        'auto_refresh_seconds': 30,
        'default_layout': {
            'kpi_codes': [
                'revenue',
                'gross_margin',
                'net_margin',
                'operating_expenses',
                'cash_flow',
                'burn_rate',
            ],
            'charts': [
                {'chart_id': 'revenue_trend', 'span': 'full'},
                {'chart_id': 'margin_trend', 'span': 'half'},
            ],
        },
        'staleness_badge_enabled': True,
    }
    if overrides:
        base.update(overrides)
    return base


def _valid_web_vercel_dict(overrides: dict | None = None) -> dict:
    """Return a complete valid web.vercel config dict with optional overrides."""
    base = {
        'vercel': {
            'sync_enabled': True,
            'preview_api_target': 'mock',
            'log_forwarding_enabled': True,
            'log_retention_days': 30,
            'never_log_file': 'config/never_log.yaml',
            'otlp_log_group': '/aws/finsight/web-prod',
        },
    }
    if overrides:
        # Handle nested overrides for vercel
        if 'vercel' in overrides:
            base['vercel'].update(overrides['vercel'])
        else:
            base.update(overrides)
    return base


def _valid_golden_set_dict(overrides: dict | None = None) -> dict:
    """Return a complete valid golden_set config dict with optional overrides."""
    base = {
        'kpi_questions_path': 'tests/golden/questions/phase2_kpi.yaml',
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


class TestChartsSpecs:
    """charts.specs validation (9 chart specs per Phase 2 spec §6, closed enum, diverging only on budget_variance)."""

    def test_all_nine_specs_pass(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        cfg = Config.model_validate(data)
        assert cfg.charts is not None
        assert len(cfg.charts.specs) == 9

    def test_chart_type_closed_enum(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'chart_type': 'breakdown_pie',
                    },
                },
            }
        )
        with pytest.raises(
            ValidationError,
            match="Input should be 'trend_line', 'comparison_bar' or 'breakdown_bar'",
        ):
            Config.model_validate(data)

    def test_unknown_chart_type_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'chart_type': 'unknown_type',
                    },
                },
            }
        )
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_diverging_true_only_on_budget_variance(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'diverging': True,
                    },
                },
            }
        )
        # The first validation check is for chart_type (must be comparison_bar)
        with pytest.raises(
            ValidationError, match='diverging=true only allowed on comparison_bar type'
        ):
            Config.model_validate(data)

    def test_diverging_true_only_on_budget_vs_actual(self) -> None:
        """Test diverging=true only allowed for budget_vs_actual kpi_code."""
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'chart_type': 'comparison_bar',
                        'diverging': True,
                    },
                },
            }
        )
        with pytest.raises(
            ValidationError, match='diverging=true only allowed for budget_vs_actual'
        ):
            Config.model_validate(data)

    def test_diverging_true_requires_comparison_bar(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'budget_variance': {
                        **_valid_charts_dict()['specs']['budget_variance'],
                        'chart_type': 'trend_line',
                    },
                },
            }
        )
        with pytest.raises(
            ValidationError, match='diverging=true only allowed on comparison_bar type'
        ):
            Config.model_validate(data)

    def test_kpi_codes_must_be_valid(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'kpi_codes': ['unknown_kpi'],
                    },
                },
            }
        )
        with pytest.raises(ValidationError, match='unknown KPI code: unknown_kpi'):
            Config.model_validate(data)

    def test_breakdown_keys_only_allowed_values(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    **_valid_charts_dict()['specs'],
                    'revenue_breakdown': {
                        **_valid_charts_dict()['specs']['revenue_breakdown'],
                        'breakdown_keys': ['invalid_key'],
                    },
                },
            }
        )
        with pytest.raises(ValidationError, match="Input should be 'document_category'"):
            Config.model_validate(data)

    def test_chart_id_must_match_key(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'specs': {
                    'revenue_trend': {
                        **_valid_charts_dict()['specs']['revenue_trend'],
                        'chart_id': 'mismatched_id',
                    },
                },
            }
        )
        with pytest.raises(ValidationError, match='chart_id must match key: revenue_trend'):
            Config.model_validate(data)

    def test_export_formats_subset_of_allowed(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'export_formats': ['png', 'pdf', 'svg'],
            }
        )
        with pytest.raises(ValidationError, match="Input should be 'png' or 'pdf'"):
            Config.model_validate(data)

    def test_export_formats_empty_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict(
            {
                'export_formats': [],
            }
        )
        # empty list is allowed by the model, but our validator checks for subset
        cfg = Config.model_validate(data)
        assert cfg.charts is not None
        assert cfg.charts.export_formats == []

    def test_missing_specs_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = {'export_formats': ['png', 'pdf']}
        with pytest.raises(ValidationError):
            Config.model_validate(data)


class TestDashboardConfig:
    """dashboard validation (auto_refresh 5-300, default_layout resolvable, staleness_badge_enabled fixed true)."""

    def test_auto_refresh_seconds_valid_range(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict({'auto_refresh_seconds': 5})
        cfg = Config.model_validate(data)
        assert cfg.dashboard is not None
        assert cfg.dashboard.auto_refresh_seconds == 5

        data['dashboard'] = _valid_dashboard_dict({'auto_refresh_seconds': 300})
        cfg = Config.model_validate(data)
        assert cfg.dashboard.auto_refresh_seconds == 300

    def test_auto_refresh_below_min_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict({'auto_refresh_seconds': 4})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_auto_refresh_above_max_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict({'auto_refresh_seconds': 301})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_default_layout_kpi_codes_resolvable(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue', 'gross_margin'],
                    'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}],
                },
            }
        )
        cfg = Config.model_validate(data)
        assert cfg.dashboard is not None
        assert cfg.dashboard.default_layout.kpi_codes == ['revenue', 'gross_margin']

    def test_default_layout_unknown_kpi_code_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue', 'unknown_code'],
                    'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}],
                },
            }
        )
        with pytest.raises(ValidationError, match='unknown KPI code: unknown_code'):
            Config.model_validate(data)

    def test_default_layout_duplicate_kpi_codes_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue', 'revenue'],
                    'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}],
                },
            }
        )
        with pytest.raises(ValidationError, match='must not contain duplicates'):
            Config.model_validate(data)

    def test_default_layout_charts_resolvable(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue'],
                    'charts': [{'chart_id': 'revenue_trend', 'span': 'full'}],
                },
            }
        )
        cfg = Config.model_validate(data)
        assert cfg.dashboard is not None
        assert len(cfg.dashboard.default_layout.charts) == 1

    def test_default_layout_unknown_chart_id_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue'],
                    'charts': [{'chart_id': 'unknown_chart', 'span': 'full'}],
                },
            }
        )
        with pytest.raises(ValidationError, match='unknown chart_id: unknown_chart'):
            Config.model_validate(data)

    def test_default_layout_span_must_be_full_or_half(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue'],
                    'charts': [{'chart_id': 'revenue_trend', 'span': 'quarter'}],
                },
            }
        )
        with pytest.raises(ValidationError, match="Input should be 'full' or 'half'"):
            Config.model_validate(data)

    def test_default_layout_duplicate_chart_ids_rejected(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict(
            {
                'default_layout': {
                    'kpi_codes': ['revenue'],
                    'charts': [
                        {'chart_id': 'revenue_trend', 'span': 'full'},
                        {'chart_id': 'revenue_trend', 'span': 'half'},
                    ],
                },
            }
        )
        with pytest.raises(ValidationError, match='must not contain duplicate chart_ids'):
            Config.model_validate(data)

    def test_staleness_badge_enabled_must_be_true(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict({'staleness_badge_enabled': False})
        with pytest.raises(ValidationError, match='staleness_badge_enabled must be true'):
            Config.model_validate(data)

    def test_staleness_badge_enabled_true_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict({'staleness_badge_enabled': True})
        cfg = Config.model_validate(data)
        assert cfg.dashboard is not None
        assert cfg.dashboard.staleness_badge_enabled is True


class TestWebVercelConfig:
    """web.vercel validation (sync_enabled fixed true, preview_api_target mock only, log_forwarding_enabled fixed true)."""

    def test_valid_web_vercel_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict()
        cfg = Config.model_validate(data)
        assert cfg.web is not None
        assert cfg.web.vercel is not None
        assert cfg.web.vercel.sync_enabled is True
        assert cfg.web.vercel.preview_api_target == 'mock'
        assert cfg.web.vercel.log_forwarding_enabled is True

    def test_sync_enabled_must_be_true(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'sync_enabled': False}})
        with pytest.raises(ValidationError, match='sync_enabled must be true'):
            Config.model_validate(data)

    def test_preview_api_target_must_be_mock(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'preview_api_target': 'staging'}})
        with pytest.raises(ValidationError, match="Input should be 'mock'"):
            Config.model_validate(data)

        data['web'] = _valid_web_vercel_dict({'vercel': {'preview_api_target': 'production'}})
        with pytest.raises(ValidationError, match="Input should be 'mock'"):
            Config.model_validate(data)

    def test_log_forwarding_enabled_must_be_true(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'log_forwarding_enabled': False}})
        with pytest.raises(ValidationError, match='log_forwarding_enabled must be true'):
            Config.model_validate(data)

    def test_log_retention_days_positive(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'log_retention_days': 0}})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

        data['web'] = _valid_web_vercel_dict({'vercel': {'log_retention_days': -1}})
        with pytest.raises(ValidationError):
            Config.model_validate(data)

    def test_never_log_file_non_empty(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'never_log_file': ''}})
        with pytest.raises(ValidationError, match='never_log_file must be non-empty'):
            Config.model_validate(data)

    def test_otlp_log_group_non_empty(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict({'vercel': {'otlp_log_group': ''}})
        with pytest.raises(ValidationError, match='String should have at least 1 character'):
            Config.model_validate(data)


class TestGoldenSetConfig:
    """golden_set validation (kpi_questions_path under tests/golden/questions/, tolerances_file forbidden)."""

    def test_valid_golden_set_passes(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict()
        data['golden_set'] = _valid_golden_set_dict()
        cfg = Config.model_validate(data)
        assert cfg.golden_set is not None
        assert cfg.golden_set.kpi_questions_path == 'tests/golden/questions/phase2_kpi.yaml'

    def test_kpi_questions_path_must_be_under_tests_golden_questions(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict()
        data['golden_set'] = _valid_golden_set_dict({'kpi_questions_path': 'invalid/path.yaml'})
        with pytest.raises(ValidationError, match='must be under tests/golden/questions/'):
            Config.model_validate(data)

    def test_kpi_questions_path_non_empty(self) -> None:
        data = _base_config_dict()
        data['kpi'] = _valid_kpi_dict()
        data['charts'] = _valid_charts_dict()
        data['dashboard'] = _valid_dashboard_dict()
        data['web'] = _valid_web_vercel_dict()
        data['golden_set'] = _valid_golden_set_dict({'kpi_questions_path': ''})
        with pytest.raises(ValidationError, match='String should have at least 1 character'):
            Config.model_validate(data)


class TestChartsConfigModelDirectly:
    """Direct tests of ChartsConfig model validation."""

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChartsConfig(unknown_field=True)  # type: ignore[call-arg]

    def test_misspelled_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChartsConfig(specs={}, export_formats=['png'], misspelled='value')  # type: ignore[call-arg]


class TestDashboardConfigModelDirectly:
    """Direct tests of DashboardConfig model validation."""

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DashboardConfig(unknown_field=True)  # type: ignore[call-arg]

    def test_misspelled_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DashboardConfig(
                auto_refresh_seconds=30,
                default_layout={},
                staleness_badge_enabled=True,
                misspelled='value',
            )  # type: ignore[call-arg]


class TestVercelConfigModelDirectly:
    """Direct tests of VercelConfig model validation."""

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VercelConfig(unknown_field=True)  # type: ignore[call-arg]

    def test_misspelled_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VercelConfig(
                sync_enabled=True,
                preview_api_target='mock',
                log_forwarding_enabled=True,
                misspelled='value',
            )  # type: ignore[call-arg]


class TestGoldenSetConfigModelDirectly:
    """Direct tests of GoldenSetConfig model validation."""

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GoldenSetConfig(unknown_field=True)  # type: ignore[call-arg]

    def test_misspelled_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GoldenSetConfig(
                kpi_questions_path='tests/golden/questions/phase2_kpi.yaml', misspelled='value'
            )  # type: ignore[call-arg]
