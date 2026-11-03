"""Behavioral tests for source-viewer orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.source_viewer import SourceViewer
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.step_result import StepResult


class _OkStep:
    async def run(self, context: Any) -> StepResult:
        return StepResult.continue_(context)


class _StopStep:
    async def run(self, context: Any) -> StepResult:
        return StepResult.stop_with_not_available(context)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def step(self, label: str, stop: bool = False) -> Any:
        outer = self

        class _Step:
            async def run(self, context: Any) -> StepResult:
                outer.calls.append(label)
                if stop:
                    return StepResult.stop_with_not_available(context)
                return StepResult.continue_(context)

        return _Step()


def test_source_viewer_sequence_runs_all_steps() -> None:
    recorder = _Recorder()
    steps = [recorder.step(f's{i}') for i in range(5)]
    audit = recorder.step('audit')

    viewer = SourceViewer(
        authorize_step=steps[0],
        resolve_citation_step=steps[1],
        resolve_version_step=steps[2],
        fetch_content_step=steps[3],
        fetch_original_step=steps[4],
        audit_step=audit,
    )

    ctx = SourceViewerContext(company_id='co1')
    result = asyncio.run(viewer.run(ctx))
    assert result.status == 'available'
    assert recorder.calls == ['s0', 's1', 's2', 's3', 's4', 'audit']


def test_source_viewer_short_circuits() -> None:
    recorder = _Recorder()
    s0 = recorder.step('s0', stop=True)
    s1 = recorder.step('s1')
    audit = recorder.step('audit')

    viewer = SourceViewer(
        authorize_step=s0,
        resolve_citation_step=s1,
        resolve_version_step=_OkStep(),
        fetch_content_step=_OkStep(),
        fetch_original_step=_OkStep(),
        audit_step=audit,
    )

    ctx = SourceViewerContext(company_id='co1')
    result = asyncio.run(viewer.run(ctx))
    assert result.status == 'not_available'
    assert recorder.calls == ['s0', 'audit']
