# Deployment Guide

**Status: plumbing in place, no application deployed.** Stage B of the AWS
plan (`docs/plans/aws-infra-cicd-plan.md`) provisioned the account-level
plumbing: AWS credentials and CLI, a config-driven billing budget with anomaly
alerts, an IAM deployment role trusting GitHub OIDC, GitHub Environments, and a
manual OIDC smoke workflow. No application stack is deployed yet, and there is
still no deploy/release workflow — that is Stage D. Four provisioning steps
remain blocked by the organization's service control policies; they are listed
under "Blocked by organization policy" below. In particular the OIDC identity
provider does not exist yet, so the smoke workflow cannot succeed until an
organization administrator creates it.

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

## Provisioned (Stage B)

Target account: `069632763967` (region `us-east-1`).

| Resource | Identifier | Where it is configured |
|---|---|---|
| IAM deployment role | `arn:aws:iam::069632763967:role/finsight-deploy-role` | Trust policy scoped to this repo's `dev`/`staging`/`production` environments |
| Role permissions | `finsight-deploy-policy` (customer managed) | Deliberately light; tightened in Stage C |
| GitHub Environments | `dev`, `staging`, `production` | Each holds `AWS_ROLE_ARN` + `AWS_REGION` environment variables |
| Billing budget | `finsight-monthly-budget` (monthly, USD) | Amount comes from `alerts.monthly_budget_usd` in `infra/cdk/config/envs.yaml` |
| Cost anomaly monitor | `finsight-cost-anomaly` (per service) + `finsight-cost-anomaly-subscription` | Subscribed by email; threshold from the same config value |
| OIDC smoke workflow | `.github/workflows/aws-role-smoke.yml` | Manual trigger; proves GitHub can assume the role |
| OIDC identity provider | **not created** | Blocked by the organization's service control policies (see below) |

The budget threshold is configuration, not code: change
`alerts.monthly_budget_usd` in `infra/cdk/config/envs.yaml` and re-apply the
budget. Nothing else holds the number.

### Verifying the plumbing

```bash
aws sts get-caller-identity
aws budgets describe-budget --region us-east-1 --account-id 069632763967 \
  --budget-name finsight-monthly-budget
aws ce get-anomaly-monitors --region us-east-1
aws ce get-anomaly-subscriptions --region us-east-1
aws iam get-role --role-name finsight-deploy-role
gh api repos/sah-automation/finsight-AI/environments
```

### GitHub OIDC smoke check

Run the `AWS Role Smoke Check` workflow (`workflow_dispatch`) against one of
the environments. It assumes `finsight-deploy-role` through GitHub OIDC, calls
`sts get-caller-identity`, and fails loudly if the assumed identity is not the
expected role in the expected account. It creates nothing and deploys nothing.

### Production reviewer rule

The `production` environment carries the reviewer rule as a definition —
`PRODUCTION_REQUIRED_REVIEWER=sah-automation` and `PRODUCTION_REQUIRED_APPROVALS=1`
— but no `required_reviewers` protection rule is attached, so nothing is gated
while no real users exist. Turning manual approval on is a single call (the
reviewer id is the repository owner):

```bash
gh api --method PUT repos/sah-automation/finsight-AI/environments/production \
  -f reviewers='[{"type":"User","id":266460128}]'
```

GitHub's rulesets API on this instance only accepts `branch`, `tag` and `push`
targets, so the rule is defined on the environment itself rather than as a
repository ruleset.

### Application secrets

The Neon connection string is **not stored yet**: `ssm:PutParameter` is denied
by the organization's service control policies (see below). The intended
destination is a `SecureString` under `/finsight/<env>/neon/database_url`. The
value is never printed, logged, or committed — it is read from a local file and
stored with `aws ssm put-parameter --value file://<path>`. Stage C reads it
through the secrets provider rather than from the repository.

## Blocked by organization policy

The organization's service control policies deny four provisioning actions to
every principal in this account, so they cannot be completed from the project's
own credentials:

- `iam:CreateOpenIDConnectProvider` — the GitHub OIDC identity provider.
  Without it the smoke workflow fails at the assume-role step.
- `cloudformation:*` and `s3:CreateBucket` — `cdk bootstrap` and the
  `CDKToolkit` stack.
- `ssm:PutParameter` — the Neon connection string.
- `billing:GetBillingPreferences` / `billing:UpdateBillingPreferences` — the
  budget's email subscribers. Budgets created without billing-alert preferences
  enabled accept the request but silently drop the notification, so the budget
  alarm currently has no email subscriber. The Cost Explorer anomaly
  subscription is unaffected and is confirmed.

Each needs an organization administrator (or an SCP exception) to run from the
management account. Until then the affected steps are owned by the maintainer,
not by the agent.

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
