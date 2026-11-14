"""Tests for the billing-guardrail apply script.

The script reads the CDK environment configuration through the same loader the
stacks use, so the budget amount in AWS and the amount in
``infra/cdk/config/envs.yaml`` cannot drift apart. These tests use fake AWS
clients and assert on the requests the script makes, never on AWS itself.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'apply_billing_guardrails.py'
ACCOUNT = '069632763967'


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location('apply_billing_guardrails', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


apply_billing_guardrails = _load_script()


class FakeBudgets:
    """Minimal stand-in for the AWS Budgets client."""

    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.created: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    def describe_budgets(self, AccountId: str) -> dict[str, Any]:  # noqa: N803 - AWS casing
        return {'Budgets': self.existing}

    def create_budget(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        self.existing.append(kwargs['Budget'])
        return {}

    def delete_budget(self, **kwargs: Any) -> dict[str, Any]:
        self.deleted.append(kwargs['BudgetName'])
        self.existing = [b for b in self.existing if b['BudgetName'] != kwargs['BudgetName']]
        return {}


class FakeCostExplorer:
    """Minimal stand-in for the AWS Cost Explorer client."""

    def __init__(
        self,
        monitors: list[dict[str, Any]] | None = None,
        subscriptions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.monitors = monitors or []
        self.subscriptions = subscriptions or []
        self.created_monitors: list[dict[str, Any]] = []
        self.created_subscriptions: list[dict[str, Any]] = []

    def get_anomaly_monitors(self) -> dict[str, Any]:
        return {'AnomalyMonitors': self.monitors}

    def get_anomaly_subscriptions(self) -> dict[str, Any]:
        return {'AnomalySubscriptions': self.subscriptions}

    def create_anomaly_monitor(self, AnomalyMonitor: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        self.created_monitors.append(AnomalyMonitor)
        arn = f'arn:aws:ce::069632763967:anomalymonitor/{AnomalyMonitor["MonitorName"]}'
        self.monitors.append({'MonitorName': AnomalyMonitor['MonitorName'], 'MonitorArn': arn})
        return {'AnomalyMonitorArn': arn}

    def create_anomaly_subscription(self, AnomalySubscription: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        self.created_subscriptions.append(AnomalySubscription)
        arn = f'arn:aws:ce::069632763967:anomalysubscription/{AnomalySubscription["SubscriptionName"]}'
        self.subscriptions.append(
            {
                'SubscriptionName': AnomalySubscription['SubscriptionName'],
                'SubscriptionArn': arn,
                'MonitorArnList': AnomalySubscription['MonitorArnList'],
            }
        )
        return {'SubscriptionArn': arn}


@pytest.fixture
def alerts() -> Any:
    return apply_billing_guardrails.AlertsConfig(
        monthly_budget_usd=Decimal('5'),
        anomaly_threshold_usd=Decimal('5'),
        notification_email='alerts@example.com',
    )


def test_budget_is_built_from_the_configured_amount(alerts) -> None:
    budgets = FakeBudgets()

    apply_billing_guardrails.apply_budget(budgets, alerts, ACCOUNT)

    assert len(budgets.created) == 1
    created = budgets.created[0]
    assert created['Budget']['BudgetName'] == apply_billing_guardrails.BUDGET_NAME
    assert created['Budget']['BudgetLimit'] == {'Amount': '5', 'Unit': 'USD'}
    assert created['Budget']['TimeUnit'] == 'MONTHLY'


def test_budget_carries_email_subscribers_for_actual_and_forecast(alerts) -> None:
    budgets = FakeBudgets()

    apply_billing_guardrails.apply_budget(budgets, alerts, ACCOUNT)

    subscribers = budgets.created[0]['NotificationsWithSubscribers']
    assert {s['Notification']['NotificationType'] for s in subscribers} == {'ACTUAL', 'FORECASTED'}
    for subscriber in subscribers:
        assert subscriber['Subscribers'] == [
            {'SubscriptionType': 'EMAIL', 'Address': 'alerts@example.com'}
        ]


def test_budget_amount_is_not_hard_coded(alerts) -> None:
    bigger = apply_billing_guardrails.AlertsConfig(
        monthly_budget_usd=Decimal('42.50'),
        anomaly_threshold_usd=Decimal('5'),
        notification_email='alerts@example.com',
    )
    budgets = FakeBudgets()

    apply_billing_guardrails.apply_budget(budgets, bigger, ACCOUNT)

    assert budgets.created[0]['Budget']['BudgetLimit'] == {'Amount': '42.50', 'Unit': 'USD'}


def test_existing_budget_is_re_applied_not_duplicated(alerts) -> None:
    budgets = FakeBudgets(
        existing=[
            {'BudgetName': apply_billing_guardrails.BUDGET_NAME, 'BudgetLimit': {'Amount': '5'}}
        ]
    )

    apply_billing_guardrails.apply_budget(budgets, alerts, ACCOUNT)

    assert budgets.deleted == [apply_billing_guardrails.BUDGET_NAME]
    assert len(budgets.created) == 1
    assert budgets.created[0]['Budget']['BudgetLimit'] == {'Amount': '5', 'Unit': 'USD'}
    assert [b['BudgetName'] for b in budgets.existing] == [apply_billing_guardrails.BUDGET_NAME]


def test_anomaly_monitor_is_reused_when_it_already_exists(alerts) -> None:
    ce = FakeCostExplorer(
        monitors=[
            {
                'MonitorName': apply_billing_guardrails.MONITOR_NAME,
                'MonitorArn': 'arn:aws:ce::069632763967:anomalymonitor/existing',
            }
        ],
    )

    apply_billing_guardrails.apply_anomaly(ce, alerts)

    assert ce.created_monitors == []
    assert ce.created_subscriptions[0]['MonitorArnList'] == [
        'arn:aws:ce::069632763967:anomalymonitor/existing'
    ]


def test_anomaly_subscription_uses_the_configured_threshold(alerts) -> None:
    ce = FakeCostExplorer()

    apply_billing_guardrails.apply_anomaly(ce, alerts)

    subscription = ce.created_subscriptions[0]
    assert subscription['Subscribers'] == [{'Address': 'alerts@example.com', 'Type': 'EMAIL'}]
    dimensions = subscription['ThresholdExpression']['Dimensions']
    assert dimensions['Key'] == 'ANOMALY_TOTAL_IMPACT_ABSOLUTE'
    assert dimensions['Values'] == ['5']


def test_existing_subscription_is_not_duplicated(alerts) -> None:
    ce = FakeCostExplorer(
        monitors=[
            {
                'MonitorName': apply_billing_guardrails.MONITOR_NAME,
                'MonitorArn': 'arn:aws:ce::069632763967:anomalymonitor/existing',
            }
        ],
        subscriptions=[
            {
                'SubscriptionName': apply_billing_guardrails.SUBSCRIPTION_NAME,
                'SubscriptionArn': 'arn:aws:ce::069632763967:anomalysubscription/existing',
                'MonitorArnList': ['arn:aws:ce::069632763967:anomalymonitor/existing'],
            }
        ],
    )

    apply_billing_guardrails.apply_anomaly(ce, alerts)

    assert ce.created_subscriptions == []


def test_config_loader_is_the_single_reader_of_the_budget_amount() -> None:
    alerts = apply_billing_guardrails.load_billing_alerts('prod')

    assert alerts.monthly_budget_usd == Decimal('5')
    assert alerts.anomaly_threshold_usd == Decimal('5')
    assert '@' in alerts.notification_email


def test_verify_warns_when_the_budget_carries_no_email_subscriber() -> None:
    budgets = FakeBudgets(existing=[{'BudgetName': apply_billing_guardrails.BUDGET_NAME}])
    ce = FakeCostExplorer()

    report = apply_billing_guardrails.verify(budgets, ce, ACCOUNT)

    assert report['budget']['email_subscribers'] == []
    assert report['warnings']


def test_verify_reports_the_anomaly_subscriber_status() -> None:
    budgets = FakeBudgets(
        existing=[
            {
                'BudgetName': apply_billing_guardrails.BUDGET_NAME,
                'BudgetLimit': {'Amount': '5.0', 'Unit': 'USD'},
                'NotificationsWithSubscribers': [
                    {
                        'Notification': {'NotificationType': 'ACTUAL'},
                        'Subscribers': [
                            {'SubscriptionType': 'EMAIL', 'Address': 'alerts@example.com'}
                        ],
                    }
                ],
            }
        ]
    )
    ce = FakeCostExplorer(
        subscriptions=[
            {
                'SubscriptionName': apply_billing_guardrails.SUBSCRIPTION_NAME,
                'Subscribers': [{'Address': 'alerts@example.com', 'Status': 'CONFIRMED'}],
            }
        ],
    )

    report = apply_billing_guardrails.verify(budgets, ce, ACCOUNT)

    assert report['budget']['email_subscribers'] == ['alerts@example.com']
    assert report['anomaly']['subscribers'] == [
        {'address': 'alerts@example.com', 'status': 'CONFIRMED'}
    ]
    assert 'warnings' not in report
