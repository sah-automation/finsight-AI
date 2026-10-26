# ADR 0002: Infrastructure as Code

## Status
Accepted (scaffold). The stack skeleton and the non-deploying synth check exist. Step Functions, CloudWatch dashboards/alarms, secrets wiring, and the deploy workflow are not implemented yet (DI-20 to DI-22 in `docs/plans/dev-infra-implementation-plan.md`).

## Context
FinSight AI needs deployable infrastructure on AWS (Aurora PostgreSQL with pgvector, S3, SQS, DynamoDB, Cognito, Lambda, Step Functions, IAM, VPC, CloudWatch). We need reproducible environments (dev/staging/prod) and CI validation of templates. The plan (DI-20) requires choosing a tool and adding stacks.

## Decision
Use AWS CDK in Python (same language as the application). Rationale:
- Type-safe constructs, good integration with Lambda and Step Functions
- Parameterized per environment from `infra/cdk/config/envs.yaml`
- Synthesizable and testable in CI without AWS credentials
- Familiar to a Python team

## Consequences
- `infra/cdk/` contains the app, config, stacks, and smoke tests
- CI runs `make infra-synth` and `make infra-test` in the `Infra Synth` job (non-deploying)
- Deploys use GitHub OIDC, never long-lived AWS keys (deferred, DI-22)
- All resource names and IDs come from environment config; no hardcoded account or region
- Secrets come from AWS Secrets Manager or SSM, never committed
- The Lambda function is a placeholder until the API entrypoint exists; when
  `dist/lambda/api.zip` is present, the stack uses it instead of placeholder code
