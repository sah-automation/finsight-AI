# Infrastructure

This directory contains infrastructure definitions for FinSight AI.

## Local development
- `docker-compose.test.yml` (repo root) for local services (Postgres+pgvector, LocalStack, Redis, OTel, Arize Phoenix)
- `localstack/`, `postgres/`, `otel/` contain bootstrap/config for local stack
- Traces: applications send OTLP to the collector (`http://localhost:4318/v1/traces`,
  `config/dev.yaml` `otlp_endpoint`), the collector deletes blocklisted span
  attributes (`attributes/redact`) and exports to Phoenix (SQLite mode, UI at
  `http://localhost:6006`). Contract: `tests/contract/test_otel_collector_phoenix_contract.py`

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
