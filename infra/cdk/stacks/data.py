from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import Construct

_REMOVAL_POLICIES = {
    'retain': RemovalPolicy.RETAIN,
    'destroy': RemovalPolicy.DESTROY,
}
_ENVS_FILE = Path(__file__).resolve().parent.parent / 'config' / 'envs.yaml'


def _load_env_config(env_name: str) -> dict[str, Any]:
    """Load one environment's data settings from config/envs.yaml."""
    loaded = yaml.safe_load(_ENVS_FILE.read_text(encoding='utf-8')) or {}
    if not isinstance(loaded, dict) or env_name not in loaded:
        raise ValueError(f'Unknown environment {env_name!r}; expected one of {sorted(loaded)}')
    config = loaded[env_name]
    if not isinstance(config, dict):
        raise TypeError(f'Environment {env_name!r} must be a mapping')
    return config


def _required(config: dict[str, Any], key: str) -> object:
    if key not in config or config[key] is None:
        raise ValueError(f'Missing required data setting: {key!r}')
    return config[key]


def _required_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = _required(config, key)
    if not isinstance(value, dict):
        raise TypeError(f'Data setting {key!r} must be a mapping')
    return value


def _removal_policy(config: dict[str, Any]) -> RemovalPolicy:
    name = str(_required(config, 'removal_policy')).lower()
    try:
        return _REMOVAL_POLICIES[name]
    except KeyError as exc:
        raise ValueError(
            f'Unknown removal_policy {name!r}; expected one of {sorted(_REMOVAL_POLICIES)}'
        ) from exc


def _encryption(
    scope: Construct, env_name: str, key_mode: str, removal_policy: RemovalPolicy
) -> tuple[dynamodb.TableEncryption, s3.BucketEncryption, kms.IKey | None]:
    """Return the table, bucket and Aurora key settings for one key mode."""
    if key_mode == 'aws_managed':
        return (
            dynamodb.TableEncryption.AWS_MANAGED,
            s3.BucketEncryption.S3_MANAGED,
            None,
        )
    if key_mode == 'kms_customer':
        key = kms.Key(
            scope,
            f'DataKey{env_name}',
            description=f'FinSight {env_name} data key',
            enable_key_rotation=True,
            removal_policy=removal_policy,
        )
        return (
            dynamodb.TableEncryption.CUSTOMER_MANAGED,
            s3.BucketEncryption.KMS,
            key,
        )
    raise ValueError(f'Unknown key_mode {key_mode!r}; expected aws_managed or kms_customer')


def _dynamo_table(
    scope: Construct,
    construct_id: str,
    *,
    table_name: str,
    partition_key: str,
    sort_key: str,
    encryption: dynamodb.TableEncryption,
    encryption_key: kms.IKey | None,
    point_in_time_recovery: bool,
    removal_policy: RemovalPolicy,
    time_to_live_attribute: str | None = None,
) -> dynamodb.Table:
    """Build one encrypted pay-per-request table with environment retention.

    DynamoDB holds rebuildable views and caches only. Aurora remains the source
    of truth, so a lost table can be rebuilt from Aurora without data loss.
    """
    key_kwargs: dict[str, Any] = {}
    if encryption_key is not None:
        key_kwargs['encryption_key'] = encryption_key
    return dynamodb.Table(
        scope,
        construct_id,
        table_name=table_name,
        partition_key=dynamodb.Attribute(name=partition_key, type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name=sort_key, type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        encryption=encryption,
        point_in_time_recovery=point_in_time_recovery,
        time_to_live_attribute=time_to_live_attribute,
        removal_policy=removal_policy,
        **key_kwargs,
    )


class DataStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        vpc: ec2.Vpc,
        env_config: dict[str, Any] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config = env_config if env_config is not None else _load_env_config(env_name)
        removal_policy = _removal_policy(config)
        data_config = _required_section(config, 'data')
        point_in_time_recovery = bool(_required(data_config, 'point_in_time_recovery'))
        aurora_backup_days = int(_required(data_config, 'aurora_backup_retention_days'))
        aurora_deletion_protection = bool(_required(data_config, 'aurora_deletion_protection'))
        table_encryption, bucket_encryption, encryption_key = _encryption(
            self, env_name, str(_required(config, 'key_mode')), removal_policy
        )
        bucket_key_kwargs: dict[str, Any] = {}
        if encryption_key is not None:
            bucket_key_kwargs['encryption_key'] = encryption_key
        table_kwargs: dict[str, Any] = {
            'encryption': table_encryption,
            'encryption_key': encryption_key,
            'point_in_time_recovery': point_in_time_recovery,
            'removal_policy': removal_policy,
        }

        # S3 buckets (parameterized by env)
        self.documents_bucket = s3.Bucket(
            self,
            f'DocumentsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-documents',
            encryption=bucket_encryption,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=removal_policy,
            auto_delete_objects=removal_policy == RemovalPolicy.DESTROY,
            **bucket_key_kwargs,
        )
        self.reports_bucket = s3.Bucket(
            self,
            f'ReportsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-reports',
            encryption=bucket_encryption,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=removal_policy,
            auto_delete_objects=removal_policy == RemovalPolicy.DESTROY,
            **bucket_key_kwargs,
        )
        self.backups_bucket = s3.Bucket(
            self,
            f'BackupsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-backups',
            encryption=bucket_encryption,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=removal_policy,
            auto_delete_objects=removal_policy == RemovalPolicy.DESTROY,
            **bucket_key_kwargs,
        )

        # DynamoDB: rebuildable views and caches. Aurora is the sole source of
        # truth for job state; every row here can be recreated from Aurora and
        # the supporting Postgres records.
        self.answer_cache = _dynamo_table(
            self,
            f'AnswerCache{env_name}',
            table_name=f'finsight-{env_name}-answer-cache',
            partition_key='pk',
            sort_key='sk',
            time_to_live_attribute='ttl',
            **table_kwargs,
        )
        self.role_cache = _dynamo_table(
            self,
            f'RoleCache{env_name}',
            table_name=f'finsight-{env_name}-role-cache',
            partition_key='pk',
            sort_key='sk',
            time_to_live_attribute='ttl',
            **table_kwargs,
        )
        self.metering = _dynamo_table(
            self,
            f'Metering{env_name}',
            table_name=f'finsight-{env_name}-metering',
            partition_key='pk',
            sort_key='sk',
            **table_kwargs,
        )
        self.job_progress = _dynamo_table(
            self,
            f'JobProgress{env_name}',
            table_name=f'finsight-{env_name}-job-progress',
            partition_key='job_id',
            sort_key='company_id',
            **table_kwargs,
        )
        self.sessions = _dynamo_table(
            self,
            f'Sessions{env_name}',
            table_name=f'finsight-{env_name}-sessions',
            partition_key='company_id',
            sort_key='session_id',
            **table_kwargs,
        )
        self.chat_history = _dynamo_table(
            self,
            f'ChatHistory{env_name}',
            table_name=f'finsight-{env_name}-chat-history',
            partition_key='company_id',
            sort_key='message_id',
            **table_kwargs,
        )

        # Aurora PostgreSQL with pgvector (parameterized; no hardcoded creds).
        # Aurora is the source of truth for documents, jobs and chat metadata.
        aurora_kwargs: dict[str, Any] = {}
        if encryption_key is not None:
            aurora_kwargs['storage_encryption_key'] = encryption_key
        self.cluster = rds.DatabaseCluster(
            self,
            f'AuroraCluster{env_name}',
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4
            ),
            writer=rds.ClusterInstance.provisioned('writer'),
            vpc=vpc,
            default_database_name=f'finsight_{env_name}',
            storage_encrypted=True,
            backup=rds.BackupProps(retention=Duration.days(aurora_backup_days)),
            deletion_protection=aurora_deletion_protection,
            removal_policy=removal_policy,
            **aurora_kwargs,
        )
        self.source_of_truth = self.cluster
