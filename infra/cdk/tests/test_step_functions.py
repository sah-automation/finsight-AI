"""Synthesis tests for the Step Functions ingestion workflow (issue #106)."""

from __future__ import annotations

import json

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.step_functions import INGESTION_TASKS, StepFunctionsStack


def _template(env_name: str) -> Template:
    app = cdk.App()
    stack = StepFunctionsStack(app, f'FinSight-{env_name}-StepFunctions', env_name=env_name)
    return Template.from_stack(stack)


def _state_machine(env_name: str) -> dict[str, object]:
    resources = _template(env_name).find_resources('AWS::StepFunctions::StateMachine')
    assert len(resources) == 1
    return next(iter(resources.values()))


def test_state_machine_synthesizes() -> None:
    resource = _state_machine('dev')
    assert resource['Properties']['StateMachineName'] == 'finsight-dev-ingestion'


def test_every_ingestion_step_is_a_task() -> None:
    resource = _state_machine('dev')
    definition = json.loads(resource['Properties']['DefinitionString'])
    states = definition['States']

    tasks = {name: states[name] for name in INGESTION_TASKS}
    assert set(tasks) == set(INGESTION_TASKS)
    for state in tasks.values():
        assert state['Type'] == 'Task'


def test_each_task_has_bounded_retry_and_finite_timeout() -> None:
    resource = _state_machine('dev')
    definition = json.loads(resource['Properties']['DefinitionString'])
    states = definition['States']

    for name in INGESTION_TASKS:
        state = states[name]
        assert isinstance(state['TimeoutSeconds'], int)
        assert state['TimeoutSeconds'] > 0
        assert state['Retry'], f'{name} is missing retries'
        retry = state['Retry'][0]
        assert retry['MaxAttempts'] > 0
        max_retry_bound = 100
        assert retry['MaxAttempts'] < max_retry_bound


def test_each_task_catches_to_dead_letter_queue() -> None:
    resource = _state_machine('dev')
    definition = json.loads(resource['Properties']['DefinitionString'])
    states = definition['States']

    for name in INGESTION_TASKS:
        state = states[name]
        assert state['Catch'], f'{name} is missing DLQ catch'
        assert any(catch.get('Next') == 'DeadLetter' for catch in state['Catch'])

    dead_letter = states['DeadLetter']
    assert dead_letter['Type'] == 'Task'
    assert dead_letter['Resource'] == 'arn:aws:states:::sqs:sendMessage'


def test_dead_letter_target_synthesizes_with_queue() -> None:
    templates = {env: _template(env) for env in ('dev', 'prod')}
    for env_name, template in templates.items():
        queues = template.find_resources('AWS::SQS::Queue')
        assert queues, f'{env_name} is missing its DLQ target'
