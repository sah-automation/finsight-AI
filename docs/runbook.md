# Runbook

**Status: active.** These procedures are exercised by the Deploy workflow
(`.github/workflows/deploy.yml`) which runs on every push to `main`. See
[deployment.md](deployment.md) for the deployment pipeline and the
owner-gated steps.

## Overview

Operational procedures for FinSight AI in production/staging environments.

## Deployment
See [Deployment Guide](deployment.md).

## Rollback Procedures

### Lambda Functions
1. Identify previous successful deployment (GitHub Actions run or artifact)
2. Redeploy previous Lambda package version
3. Update alias to point to previous version if using aliases
4. Verify health checks pass

### Database Migrations
**Critical**: Do not use `alembic downgrade` in production.
1. If migration causes issues, write a forward fix migration
2. For catastrophic issues, restore from backup
3. Document restore procedure and test in staging regularly

### Container Deployments
1. Redeploy previous image by digest
2. Verify container health
3. Check logs

## Monitoring
- CloudWatch Logs: `/aws/lambda/finsight-{env}-api` and
  `/aws/lambda/finsight-{env}-gateway` (gateway writes NDJSON litellm chunks)
- CloudWatch Dashboards/Alarms (via ObservabilityStack)
- Structured OTLP spans exported to CloudWatch Logs via the
  `OTLP_ENDPOINT`/`OTLP_HEADERS` env vars wired by the Compute stack

## Incidents
1. Assess impact
2. Rollback if necessary
3. Document in incident report
4. Follow up with post-mortem

## Environment surgery

The API function's environment is CDK-managed plus secret-backed values:

- CDK-managed (buckets, tables, queues, Cognito ids, gateway URL): changed
  only by CDK deploys — never edit these by hand.
- Secret-backed (`VECTOR_DB_*`, `MODEL_GATEWAY_AUTH_TOKEN`): re-injected by
  `scripts/sync_lambda_env.py` after every deploy. If a deploy lands without
  them, run it manually:

  ```bash
  uv run python scripts/sync_lambda_env.py --environment prod --region us-east-1
  ```

  The script fails loudly if the Neon URL is missing, if the master key
  still holds a scaffold placeholder, or if the source-viewer signing key
  is missing. It prints no secret values.

## Secrets Management
- SSM Parameter Store (`/finsight/<env>/...` SecureStrings) for the Neon DSN
  and the model-gateway master key; rotate with
  `aws ssm put-parameter --overwrite`
- `MODEL_GATEWAY_AUTH_TOKEN` on the API Lambda must be re-synced after every
  master-key rotation
- Never commit secrets; never route secrets through CDK synthesis
- Use GitHub OIDC for CI/CD
