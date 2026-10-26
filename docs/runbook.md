# Runbook

**Status: scaffolding.** These are the intended procedures. No deploy pipeline
exists yet, so none of this has been exercised. See
[deployment.md](deployment.md).

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
- CloudWatch Logs: `/aws/lambda/finsight-{env}`
- CloudWatch Dashboards/Alarms (via ObservabilityStack)
- OpenTelemetry collector for traces

## Incidents
1. Assess impact
2. Rollback if necessary
3. Document in incident report
4. Follow up with post-mortem

## Secrets Management
- Use AWS Secrets Manager / SSM Parameter Store
- Rotate credentials regularly
- Never commit secrets
- Use GitHub OIDC for CI/CD
