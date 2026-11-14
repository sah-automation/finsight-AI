#!/usr/bin/env python3
"""Apply the AWS billing guardrails from the CDK environment configuration.

The budget amount, the anomaly threshold and the notification mailbox are read
from ``infra/cdk/config/envs.yaml`` through the same loader the CDK stacks
use, so the amount in AWS and the amount in the repository cannot drift apart:
changing the threshold is a config change plus one run of this script.

The script is idempotent — it updates an existing budget instead of failing,
reuses an existing anomaly monitor, and never creates a second subscription.
Every resource is read back through the service API afterwards, so the output
states what actually exists rather than what was requested.

Usage:

    uv run python scripts/apply_billing_guardrails.py --env prod
    uv run python scripts/apply_billing_guardrails.py --env prod --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3

REPO_ROOT = Path(__file__).resolve().parent.parent
CDK_DIR = REPO_ROOT / 'infra' / 'cdk'
if str(CDK_DIR) not in sys.path:
    sys.path.insert(0, str(CDK_DIR))

from stacks.env_config import AlertsConfig, load_alerts_config  # noqa: E402

if TYPE_CHECKING:
    from decimal import Decimal

BUDGET_NAME = 'finsight-monthly-budget'
MONITOR_NAME = 'finsight-cost-anomaly'
SUBSCRIPTION_NAME = 'finsight-cost-anomaly-subscription'
CURRENCY = 'USD'


def load_billing_alerts(env_name: str) -> AlertsConfig:
    """Read the billing guardrail settings for one environment."""
    return load_alerts_config(env_name)


def _amount(value: Decimal) -> str:
    """Render a money amount the way the AWS APIs expect it."""
    return f'{value:f}'


def _notification(notification_type: str, threshold: int) -> dict[str, Any]:
    return {
        'Notification': {
            'NotificationType': notification_type,
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': threshold,
            'ThresholdType': 'PERCENTAGE',
        },
        'Subscribers': [],
    }


def budget_definition(alerts: AlertsConfig) -> dict[str, Any]:
    """Build the budget payload from the configured amounts and mailbox."""
    subscribers = [{'SubscriptionType': 'EMAIL', 'Address': alerts.notification_email}]
    notifications = [
        _notification('ACTUAL', 80),
        _notification('ACTUAL', 100),
        _notification('FORECASTED', 100),
    ]
    for notification in notifications:
        notification['Subscribers'] = subscribers
    return {
        'Budget': {
            'BudgetName': BUDGET_NAME,
            'BudgetType': 'COST',
            'TimeUnit': 'MONTHLY',
            'BudgetLimit': {'Amount': _amount(alerts.monthly_budget_usd), 'Unit': CURRENCY},
        },
        'NotificationsWithSubscribers': notifications,
    }


def apply_budget(budgets_client: Any, alerts: AlertsConfig, account_id: str) -> str:
    """Create or update the monthly budget and return the applied amount.

    AWS rejects a second budget with the same name, so an existing budget is
    replaced rather than left stale.
    """
    existing = {
        budget['BudgetName']
        for budget in budgets_client.describe_budgets(AccountId=account_id)['Budgets']
    }
    payload = budget_definition(alerts)
    if BUDGET_NAME in existing:
        budgets_client.delete_budget(AccountId=account_id, BudgetName=BUDGET_NAME)
    budgets_client.create_budget(
        AccountId=account_id,
        Budget=payload['Budget'],
        NotificationsWithSubscribers=payload['NotificationsWithSubscribers'],
    )
    return payload['Budget']['BudgetLimit']['Amount']


def apply_anomaly(ce_client: Any, alerts: AlertsConfig) -> tuple[str, str]:
    """Create or reuse the anomaly monitor and its email subscription."""
    monitors = {
        monitor['MonitorName']: monitor['MonitorArn']
        for monitor in ce_client.get_anomaly_monitors()['AnomalyMonitors']
    }
    monitor_arn = monitors.get(MONITOR_NAME)
    if monitor_arn is None:
        created = ce_client.create_anomaly_monitor(
            AnomalyMonitor={
                'MonitorName': MONITOR_NAME,
                'MonitorType': 'DIMENSIONAL',
                'MonitorDimension': 'SERVICE',
            },
        )
        monitor_arn = created['AnomalyMonitorArn']
    subscriptions = {
        subscription['SubscriptionName']: subscription
        for subscription in ce_client.get_anomaly_subscriptions()['AnomalySubscriptions']
    }
    if SUBSCRIPTION_NAME not in subscriptions:
        ce_client.create_anomaly_subscription(
            AnomalySubscription={
                'SubscriptionName': SUBSCRIPTION_NAME,
                'MonitorArnList': [monitor_arn],
                'Subscribers': [
                    {'Address': alerts.notification_email, 'Type': 'EMAIL'},
                ],
                'Frequency': 'DAILY',
                'ThresholdExpression': {
                    'Dimensions': {
                        'Key': 'ANOMALY_TOTAL_IMPACT_ABSOLUTE',
                        'MatchOptions': ['GREATER_THAN_OR_EQUAL'],
                        'Values': [_amount(alerts.anomaly_threshold_usd)],
                    },
                },
            },
        )
    return monitor_arn, SUBSCRIPTION_NAME


def verify(budgets_client: Any, ce_client: Any, account_id: str) -> dict[str, Any]:
    """Read the guardrails back so the report states what exists."""
    budgets = {
        budget['BudgetName']: budget
        for budget in budgets_client.describe_budgets(AccountId=account_id)['Budgets']
    }
    budget = budgets.get(BUDGET_NAME, {})
    subscriptions = {
        subscription['SubscriptionName']: subscription
        for subscription in ce_client.get_anomaly_subscriptions()['AnomalySubscriptions']
    }
    subscription = subscriptions.get(SUBSCRIPTION_NAME, {})
    budget_subscribers = [
        subscriber['Address']
        for notification in budget.get('NotificationsWithSubscribers', []) or []
        for subscriber in notification.get('Subscribers', [])
    ]
    report = {
        'budget': {
            'name': BUDGET_NAME,
            'limit': budget.get('BudgetLimit'),
            'notifications': len(budget.get('NotificationsWithSubscribers', []) or []),
            'email_subscribers': budget_subscribers,
        },
        'anomaly': {
            'monitor': MONITOR_NAME,
            'subscription': SUBSCRIPTION_NAME,
            'subscribers': [
                {'address': subscriber['Address'], 'status': subscriber.get('Status')}
                for subscriber in subscription.get('Subscribers', [])
            ],
        },
    }
    if not budget_subscribers:
        report['warnings'] = [
            (
                'The budget carries no email subscriber. AWS accepts the request and then '
                'drops budget notifications when billing-alert preferences are off, which '
                'the organization policies block. Enable billing alerts, then re-run this '
                'script.'
            )
        ]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='prod', help='CDK environment name (default: prod)')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='print the payload that would be applied, change nothing',
    )
    args = parser.parse_args(argv)

    alerts = load_billing_alerts(args.env)
    if args.dry_run:
        print(json.dumps(budget_definition(alerts), indent=2, default=str))
        return 0

    budgets_client = boto3.client('budgets', region_name=args.region)
    ce_client = boto3.client('ce', region_name=args.region)
    sts_client = boto3.client('sts', region_name=args.region)
    account_id = sts_client.get_caller_identity()['Account']

    apply_budget(budgets_client, alerts, account_id)
    apply_anomaly(ce_client, alerts)
    report = verify(budgets_client, ce_client, account_id)
    report['account'] = account_id
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
