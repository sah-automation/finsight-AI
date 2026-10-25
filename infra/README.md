# Infrastructure

Infrastructure as code.

**Belongs here:**
- CDK/Terraform/Pulumi stacks
- Aurora cluster, pgvector extension
- DynamoDB tables (cache, metering, roles)
- S3 buckets (documents, reports, backups)
- SQS queues (ingestion, reprocessing, reports, dead-letter)
- Lambda functions (API, workers, scheduled)
- Step Functions state machines
- Cognito user pools
- IAM roles and policies
- VPC, subnets, security groups
- CloudWatch dashboards and alarms

**Rules:**
- Config-driven (no hardcoded values)
- Environment parity (dev/staging/prod same structure)
- No manual console edits - all changes via IaC
- Secrets in Secrets Manager, referenced by config
