# Infrastructure

This directory contains infrastructure definitions for FinSight AI.

## Local development
- `docker-compose.test.yml` (repo root) for local services (Postgres+pgvector, LocalStack, Redis, OTel)
- `localstack/`, `postgres/`, `otel/` contain bootstrap/config for local stack

## Production/deployment (IaC)
We use AWS CDK in Python under `infra/cdk/` (decision record:
`docs/adr/0002-infrastructure-as-code.md`).

**Implemented (scaffold):**
- Network (VPC, subnets, security groups)
- Data (Aurora PostgreSQL, DynamoDB tables, S3 buckets)
- Messaging (SQS queues + DLQs)
- Auth (Cognito user pool + app client)
- Compute (placeholder Lambda function and IAM role)
- Observability (CloudWatch log group)

**Not implemented yet:** Step Functions, CloudWatch dashboards and alarms,
Secrets Manager/SSM wiring, real function packages, and the deploy workflow.

## CI
`make infra-synth` and `make infra-test` run in the `Infra Synth` CI job on
every PR. They synthesize every stack and need no AWS credentials.

```bash
make infra-synth   # cdk app.synth()
make infra-test    # smoke tests, including unknown-environment rejection
```

## Secrets
No secrets committed. Use AWS Secrets Manager or SSM Parameter Store. Deploys
will use GitHub OIDC once the deploy workflow exists (see
`docs/deployment.md`).
