# Deployment Guide

**Status: scaffolding.** The infrastructure is defined in `infra/cdk/` and
`make infra-synth` validates it without deploying. There is no deploy workflow
yet: DI-22 is deliberately deferred until an AWS account, OIDC role, and the
GitHub Environments exist. Do not treat any command here as a working
production procedure.

## Overview

FinSight AI will be deployed as AWS Lambda zip packages behind API Gateway.
Infrastructure is defined with AWS CDK in `infra/cdk/`. Deployments are
intended to use GitHub OIDC (no long-lived AWS keys).

## Environments

- `dev` - development
- `staging` - staging
- `production` - production (requires manual approval in GitHub Environments)

Known environment names live in `infra/cdk/config/envs.yaml`, selected with
`CDK_ENV` (or the CDK `env` context). The app fails loudly when the value is
not listed there. `CDK_ENV` is separate from the application's `ENVIRONMENT`.

## Prerequisites (not yet provisioned)

- AWS account with appropriate permissions
- GitHub Environments (`dev`, `staging`, `production`) with protection rules
- An AWS IAM role trusting GitHub OIDC, stored as `AWS_ROLE_ARN`
- An `AWS_REGION` repository or environment variable

## Validating changes

```bash
make infra-synth   # synthesize every stack, no AWS credentials needed
make infra-test    # CDK smoke tests, including the unknown-environment check
```

The CI `Infra Synth` job runs both commands on every PR.

## Deployment process (not implemented)

The intended flow, once DI-22 closes:

1. Build artifacts with `make lambda-build` (zip + checksum) and
   `make docker-build` (container image).
2. Assume the environment role through GitHub OIDC.
3. Run `cdk deploy --all` for the target environment.
4. Run the smoke checks below.

There is no release/tag workflow yet. Do not add a `v*` tag expecting a deploy.

## Rollback

### Lambda

- Redeploy the previous published version or shift the alias.

### Database

- Forward-only migrations only in production.
- Documented restore path from backups (see [runbook](runbook.md)).
- Do **not** rely on `alembic downgrade` in production.

### Container

- Redeploy the previous image digest.

## Smoke tests (once an entrypoint exists)

- Health endpoint responds.
- One read-only check passes.

See [runbook.md](runbook.md) for operational procedures.
