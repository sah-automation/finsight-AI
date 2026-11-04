from __future__ import annotations

import asyncio

from finsight.application.source_viewer import StepResult
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.resolve_citation_step import ResolveCitationStep
from finsight.core.security.citation_locator import mint_citation_locator

SECRET = 'secret-key-1234567890-abcdefghijklmnopqrstuvwxyz'  # pragma: allowlist secret


def _step(signing_key: str = SECRET) -> ResolveCitationStep:
    return ResolveCitationStep(signing_key=signing_key)


def test_missing_signing_key_raises() -> None:
    try:
        ResolveCitationStep(signing_key='')
    except ValueError:
        return
    raise AssertionError('expected ValueError')


def test_valid_signed_locator_writes_claims() -> None:
    token = mint_citation_locator(
        SECRET, document_id='doc-1', document_version='v-1', chunk_id='chunk-1', page=3
    )
    step = _step()
    ctx = SourceViewerContext(citation_input=token)
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.document_id == 'doc-1'
    assert ctx.version_id == 'v-1'
    assert ctx.chunk_id == 'chunk-1'
    assert ctx.page == 3


def test_tampered_signature_stops() -> None:
    token = mint_citation_locator(SECRET, document_id='doc-1', document_version='v-1')
    step = _step()
    ctx = SourceViewerContext(citation_input=token[:-4] + 'abcd')
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'not_available'


def test_wrong_key_stops() -> None:
    token = mint_citation_locator(SECRET, document_id='doc-1', document_version='v-1')
    step = _step(signing_key='other-key-abcdefghijklmnopqrstuvwxyz1234')
    ctx = SourceViewerContext(citation_input=token)
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'not_available'


def test_absent_citation_continues() -> None:
    step = _step()
    ctx = SourceViewerContext(citation_input=None, document_id='doc-explicit')
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.document_id == 'doc-explicit'


def test_plain_non_locator_string_continues() -> None:
    step = _step()
    ctx = SourceViewerContext(citation_input='some citation metadata')
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'


def test_citation_object_supplies_fields() -> None:
    step = _step()
    ctx = SourceViewerContext(
        citation_input={
            'document_id': 'obj-doc',
            'document_version': 'obj-ver',
            'chunk_id': 'obj-chunk',
            'page': 7,
            'category': 'obj-cat',
        }
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.document_id == 'obj-doc'
    assert ctx.version_id == 'obj-ver'
    assert ctx.chunk_id == 'obj-chunk'
    assert ctx.page == 7
    assert ctx.category == 'obj-cat'


def test_explicit_fields_win_over_claims() -> None:
    token = mint_citation_locator(
        SECRET, document_id='loc-doc', document_version='loc-ver', chunk_id='loc-chunk', page=9
    )
    step = _step()
    ctx = SourceViewerContext(
        citation_input=token,
        document_id='explicit-doc',
        version_id='explicit-ver',
        chunk_id='explicit-chunk',
        page=99,
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.document_id == 'explicit-doc'
    assert ctx.version_id == 'explicit-ver'
    assert ctx.chunk_id == 'explicit-chunk'
    assert ctx.page == 99


def test_result_type() -> None:
    step = _step()
    ctx = SourceViewerContext(citation_input=None)
    result = asyncio.run(step.run(ctx))
    assert isinstance(result, StepResult)
