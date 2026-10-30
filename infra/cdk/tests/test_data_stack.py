"""Synthesis tests for the data stack (issue #104).

The stack is deploy-neutral: these tests inspect the synthesized CloudFormation
template only. They never create AWS resources.
"""

from __future__ import annotations

import copy

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.data import DataStack, _load_env_config
from stacks.network import NetworkStack

TABLE_NAMES = {
    'answer-cache',
    'role-cache',
    'metering',
    'job-progress',
    'sessions',
    'chat-history',
}


def _data_template(env_name: str) -> Template:
    app = cdk.App()
    network = NetworkStack(app, f'FinSight-{env_name}-Network', env_name=env_name)
    data = DataStack(app, f'FinSight-{env_name}-Data', env_name=env_name, vpc=network.vpc)
    return Template.from_stack(data)


def _tables(template: Template) -> dict[str, dict[str, object]]:
    resources = template.find_resources('AWS::DynamoDB::Table')
    return {resource['Properties']['TableName']: resource for resource in resources.values()}


def test_every_required_table_is_defined() -> None:
    tables = _tables(_data_template('dev'))

    assert set(tables) == {f'finsight-dev-{name}' for name in TABLE_NAMES}


def test_tables_are_pay_per_request_and_encrypted() -> None:
    for table in _tables(_data_template('dev')).values():
        properties = table['Properties']
        assert properties['BillingMode'] == 'PAY_PER_REQUEST'
        assert properties['SSESpecification'] == {'SSEEnabled': True}


def test_job_progress_rows_are_keyed_by_job_id() -> None:
    table = _tables(_data_template('dev'))['finsight-dev-job-progress']
    key_schema = table['Properties']['KeySchema']

    assert {'AttributeName': 'job_id', 'KeyType': 'HASH'} in key_schema
    assert {'AttributeName': 'company_id', 'KeyType': 'RANGE'} in key_schema


def test_production_tables_are_retained_with_point_in_time_recovery() -> None:
    for table in _tables(_data_template('prod')).values():
        assert table['DeletionPolicy'] == 'Retain'
        recovery = table['Properties']['PointInTimeRecoverySpecification']
        assert recovery == {'PointInTimeRecoveryEnabled': True}


def test_non_production_tables_are_destroyed_without_point_in_time_recovery() -> None:
    for table in _tables(_data_template('dev')).values():
        assert table['DeletionPolicy'] == 'Delete'
        recovery = table['Properties'].get('PointInTimeRecoverySpecification', {})
        assert recovery.get('PointInTimeRecoveryEnabled') is not True


def test_aurora_cluster_is_the_source_of_truth_and_encrypted() -> None:
    for env_name in ('dev', 'prod'):
        template = _data_template(env_name)
        clusters = template.find_resources('AWS::RDS::DBCluster')
        assert len(clusters) == 1
        cluster = next(iter(clusters.values()))
        properties = cluster['Properties']

        assert properties['StorageEncrypted'] is True
        assert properties.get('DeletionProtection') is (env_name == 'prod')
        assert cluster['DeletionPolicy'] == ('Retain' if env_name == 'prod' else 'Delete')


def test_aurora_backup_retention_comes_from_environment_config() -> None:
    expected = {'dev': 1, 'prod': 35}
    for env_name, days in expected.items():
        template = _data_template(env_name)
        cluster = next(iter(template.find_resources('AWS::RDS::DBCluster').values()))
        assert cluster['Properties']['BackupRetentionPeriod'] == days


def test_cache_tables_have_ttl_and_tenant_sort_keys() -> None:
    tables = _tables(_data_template('dev'))

    for name in ('answer-cache', 'role-cache'):
        table = tables[f'finsight-dev-{name}']
        assert table['Properties']['TimeToLiveSpecification'] == {
            'AttributeName': 'ttl',
            'Enabled': True,
        }
        assert {'AttributeName': 'sk', 'KeyType': 'RANGE'} in table['Properties']['KeySchema']
        assert {'AttributeName': 'pk', 'KeyType': 'HASH'} in table['Properties']['KeySchema']

    metering = tables['finsight-dev-metering']
    assert {'AttributeName': 'sk', 'KeyType': 'RANGE'} in metering['Properties']['KeySchema']


def test_customer_managed_key_mode_uses_one_kms_key_for_data() -> None:
    env_config = copy.deepcopy(_load_env_config('dev'))
    env_config['key_mode'] = 'kms_customer'

    app = cdk.App()
    network = NetworkStack(app, 'FinSight-dev-Network', env_name='dev')
    data = DataStack(
        app,
        'FinSight-dev-Data',
        env_name='dev',
        vpc=network.vpc,
        env_config=env_config,
    )
    template = Template.from_stack(data)

    assert len(template.find_resources('AWS::KMS::Key')) == 1
    for table in _tables(template).values():
        specification = table['Properties']['SSESpecification']
        assert specification['SSEEnabled'] is True
        assert specification['SSEType'] == 'KMS'
        assert 'KMSMasterKeyId' in specification

    cluster = next(iter(template.find_resources('AWS::RDS::DBCluster').values()))
    assert cluster['Properties']['StorageEncrypted'] is True
    assert 'KmsKeyId' in cluster['Properties']
