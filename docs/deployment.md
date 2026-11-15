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
| Operator user + guardrails | `aws-cli` IAM user, three deny policies | `infra/cdk/policies/`; see "Operator access model" below |

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

## Operator access model

Two identities reach this account, and they are deliberately different.

| Identity | What it is | What it can do |
|---|---|---|
| **Root user** (`069632763967`) | The account owner | Everything, including root-only operations (root password, root email, root MFA, closing the account). Protected by MFA and kept in a password manager. Never used for day-to-day work |
| **`aws-cli` IAM user** | The operator identity used by CI tooling and by an agent with the key | Only what the three guardrail policies allow. Revocable by deleting one access key, with no effect on any other resource |

The operator user's credentials live in `~/.aws/credentials` (mode `0600`) and
must also be stored in a password manager — the file on one laptop is not a
backup.

### The three guardrail policies

They live in the repository under `infra/cdk/policies/` and are attached to the
`aws-cli` user:

| Policy | What it grants | What it denies |
|---|---|---|
| `finsight-aws-cli-identity` | The baseline: everything in this account | Creating or changing IAM users; anyone else's access keys; roles or policies outside `finsight-*` / `FinSight-*` / `cdk-*`; the OIDC and SAML providers; any permissions boundary |
| `finsight-aws-cli-data` | — | `organizations:*`, `account:*`, web-identity and SAML federation; assuming any role but the app's; stacks other than `FinSight-*` / `CDKToolkit`; SSM parameters outside `/finsight/*` and `/cdk-bootstrap/*`; secrets and KMS decrypts outside the app's |
| `finsight-aws-cli-services` | — | Object reads/writes and bucket policies outside `finsight-*` / `cdk-*`; log writes outside the app's groups; compute, ML, and messaging services the application never uses |

The baseline is `Allow *`, so the deny list is the guardrail: any AWS action
that is not on it is permitted in this account. Keep that in mind before
adding a service the application does not use.

### Applying and verifying

```bash
# attach the three guardrails (order matters: attach before removing admin)
for name in identity data services; do
  aws iam create-policy \
    --policy-name "finsight-aws-cli-$name" \
    --policy-document "file://infra/cdk/policies/finsight-aws-cli-$name.json" \
    --description "Deny guardrails for the FinSight AI aws-cli user"
  aws iam attach-user-policy --user-name aws-cli \
    --policy-arn "arn:aws:iam::069632763967:policy/finsight-aws-cli-$name"
done

# AdministratorAccess is no longer needed: the identity policy grants the baseline
aws iam detach-user-policy --user-name aws-cli \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

Then prove both halves — that the work still succeeds and that the guardrails
still block:

```bash
uv run python scripts/verify_aws_cli_permissions.py
```

The verifier makes only read-only calls (or calls against resources that do
not exist) and evaluates the resource-scoped decisions with the IAM policy
simulator, so running it changes nothing. It prints `all 51 checks passed` when
the arrangement is intact.

**Never** attach these as a permissions boundary or an inline user policy:
both are capped at 2,048 characters and would be rejected. They are attached
managed policies, each under the 6,144-character limit.

### Getting back in if you are locked out

1. Sign in to the **management account** (`My-Team`, `899706604406`) as root.
2. IAM Identity Center → assign yourself to `FinSight AI` → sign in with the
   `AccountFullAccessRole` permission set.
3. From there, create a new access key for `aws-cli` and update
   `~/.aws/credentials`.

The root password, the root MFA backup codes and the operator access key should
all live in a password manager. Each account's **alternate contact** (email and
phone) is the only recovery path that works when everything else is lost.

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
