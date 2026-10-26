from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import Construct


class DataStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, env_name: str, vpc: ec2.Vpc, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 buckets (parameterized by env)
        self.documents_bucket = s3.Bucket(
            self,
            f'DocumentsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-documents',
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
            auto_delete_objects=env_name != 'prod',
        )
        self.reports_bucket = s3.Bucket(
            self,
            f'ReportsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-reports',
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
            auto_delete_objects=env_name != 'prod',
        )
        self.backups_bucket = s3.Bucket(
            self,
            f'BackupsBucket{env_name}',
            bucket_name=f'finsight-{env_name}-backups',
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
            auto_delete_objects=env_name != 'prod',
        )

        # DynamoDB tables
        self.answer_cache = dynamodb.Table(
            self,
            f'AnswerCache{env_name}',
            table_name=f'finsight-{env_name}-answer-cache',
            partition_key=dynamodb.Attribute(name='pk', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
        )
        self.role_cache = dynamodb.Table(
            self,
            f'RoleCache{env_name}',
            table_name=f'finsight-{env_name}-role-cache',
            partition_key=dynamodb.Attribute(name='pk', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
        )
        self.metering = dynamodb.Table(
            self,
            f'Metering{env_name}',
            table_name=f'finsight-{env_name}-metering',
            partition_key=dynamodb.Attribute(name='pk', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
        )

        # Aurora PostgreSQL with pgvector (parameterized; no hardcoded creds)
        self.cluster = rds.DatabaseCluster(
            self,
            f'AuroraCluster{env_name}',
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4
            ),
            writer=rds.ClusterInstance.provisioned('writer'),
            vpc=vpc,
            default_database_name=f'finsight_{env_name}',
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
        )
