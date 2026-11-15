# Deployment Guide

**Status: Stage B complete, no application deployed.** Stage B of the AWS
plan (`docs/plans/aws-infra-cicd-plan.md`) provisioned the account-level
plumbing: AWS credentials and CLI, a config-driven billing budget with anomaly
alerts, an IAM deployment role trusting GitHub OIDC, GitHub Environments, the
GitHub OIDC identity provider, a bootstrapped CDK environment, the Neon
credential in SSM Parameter Store, and a manual OIDC smoke workflow that passes
on all three environments. No application stack is deployed yet, and there is
still no deploy/release workflow — that is Stage D. One step still needs the
account owner: enabling the budget's email notifications, listed under
"Remaining owner steps" below.

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
| Billing budget | `finsight-monthly-budget` (monthly, USD) | Amount comes from `alerts.monthly_budget_usd` in `infra/cdk/config/envs.yaml`, applied by `scripts/apply_billing_guardrails.py` |
| Cost anomaly monitor | `finsight-cost-anomaly` (per service) + `finsight-cost-anomaly-subscription` | Subscribed by email; threshold comes from `alerts.anomaly_threshold_usd` in the same file |
| OIDC identity provider | `arn:aws:iam::069632763967:oidc-provider/token.actions.githubusercontent.com` | Client id `sts.amazonaws.com`; the role's trust policy points at it |
| CDK environment | `CDKToolkit` stack in `us-east-1` | Bootstrap version 23; asset bucket `cdk-hnb659fds-assets-069632763967-us-east-1` |
| Database credential | `/finsight/prod/neon/database_url` | `SecureString`; the value is never printed, logged or committed |
| OIDC smoke workflow | `.github/workflows/aws-role-smoke.yml` | Manual trigger; proves GitHub can assume the role |

### The trust policy's subject format

GitHub's OIDC `sub` claim is **not** `owner/repo` for every repository. When
the repository owner is a user rather than an organization, the claim carries
numeric ids:

```
repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:<environment-name>
```

For this repository that is
`repo:sah-automation@266460128/finsight-AI@1433058315:environment:dev`. The
role's trust policy lists the `dev`, `staging` and `production` variants of
that string. A trust policy written against the organization-style
`repo:sah-automation/finsight-AI:environment:dev` never matches, and AWS
reports it as the unhelpful *"Not authorized to perform
sts:AssumeRoleWithWebIdentity"*.

Read the real claim out of CloudTrail when it changes:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --max-results 1 --output json \
  | jq -r '.Events[0].Username'
```

The budget threshold is configuration, not code: `alerts.monthly_budget_usd` in
`infra/cdk/config/envs.yaml` is the only place the amount is written down, and
`scripts/apply_billing_guardrails.py` reads it through the same loader the CDK
stacks use and applies it to AWS. Changing the threshold is a config change
plus one run of that script:

```bash
uv run python scripts/apply_billing_guardrails.py --env prod
```

The script is idempotent (it replaces an existing budget, reuses the anomaly
monitor, never creates a second subscription) and it reads every resource back
before reporting, so its output states what exists in the account rather than
what was requested.

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

All three environments pass:

```bash
gh workflow run aws-role-smoke.yml --ref main -f environment=dev
gh workflow run aws-role-smoke.yml --ref main -f environment=staging
gh workflow run aws-role-smoke.yml --ref main -f environment=production
```

A passing run ends with
`OIDC trust chain verified: assumed role ARN arn:aws:sts::069632763967:assumed-role/finsight-deploy-role/finsight-aws-role-smoke in account 069632763967`.

### Production reviewer rule

The `production` environment carries the reviewer rule as a definition —
`PRODUCTION_REQUIRED_REVIEWER=266460128` (the repository owner's user id) and
`PRODUCTION_REQUIRED_APPROVALS=1` — but no `required_reviewers` protection rule
is attached, so nothing is gated while no real users exist. Turning manual
approval on is a single call that uses the recorded id verbatim:

```bash
gh api --method PUT repos/sah-automation/finsight-AI/environments/production \
  -f reviewers='[{"type":"User","id":266460128}]'
```

GitHub's rulesets API on this instance only accepts `branch`, `tag` and `push`
targets, so the rule is defined on the environment itself rather than as a
repository ruleset.

### Application secrets

The Neon connection string is stored in SSM Parameter Store as a `SecureString`
under `/finsight/<env>/neon/database_url`. The value is never printed, logged
or committed: the owner pastes it into a local file with owner-only
permissions (outside the repository), the agent reads it in memory, hands it
straight to the SSM API, verifies the parameter by metadata only, and then
removes the local file.

| Parameter | State |
|---|---|
| `/finsight/prod/neon/database_url` | **Stored** — `SecureString`, version 1 |
| `/finsight/dev/neon/database_url` | Not created — the `dev` environment gets its own database when it has one; the production credential is deliberately not copied into a development path |
| `/finsight/staging/neon/database_url` | Same as `dev` |

Stage C reads the parameter through the secrets provider rather than from the
repository. The application config (`config/*.yaml`) still carries the
`VECTOR_DB_*` placeholders that Stage C replaces with the stored DSN.

To store another environment's credential:

```bash
uv run python scripts/capture_neon_credential.py
uv run python scripts/store_neon_parameter.py \
  --parameter-name /finsight/dev/neon/database_url
```

## Remaining owner steps

One step needs the account owner, and it is not blocked by a policy — the
organization's service control policy was narrowed so that `cloudformation:*`,
the `s3`/`sqs`/`ssm` actions the tooling needs, and
`sts:AssumeRoleWithWebIdentity` are permitted in `us-east-1`.

1. **Enable the budget's email notifications.** AWS accepts a budget
   notification and then silently drops it when billing-alert preferences are
   off, so `finsight-monthly-budget` currently has **no** email subscriber.
   The Cost Explorer anomaly subscription is unaffected and is `CONFIRMED`.
   Fix it by enabling billing alerts and re-applying the budget from the same
   config file:

   ```bash
   aws billing update-billing-preferences --features BILLING_ALERTS
   uv run python scripts/apply_billing_guardrails.py --env prod
   ```

   The script replaces the existing budget (AWS rejects a second budget with
   the same name), reuses the anomaly monitor, and prints a warning when the
   budget still carries no email subscriber.

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
