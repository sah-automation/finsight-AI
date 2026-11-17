# Runbook

**Status: verified (Stage D-8).** These procedures are exercised by the Deploy
workflow (`.github/workflows/deploy.yml`) which runs on every push to `main`,
and the Lambda alias rollback path was exercised once against the live
production function. See [deployment.md](deployment.md) for the deployment
pipeline and the owner-gated steps.

## Overview

Operational procedures for FinSight AI in production/staging environments.

## Deployment
See [Deployment Guide](deployment.md).

## Rollback Procedures

### Lambda Functions (alias-based, verified 2026-11-18)

The deploy workflow publishes a new Lambda version on every deploy and keeps
the `live` alias on the last known-good version until the smoke gate passes.

1. List published versions:
   ```bash
   aws lambda list-versions-by-function --function-name finsight-prod-api --region us-east-1
   ```
2. Shift the `live` alias to the previous version:
   ```bash
   aws lambda update-alias --function-name finsight-prod-api --name live \
     --function-version <previous-version> --region us-east-1
   ```
3. Verify the previous version still serves through the alias:
   ```bash
   aws lambda invoke --function-name arn:aws:lambda:us-east-1:069632763967:function:finsight-prod-api:live \
     --cli-binary-format raw-in-base64-out --payload '{"version":"2.0","routeKey":"GET /health","rawPath":"/health","requestContext":{"http":{"method":"GET","path":"/health"}}}' /tmp/health.json
   cat /tmp/health.json   # expect {"status":"ok"}
   ```
4. Re-run the smoke tests against the endpoint once the alias is stable.
5. To move forward again, publish a new version and point the alias at it (or
   re-run the deploy workflow).

The endpoint (`GET /health`) is also reachable directly through API Gateway,
which invokes `$LATEST`; the alias is the rollback lever and is exercised
independently of the gateway integration.

### Database Migrations
**Critical**: Do not use `alembic downgrade` in production.
- Schema changes are forward-only. A broken migration is fixed by a new
  forward migration, never by `alembic downgrade`.
- For catastrophic data loss/corruption, restore the Neon database from a
  point-in-time backup (Neon console → Branches → Restore). Document the
  restore point and re-run `alembic upgrade head` only after the restore.
- `alembic downgrade` is forbidden in production; CI and runbooks must not
  invoke it.

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
