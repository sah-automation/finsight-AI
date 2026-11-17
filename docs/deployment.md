# Deployment Guide

**Status: production deployed (Stage D-7).** Stage B provisioned the
account-level plumbing (see below), Stage C the application stacks, and the
Deploy workflow (`.github/workflows/deploy.yml`) now builds, deploys, migrates
and smoke-tests the live API on every push to `main`. The live production API
serves `GET /health` and the read-only `/ask` endpoint. Remaining steps that
need the account owner are listed under "Remaining owner steps" and
"Owner-gated production steps" below.

## Overview

FinSight AI is deployed as AWS Lambda zip packages behind an API Gateway HTTP
API. Infrastructure is defined with AWS CDK in `infra/cdk/`. Deployments use
GitHub OIDC (no long-lived AWS keys) via the Deploy workflow.

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
| Role permissions | `finsight-deploy-policy` (customer managed) | Policy document committed at `infra/iam/finsight-deploy-policy.json`; the owner applies it (the operator cannot create IAM policies) |
| GitHub Environments | `dev`, `staging`, `production` | Each holds `AWS_ROLE_ARN` + `AWS_REGION` environment variables |
| Billing budget | `finsight-monthly-budget` (monthly, USD) | Amount comes from `alerts.monthly_budget_usd` in `infra/cdk/config/envs.yaml`, applied by `scripts/apply_billing_guardrails.py` |
| Cost anomaly monitor | `finsight-cost-anomaly` (per service) + `finsight-cost-anomaly-subscription` | Subscribed by email; threshold comes from `alerts.anomaly_threshold_usd` in the same file |
| OIDC identity provider | `arn:aws:iam::069632763967:oidc-provider/token.actions.githubusercontent.com` | Client id `sts.amazonaws.com`; the role's trust policy points at it |
| CDK environment | `CDKToolkit` stack in `us-east-1` | Bootstrap version 23; asset bucket `cdk-hnb659fds-assets-069632763967-us-east-1` |
| Database credential | `/finsight/prod/neon/database_url` | `SecureString`; the value is never printed, logged or committed |
| Gateway master key | `/finsight/prod/model_gateway_master_key` | `SecureString`; owner-rotated, never owned by CDK (see "Secret-backed values") |
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

## Deployment pipeline (Deploy workflow)

`.github/workflows/deploy.yml` runs on every push to `main` (and on manual
dispatch for `dev`/`staging`/`production`). For `main` pushes the target is
always `prod`; manual dispatch maps the chosen environment name to the CDK env
(`production → prod`). The pipeline:

1. **Build** — `scripts/build_lambda.py` produces `api.zip` and
   `gateway.zip` (uploaded as workflow artifacts, checksum-verified before
   use).
2. **Deploy infrastructure stacks** — CDK deploys Network, Data, Messaging,
   Auth, StepFunctions and Observability. The ApiGateway stack is *not* in
   this phase: it owns the HTTP API routes and their Lambda invoke
   permissions and imports the Compute function ARN, so it must follow
   Compute.
3. **Database migration** (prod) — `scripts/run_migration.py` reads the Neon
   DSN from SSM, runs `alembic upgrade head`, and verifies with
   `alembic current`. A migration failure halts the deployment.
4. **Deploy Compute + ApiGateway** — CDK deploys both (dependency order is
   automatic).
5. **Sync secret-backed Lambda environment** (prod) —
   `scripts/sync_lambda_env.py` re-injects the values CDK must not own (the
   Neon URL → `VECTOR_DB_*`, the gateway master key →
   `MODEL_GATEWAY_AUTH_TOKEN`) into `finsight-prod-api`, merging into the
   CDK-managed environment. CDK resets the function environment on every
   deploy, so this step runs after every deploy.
6. **Smoke tests (deploy gate)** — the smoke job resolves the custom domain
   (falling back to the raw execute-api endpoint while DNS is not resolving),
   obtains a JWT for the smoke-test user via `admin-initiate-auth`, and runs
   `scripts/smoke_test.py`: `GET /health` must return 200
   `{"status": "ok"}` and `POST /ask` must stream a complete SSE envelope. A
   failure fails the deploy loudly (unless `force` was set).

GitHub Environments `dev`, `staging` and `production` exist with no
protection rules yet; secrets for the smoke user live on `production`.

### Secret-backed values (never through CDK)

| Parameter | Feeds | How it is set |
|---|---|---|
| `/finsight/<env>/neon/database_url` | `VECTOR_DB_*` on the API Lambda | Owner, one-time per environment (see "Application secrets") |
| `/finsight/<env>/model_gateway_master_key` | `MODEL_GATEWAY_AUTH_TOKEN` on the API Lambda; read at runtime by the gateway itself | Owner, one-time per environment: `aws ssm put-parameter --name <param> --type SecureString --value <generated-key> --overwrite` (this creates the parameter when it does not exist yet). CDK only references the name and grants the gateway `ssm:GetParameter`; it never creates or updates the parameter, because CloudFormation cannot change an existing SSM parameter's `Type` and a CDK-managed value would overwrite the rotated key. `sync_lambda_env.py` fails loudly if the parameter is missing or still holds a scaffold placeholder |

> **Stack-state migration (2026-11-17, prod).** The `ModelGatewayMasterKeyprod`
> parameter was originally created by the Compute stack as `Type: String` and
> then rotated by the owner into a `SecureString`. A CDK-managed template would
> have failed CloudFormation early validation on the `Type` change (and, had it
> passed, overwritten the rotated key). Before the stack stopped managing the
> parameter, a template-only changeset was executed against
> `FinSight-prod-Compute` setting `DeletionPolicy: Retain` on the recorded
> resource, so the deploy that removes the resource retains the physical
> parameter instead of deleting it. Fresh environments never need this: the
> owner creates the parameter directly in SSM and CDK never owns it.
| `/finsight/<env>/source_viewer_signing_key` | `SOURCE_VIEWER_SIGNING_KEY` on the API Lambda (required by the config loader's `documents` section) | Owner, one-time per environment: `aws ssm put-parameter --name <param> --type SecureString --value <generated-key> --overwrite` (this creates the parameter when it does not exist yet). `sync_lambda_env.py` fails loudly if it is missing |
| `/finsight/<env>/groq_api_key` | `GROQ_API_KEY` on the gateway Lambda (litellm provider key) | Owner, one-time per environment: `aws ssm put-parameter --name <param> --type SecureString --value <key> --overwrite`. Missing parameters are skipped with a warning so a subset of providers can be configured |
| `/finsight/<env>/gemini_api_key` | `GEMINI_API_KEY` on the gateway Lambda (litellm provider key) | Same as above |
| `/finsight/<env>/nvidia_nim_api_key` | `NVIDIA_NIM_API_KEY` on the gateway Lambda (litellm provider key) | Same as above |
| `/finsight/<env>/cohere_api_key` | `COHERE_API_KEY` on the gateway Lambda (litellm provider key) | Same as above |
| `/finsight/<env>/nvidia_api_key` | `NVIDIA_API_KEY` on the gateway Lambda (litellm provider key) | Same as above |

> **Stack-state migration (2026-11-17, prod) — drifted `/health` route.** A
> `GET /health` route exists on the prod HTTP API that CloudFormation never
> created: it appears in no `FinSight-prod-ApiGateway` template and no stack
> event history. Because the route physically exists, the stack's CREATE of
> its own `GET /health` route fails with a 409
> `ConflictException: Route with key GET /health already exists for this API`
> and the stack rolls back. The deploy workflow therefore runs a guarded
> "adopt drifted routes" step immediately before the Compute/ApiGateway
> `cdk deploy`: it lists the physical API id from
> `cloudformation list-stack-resources`, and deletes the physical
> `GET /health` route via `apigatewayv2 delete-route` only when
> `list-stack-resources` shows no stack-managed route (no logical id
> containing `GEThealth`). Once a deploy succeeds the stack owns the route
> and the step is a no-op. Fresh environments never need this.

### Smoke-test user

The pipeline authenticates a dedicated read-only user (`smoke-test@finsight.local`,
custom attributes `role=executive_leadership`, `company_id=smoke-test-readonly-tenant`)
with the Cognito `ADMIN_USER_PASSWORD_AUTH` flow, which the app client allows
explicitly. Credentials are stored as the `SMOKE_TEST_USER_EMAIL` /
`SMOKE_TEST_USER_PASSWORD` secrets on the `production` GitHub environment.
JWTs expire within the hour, so the workflow obtains a fresh token per run
instead of storing one.

## Owner-gated production steps

The agent-operator identity cannot perform these; each needs the account
owner:

1. **Deploy role permissions.** `finsight-deploy-role` has no attached
   policies, so GitHub OIDC deployments fail with AccessDenied. The complete
   customer-managed policy is committed at
   `infra/iam/finsight-deploy-policy.json` (built from the synthesized
   templates; roles/tables/queues/parameters are scoped to `FinSight-*` /
   `finsight-*`, and `iam:PassRole`/`AttachRolePolicy` are constrained
   accordingly). Apply it with:

   ```bash
   aws iam create-policy \
     --policy-name finsight-deploy-policy \
     --policy-document file://infra/iam/finsight-deploy-policy.json
   aws iam attach-role-policy \
     --role-name finsight-deploy-role \
     --policy-arn "arn:aws:iam::069632763967:policy/finsight-deploy-policy"
   ```

2. **DNS for the custom domain.** The ACM certificate for
   `api.finsight.sahcreatives.com` is validated, but the DNS zone is managed
   outside this account: the CNAME for `api.finsight.sahcreatives.com` must
   point at the HTTP API endpoint (region alias name of
   `d-…​.execute-api.us-east-1.amazonaws.com` for the API id `bnf10a9j6l`,
   resolvable with `aws apigatewayv2 get-domain-name`). Until the record is
   corrected, the API is reachable only through the raw endpoint and the
   smoke gate falls back to it.

3. **LLM provider API keys.** The model gateway uses litellm provider
    models (groq/gemini/nvidia_nim/cohere); their API keys are stored as
    SecureStrings in SSM (`/finsight/<env>/groq_api_key`, etc.) and synced
    to the gateway Lambda by `sync_lambda_env.py --target gateway` after
    every deploy. To add or rotate a key:

        aws ssm put-parameter --name /finsight/prod/groq_api_key --type SecureString --value <key> --overwrite
        # then re-run the gateway sync (or trigger a deploy)
        uv run python scripts/sync_lambda_env.py --target gateway --environment prod --region us-east-1

    Until keys are set, `/ask` answers come back as the graceful
    `insufficient_data` envelope instead of real answers. Keys must never
    be committed.

4. **Budget email notifications** — see "Remaining owner steps" below.

## Rollback

### Lambda

- Redeploy the previous published version or shift the alias.

### Database

- Forward-only migrations only in production.
- Documented restore path from backups (see [runbook](runbook.md)).
- Do **not** rely on `alembic downgrade` in production.

### Container

- Redeploy the previous image digest.

## Smoke tests

The deploy workflow's final gate runs `scripts/smoke_test.py` against the
live custom domain (see "Deployment pipeline"); it asserts:

- `GET /health` returns 200 with `{"status": "ok"}`.
- One read-only `POST /ask` (the dedicated `smoke-test-readonly-tenant`)
  streams a complete SSE answer envelope.

## Deployment evidence (Stage D-7)

- **Date:** 2026-11-18
- **Green deploy run:** https://github.com/sah-automation/finsight-AI/actions/runs/44146564438
  (workflow_dispatch, production; push-triggered mirror run 44146259303 also green)
- **Custom domain:** https://api.finsight.sahcreatives.com → CNAME `d-qyvjxyznah.execute-api.us-east-1.amazonaws.com`
- **`GET /health`:** 200 `{"status": "ok"}` (both custom domain and raw API endpoint)
- **`POST /ask`:** 200 SSE stream with a complete answer envelope; returns the
  documented graceful `insufficient_data` envelope (`no_evidence`) because the
  LLM provider API keys (groq/gemini) are an owner-gated step still pending —
  this satisfies the "complete envelope" requirement.
- **ApiGateway stack:** `UPDATE_COMPLETE` with stack-managed `GET /health` route
  (drift adopted by the guarded step in the deploy job).
- **Compute stack:** `UPDATE_COMPLETE` with real Lambda code (79 MB) and 30 s
  API / 900 s gateway timeouts.

## Deployment evidence (Stage D-8)

- **Date:** 2026-11-18
- **Rollback exercise:** published Lambda versions 1 and 2 of
  `finsight-prod-api`; shifted the `live` alias 1 → 2 → 1. Each invocation
  returned `{"status":"ok"}` with `ExecutedVersion` matching the alias target,
  so the previous version serves correctly through the alias.
- **CloudWatch dashboard:** `finsight-prod` dashboard is live (alarms +
  OTLP span query widget) after the Observability stack update.
- **Alarms:** all five `finsight-prod-*` alarms are in `OK` state
  (treat-missing-data = not breaching).
- **OTLP traces:** exported to `/aws/lambda/finsight-prod` log group via the
  CloudWatch Logs OTLP endpoint using the `x-aws-logs-group` /
  `x-aws-logs-stream` routing headers wired by the Compute stack
  (`OTLP_HEADERS`).
- **Cost guardrails:** budget alarm `finsight-monthly-budget` and the
  `finsight-cost-anomaly` monitor/subscription are left for the account owner
  to confirm in the AWS console (no Cost Explorer / Budgets API calls from
  scripts or CI; those calls bill per request).

See [runbook.md](runbook.md) for operational procedures.
