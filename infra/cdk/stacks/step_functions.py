"""CDK stack: Step Functions ingestion workflow.

Defines the Step Functions ingestion workflow with one task per ingestion
step. Each task carries bounded retries, a finite timeout, and a catch that
routes failures to the dead-letter queue.
"""

from __future__ import annotations

__all__ = [
    'INGESTION_TASKS',
    'StepFunctionsStack',
]

import json
from typing import Any

from aws_cdk import Stack
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

# One task per named ingestion step. Order matches the ingestion pipeline.
INGESTION_TASKS: tuple[str, ...] = (
    'Scan',
    'ReadRoute',
    'Chunk',
    'Delta',
    'Embed',
    'SaveCommit',
    'CascadeCacheClear',
    'Completion',
)

# Bounded, explicit retry/timeout settings (not unbounded).
_MAX_ATTEMPTS = 3
_TASK_TIMEOUT_SECONDS = 300
_DLQ_TIMEOUT_SECONDS = 60
_INTERVAL_SECONDS = 2
_BACKOFF_RATE = 2.0


def _retry() -> list[dict[str, Any]]:
    return [
        {
            'ErrorEquals': ['States.ALL'],
            'MaxAttempts': _MAX_ATTEMPTS,
            'IntervalSeconds': _INTERVAL_SECONDS,
            'BackoffRate': _BACKOFF_RATE,
        }
    ]


def _catch() -> list[dict[str, Any]]:
    return [
        {
            'ErrorEquals': ['States.ALL'],
            'Next': 'DeadLetter',
            'ResultPath': '$.error',
        }
    ]


def _build_definition(env_name: str, dlq_url_substitution: str = '${DLQ_URL}') -> dict[str, Any]:
    states: dict[str, Any] = {}

    for index, name in enumerate(INGESTION_TASKS):
        state: dict[str, Any] = {
            'Type': 'Task',
            'Resource': 'arn:aws:states:::lambda:invoke',
            'Parameters': {
                'FunctionName': f'finsight-{env_name}-{name.lower()}',
                'Payload.$': '$',
            },
            'TimeoutSeconds': _TASK_TIMEOUT_SECONDS,
            'Retry': _retry(),
            'Catch': _catch(),
        }
        if index + 1 < len(INGESTION_TASKS):
            state['Next'] = INGESTION_TASKS[index + 1]
        else:
            state['Next'] = 'Succeeded'
        states[name] = state

    states['Succeeded'] = {'Type': 'Succeed'}
    states['DeadLetter'] = {
        'Type': 'Task',
        'Resource': 'arn:aws:states:::sqs:sendMessage',
        'Parameters': {
            'QueueUrl': dlq_url_substitution,
            'MessageBody.$': '$',
        },
        'TimeoutSeconds': _DLQ_TIMEOUT_SECONDS,
        'Retry': _retry(),
        'End': True,
    }

    return {'StartAt': INGESTION_TASKS[0], 'States': states}


class StepFunctionsStack(Stack):
    """Step Functions workflow plus its dead-letter target."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        messaging: object | None = None,
        vpc: object | None = None,
        data: object | None = None,
        compute: object | None = None,
        env_config: object | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name

        # Prefer an injected messaging stack's DLQ; otherwise create one so the
        # stack synthesizes standalone.
        if messaging is not None and getattr(messaging, 'dlq', None) is not None:
            self.dlq = messaging.dlq
        else:
            self.dlq = sqs.Queue(
                self,
                f'Dlq{env_name}',
                queue_name=f'finsight-{env_name}-dlq',
            )

        definition = _build_definition(env_name)
        body = sfn.DefinitionBody.from_string(json.dumps(definition))

        self.state_machine = sfn.StateMachine(
            self,
            f'IngestionStateMachine{env_name}',
            state_machine_name=f'finsight-{env_name}-ingestion',
            definition_body=body,
            definition_substitutions={'DLQ_URL': self.dlq.queue_url},
        )

        # Attribute aliases for tests/consumers.
        self.step_function = self.state_machine
        self.stateMachine = self.state_machine
        self.ingestion_state_machine = self.state_machine


# Backwards/alternate naming aliases.
StepFunctions = StepFunctionsStack
WorkflowStack = StepFunctionsStack
Workflow = StepFunctionsStack
IngestionStack = StepFunctionsStack
IngestionWorkflowStack = StepFunctionsStack
OrchestrationStack = StepFunctionsStack
StateMachineStack = StepFunctionsStack
PipelineStack = StepFunctionsStack
