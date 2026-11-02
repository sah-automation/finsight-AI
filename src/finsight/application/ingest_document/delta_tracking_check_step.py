"""Deep module: Delta-tracking check step for the ingestion pipeline."""

from __future__ import annotations

from typing import Any

from .pipeline_step_worker import (
    PipelineStepWorker,
)
from .step_context import (  # noqa: F401
    Context,
    IngestionContext,
    IngestionStepContext,
    PipelineContext,
    PipelineStepContext,
    StepContext,
)

__all__ = [
    'Context',
    'DeepDeltaTrackingCheck',
    'DeepDeltaTrackingCheckStep',
    'DeltaTrackingCheck',
    'DeltaTrackingCheckDeep',
    'DeltaTrackingCheckModule',
    'DeltaTrackingCheckStep',
    'DeltaTrackingCheckStepDeep',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineContext',
    'PipelineDeltaTrackingCheckStep',
    'PipelineStepContext',
    'StepContext',
]

aliases = [
    'DeltaTrackingCheck',
    'DeltaTrackingCheckDeep',
    'DeltaTrackingCheckModule',
    'DeltaTrackingCheckStep',
    'DeltaTrackingCheckStepDeep',
    'DeepDeltaTrackingCheck',
    'DeepDeltaTrackingCheckStep',
    'PipelineDeltaTrackingCheckStep',
]


class DeltaTrackingCheckStep(PipelineStepWorker):
    """Return the configured delta-tracking status without touching data."""

    step_name = 'delta_tracking_check'

    def __init__(
        self,
        *,
        config: Any = None,
        settings: Any = None,
        configuration: Any = None,
        app_config: Any = None,
        delta_tracking: Any = None,
        container: Any = None,
        composition: Any = None,
        root: Any = None,
        app: Any = None,
        context: Any = None,
    ) -> None:
        def _pick(mapping: dict[str, Any]) -> Any:
            for value in mapping.values():
                if value is not None:
                    return value
            return None

        cfg = _pick(
            {
                'config': config,
                'settings': settings,
                'configuration': configuration,
                'app_config': app_config,
            }
        )

        container_obj = None
        for candidate in (container, composition, root, app, context):
            if candidate is not None and not isinstance(candidate, (str, bytes, dict)):
                container_obj = candidate
                break

        if container_obj is not None and cfg is None:
            cfg = getattr(container_obj, 'config', cfg)

        super().__init__(
            config=cfg,
            step_name='delta_tracking_check',
            **({'delta_tracking': delta_tracking} if delta_tracking is not None else {}),
        )

    async def run(self, context: Any) -> Any:
        ctx = context
        try:
            ctx.delta_tracking = self.delta_tracking
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['delta_tracking'] = self.delta_tracking
        try:
            ctx.status = 'ok'
        except Exception:  # noqa: BLE001
            if isinstance(ctx, dict):
                ctx['status'] = 'ok'
        return ctx

    def __call__(self, context: Any) -> Any:
        return self.run(context)


DeltaTrackingCheck = DeltaTrackingCheckStep
DeltaTrackingCheckDeep = DeltaTrackingCheckStep
DeltaTrackingCheckModule = DeltaTrackingCheckStep
DeltaTrackingCheckStepDeep = DeltaTrackingCheckStep
DeepDeltaTrackingCheck = DeltaTrackingCheckStep
DeepDeltaTrackingCheckStep = DeltaTrackingCheckStep
PipelineDeltaTrackingCheckStep = DeltaTrackingCheckStep
