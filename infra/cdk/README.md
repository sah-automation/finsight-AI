# FinSight AI CDK (Python)

AWS CDK app for FinSight AI infrastructure. Environments are parameterized
from `config/envs.yaml` (no hardcoded account, region, or resource names).
This is a validated scaffold, not a deployed environment. See issue #10.

## Run from the repository root

```bash
make infra-synth   # synthesize all CDK stacks; no AWS credentials needed
make infra-test    # smoke tests, including unknown-environment rejection
```

`make infra-synth` runs `python -m app.app` from this directory with the
dependencies in `requirements.txt` installed in an ephemeral uv environment.
`cdk.json` uses the same module path, so the CDK CLI also works:

```bash
cd infra/cdk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk synth --all
```

## Stacks

| Stack | Contents |
| --- | --- |
| Network | VPC, public/private/isolated subnets, one NAT gateway |
| Data | Aurora PostgreSQL (source of truth), rebuildable DynamoDB tables, S3 buckets |
| Messaging | SQS queues and DLQ |
| Auth | Cognito user pool and app client |
| Compute | Placeholder Lambda function and execution role |
| Observability | CloudWatch log group |
| Step Functions | Ingestion workflow state machine with DLQ catch targets |

The Data stack defines the rebuildable DynamoDB side of D2: answer cache, role
cache, metering, job progress, sessions and chat history. All six tables are
pay-per-request and encrypted. Non-production tables are destroyed with the
stack; production tables are retained and use point-in-time recovery. Aurora
remains the source of truth for documents, jobs and chat metadata, so DynamoDB
views and caches can be rebuilt from it. Environment settings (retention,
point-in-time recovery, Aurora backups, key mode) come from `config/envs.yaml`.

Not implemented yet: CloudWatch dashboards and alarms, Secrets
Manager/SSM wiring, per-function IAM, and the deploy workflow.

## Environment selection

Set `CDK_ENV` (or the CDK `env` context) to `dev`, `staging`, or `prod`. Any
other value fails the synth. `CDK_ENV` is separate from the application's
`ENVIRONMENT`: `.env.example` sets `ENVIRONMENT=test`, which is the local test
profile and is not a CDK environment, so sourcing `.env` does not change what
the CDK app synthesizes.
