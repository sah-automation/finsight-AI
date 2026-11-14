"""Tests for ingestion pipeline step worker helpers."""

from __future__ import annotations

import pytest

from finsight.application.ingest_document import pipeline_step_worker as m
from finsight.core.types import CompanyId


class TestAwaitv:
    @pytest.mark.asyncio
    async def test_returns_awaitable_result(self) -> None:
        async def f() -> int:
            return 7

        assert await m._awaitv(f()) == 7

    @pytest.mark.asyncio
    async def test_returns_plain_value(self) -> None:
        assert await m._awaitv(42) == 42


class TestGet:
    def test_gets_first_present_named(self) -> None:
        obj = {'a': 1, 'b': 2}
        assert m._get(obj, 'b', 'a') == 2

    def test_skips_none_values(self) -> None:
        obj = {'a': None, 'b': 2}
        assert m._get(obj, 'a', 'b') == 2

    def test_object_attribute(self) -> None:
        class _O:
            x = 5

        assert m._get(_O(), 'x') == 5

    def test_returns_default(self) -> None:
        assert m._get({}, 'x', default='d') == 'd'

    def test_nested_none_object_attr_skipped(self) -> None:
        class _O:
            x = None
            y = 7

        assert m._get(_O(), 'x', 'y') == 7


class TestFirst:
    def test_first_key(self) -> None:
        assert m._first({'a': 1, 'b': 2}, 'a', 'b') == 1

    def test_skips_none(self) -> None:
        assert m._first({'a': None, 'b': 2}, 'a', 'b') == 2

    def test_object_first(self) -> None:
        class _O:
            a = None
            b = 3

        assert m._first(_O(), 'a', 'b') == 3

    def test_default(self) -> None:
        assert m._first({}, 'a', default='x') == 'x'


class TestCoerceCompany:
    def test_none(self) -> None:
        assert m._coerce_company(None) is None

    def test_empty(self) -> None:
        assert m._coerce_company('   ') is None

    def test_coerces_valid(self) -> None:
        assert m._coerce_company('company-a') == CompanyId('company-a')

    def test_non_company_value(self) -> None:
        # unlikely to fail; if CompanyId rejects weird, value returned
        out = m._coerce_company(object())
        assert out is not None


class TestNormalizeKey:
    def test_normalizes_backslashes(self) -> None:
        assert m._normalize_key('a\\b/c') == 'a/b/c'

    def test_strips_leading_slash(self) -> None:
        assert m._normalize_key('/a/b') == 'a/b'

    def test_none(self) -> None:
        assert m._normalize_key(None) == ''


class TestParseKey:
    def test_empty(self) -> None:
        assert m._parse_key(None)['company_id'] is None

    def test_company_only(self) -> None:
        r = m._parse_key('company-a')
        assert r['company_id'] == 'company-a'
        assert r['document_id'] is None

    def test_full_path(self) -> None:
        r = m._parse_key('company-a/documents/doc-1/versions/v-1')
        assert r == {
            'company_id': 'company-a',
            'document_id': 'doc-1',
            'version_id': 'v-1',
        }

    def test_backslash_normalization(self) -> None:
        r = m._parse_key('company-a\\documents\\doc-1\\versions\\v-1')
        assert r['document_id'] == 'doc-1'


class TestConfigDeltaTracking:
    def test_explicit_kwarg_true(self) -> None:
        assert m._config_delta_tracking(None, {'delta_tracking': True}) is True

    def test_explicit_kwarg_false(self) -> None:
        assert m._config_delta_tracking(None, {'delta': False}) is False

    def test_explicit_track_delta(self) -> None:
        assert m._config_delta_tracking(None, {'track_delta': 0}) is False

    def test_object_attribute(self) -> None:
        class C:
            delta_tracking = True

        assert m._config_delta_tracking(C(), {}) is True

    def test_nested_documents_attr(self) -> None:
        class D:
            delta = False

        class C:
            documents = D()

        assert m._config_delta_tracking(C(), {}) is False

    def test_nested_documents_dict(self) -> None:
        c = {'documents': {'delta_tracking': True}}
        assert m._config_delta_tracking(c, {}) is True

    def test_top_level_dict(self) -> None:
        assert m._config_delta_tracking({'delta_tracking': False}, {}) is False

    def test_ingestion_attr(self) -> None:
        class _I:
            delta_tracking = True

        class C:
            ingestion = _I()

        assert m._config_delta_tracking(C(), {}) is True

    def test_default_true(self) -> None:
        assert m._config_delta_tracking(object(), {}) is True

    def test_invalid_values_fall_through(self) -> None:
        # bool conversion exceptions ignored
        class Weird:
            delta_tracking = ()

        # bool([]) is False, no exception
        assert m._config_delta_tracking(Weird(), {}) is False


class TestConfigAnswerCache:
    def test_returns_true(self) -> None:
        assert m._config_answer_cache(None) is True


class TestVersionState:
    def test_none(self) -> None:
        w = m.PipelineStepWorker()
        assert w._version_state(None) == ''

    def test_string_status(self) -> None:
        class V:
            status = 'committed'

        w = m.PipelineStepWorker()
        assert w._version_state(V()) == 'committed'

    def test_dict_status(self) -> None:
        w = m.PipelineStepWorker()
        assert w._version_state({'status': 'draft'}) == 'draft'

    def test_state_attr(self) -> None:
        class V:
            state = 'X'

        w = m.PipelineStepWorker()
        assert w._version_state(V()) == 'x'
