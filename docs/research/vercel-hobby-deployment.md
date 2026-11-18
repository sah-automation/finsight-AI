# Research: Vercel Hobby Deployment Controls

**Issue:** [#346](https://github.com/sah-automation/finsight-AI/issues/346) — Research Vercel Hobby deployment controls
**Date:** 2026-11-18
**Branch:** `research/vercel-hobby-deployment`

---

## Executive Summary

Vercel Hobby (free tier) provides a generous but constrained platform for personal/non-commercial projects. Key constraints for Phase 2 cutover:
- **Custom domains:** ✅ Supported (50/project), apex `finsight.sahcreatives.com` works with automatic HTTPS
- **Env var API:** ✅ Full CRUD via REST API (encrypted `type: "encrypted"` or `visibility: "secret"`)
- **Deployment triggers:** ✅ Git push to main, PR previews, manual redeploy via Deploy Hooks or CLI
- **Logs:** ⚠️ Runtime logs retained **1 hour only**; build logs indefinite; Drains (log forwarding) **not available on Hobby**
- **Function limits:** 300s max duration, 2GB/1vCPU, 10 concurrent executions, 4.5MB payload
- **External secrets (SSM):** ❌ No native integration; CI sync step required
- **Preview API isolation:** ⚠️ Via **Deployment Protection** (Vercel Auth on all plans); previews get separate env scopes
- **Cost tracking:** ⚠️ Dashboard only; `/v2/usage` API returns limited/empty data on Hobby

---

## 1. Custom Domain (Apex `finsight.sahcreatives.com`) Setup & HTTPS

| Capability | Hobby Support |
|------------|---------------|
| Apex domain (e.g., `finsight.sahcreatives.com`) | ✅ Yes |
| Subdomains | ✅ Yes |
| Domains per project | 50 |
| Automatic HTTPS (Let's Encrypt) | ✅ Yes, managed by Vercel |
| DNS via Vercel nameservers (`ns1/ns2.vercel-dns.com`) | ✅ Recommended |
| Custom nameservers | ✅ Supported |
| SSL certificate provisioning | Automatic, ~minutes |
| Wildcard domains | ✅ Supported |

**Setup steps:**
1. Add domain in Project Settings → Domains
2. Configure DNS: either delegate to Vercel nameservers (`ns1.vercel-dns.com`, `ns2.vercel-dns.com`) or add `A`/`CNAME` records pointing to Vercel
3. Vercel provisions SSL automatically (Let's Encrypt)
4. Verify with `vercel domains verify finsight.sahcreatives.com --project <project>`

**References:**
- [Working with Domains](https://vercel.com/docs/domains/working-with-domains)
- [Limits - Domains](https://vercel.com/docs/limits#domains)

---

## 2. Programmatic Encrypted Environment Variable Management

### API Endpoints (v10 REST API)

| Operation | Method | Endpoint | Rate Limit (Hobby) |
|-----------|--------|----------|-------------------|
| List | `GET` | `/v10/projects/{idOrName}/env` | 500/min (owner) |
| Create (single/batch) | `POST` | `/v10/projects/{idOrName}/env` | 120/min (owner) |
| Update | `PATCH` | `/v9/projects/{idOrName}/env/{id}` | 120/min (owner) |
| Delete (single) | `DELETE` | `/v9/projects/{idOrName}/env/{id}` | 60/min (owner) |
| Delete (batch) | `POST` | `/v10/projects/{idOrName}/env/batch-delete` | 60/min (owner) |

### Encrypted Variable Types

| Type / Visibility | Description | Use Case |
|-------------------|-------------|----------|
| `type: "encrypted"` (legacy) / `visibility: "secret"` (new) | Encrypted at rest, hidden in dashboard, decrypted at build/runtime | **Secrets** (API keys, DB passwords) |
| `type: "plain"` / `visibility: "config"` | Plaintext, visible in dashboard | Non-sensitive config (feature flags, public URLs) |
| `type: "sensitive"` (legacy) | Encrypted, but value visible to project members | Deprecated; use `secret` |

### Key API Parameters

```json
// Create (POST /v10/projects/{idOrName}/env?upsert=true)
{
  "key": "DATABASE_URL",
  "value": "postgresql://...",
  "type": "encrypted",        // or "plain"
  "target": ["production", "preview"],  // or ["development"]
  "comment": "Production DB connection",
  "gitBranch": "main"         // required if target includes "preview" with branch scoping
}
```

- **`upsert=true`** query param: updates existing instead of 409 error
- **`decrypt=true`** on GET: returns decrypted values (requires permission)
- Max 1000 env vars per environment per project
- Total size limit: 64KB (names + values) per deployment

**References:**
- [Retrieve Environment Variables](https://vercel.com/docs/rest-api/projects/retrieve-the-environment-variables-of-a-project-by-id-or-name)
- [Create Environment Variables](https://vercel.com/docs/rest-api/projects/create-one-or-more-environment-variables)
- [Edit Environment Variable](https://vercel.com/docs/rest-api/projects/edit-an-environment-variable)
- [Remove Environment Variable](https://vercel.com/docs/rest-api/projects/remove-an-environment-variable)
- [Environment Variables Docs](https://vercel.com/docs/environment-variables)

---

## 3. Deployment Triggers

| Trigger | Hobby Support | Mechanism |
|---------|---------------|-----------|
| Push to `main` (production) | ✅ | Git integration (GitHub/GitLab/Bitbucket) |
| Push to non-main branch (preview) | ✅ | Git integration |
| Pull Request (preview) | ✅ | Git integration |
| Manual redeploy (after env sync) | ✅ | **Deploy Hooks** (POST to URL) or `vercel --prod` CLI |
| Scheduled/cron redeploy | ✅ | Deploy Hook + external cron (e.g., GitHub Actions) |
| Deploy specific commit SHA | ✅ | `vercel deploy <sha> --prod` |

### Deploy Hooks (for manual/env-sync redeploys)
- **Limit:** 5 hooks/project on Hobby
- **Rate limit:** 60 triggers/hour/project
- **URL format:** `https://api.vercel.com/v1/integrations/deploy/<project-id>/<hook-token>`
- **No auth required** — treat URL as secret
- **Build cache:** Enabled by default (`?buildCache=false` to disable)
- **Branch targeting:** Each hook tied to a specific branch

### Git Integration Caveats (Hobby)
- **Hobby teams cannot connect to Git repositories owned by GitHub organizations** — must use personal account repos or upgrade to Pro
- Commit author must have Vercel project access (email match)
- 100 deployments/day limit

**References:**
- [Deploy Hooks](https://vercel.com/docs/deploy-hooks)
- [Git Configuration](https://vercel.com/docs/project-configuration/git-configuration)
- [Limits - General](https://vercel.com/docs/limits#general-limits)

---

## 4. Log Retention & Programmatic Access

| Log Type | Hobby Retention | Access Method |
|----------|-----------------|---------------|
| **Runtime logs** (function execution) | **1 hour** | Dashboard, CLI (`vercel logs`), REST API (`/v1/projects/{id}/logs`) |
| **Build logs** | Indefinite (per deployment) | Dashboard, CLI, REST API |
| **Request logs** (Edge/Access) | Not retained on Hobby | N/A |

### Programmatic Log Access
- **REST API:** `GET /v1/projects/{idOrName}/logs` (runtime logs within retention window)
- **Rate limit:** 100 requests/minute (user scope)
- **CLI:** `vercel logs <deployment-url>` or `vercel logs --follow`
- **Log Drains (forwarding to external):** ❌ **Not available on Hobby** — requires Pro ($0.50/GB) or Enterprise

### Implications for Phase 2
- **No long-term log storage** on Hobby — logs older than 1 hour are gone
- **No Datadog/Splunk/S3 forwarding** without Pro upgrade
- **Workaround:** Instrument application-level logging to external service (CloudWatch, etc.)

**References:**
- [Runtime Logs Limits](https://vercel.com/docs/logs/runtime#limits)
- [Limits - Logs](https://vercel.com/docs/limits#logs)
- [Drains](https://vercel.com/docs/drains) — "Drains are available on Enterprise and Pro plans"

---

## 5. Function Limits on Hobby

| Limit | Hobby Value | Notes |
|-------|-------------|-------|
| **Max duration** | 300s (5 min) | Default and hard max; Pro configurable to 800s, 1800s beta |
| **Memory / CPU** | 2 GB / 1 vCPU | Default and hard max; Pro up to 4 GB / 2 vCPU |
| **Concurrent executions** | **10** | Soft limit; 11th request queues/times out |
| **Payload size (request/response)** | 4.5 MB | Hard limit for function invocation |
| **Function invocations/month** | 1,000,000 included | Then paused (Hobby) or on-demand (Pro) |
| **Active CPU time/month** | 4 CPU-hrs included | |
| **Provisioned Memory/month** | 360 GB-hrs included | |
| **Edge Requests/month** | 1,000,000 | |
| **Fast Data Transfer/month** | 100 GB | Then paused on Hobby |
| **Build time** | 45 min | All plans |
| **Source upload size (CLI)** | 100 MB | Pro: 1 GB |
| **Concurrent builds** | 1 | Pro: up to 500 |

**Concurrency note:** Multiple sources cite **10 concurrent serverless executions** on Hobby. This is a platform-level limit, not per-function.

**References:**
- [Vercel Functions Limitations](https://vercel.com/docs/functions/limitations)
- [Vercel Hobby Plan](https://vercel.com/docs/plans/hobby)
- [Limits](https://vercel.com/docs/limits)

---

## 6. External Secrets Source (AWS SSM Parameter Store)

### Verdict: **No native integration — CI sync step required**

| Approach | Supported on Hobby? |
|----------|---------------------|
| Vercel pulls from AWS SSM at build/deploy time | ❌ No |
| Vercel pulls from HashiCorp Vault, Doppler, 1Password, etc. | ❌ No (integrations require Pro/Enterprise) |
| **CI/CD sync (GitHub Actions → Vercel API)** | ✅ **Yes — recommended pattern** |
| `vercel env pull` for local dev | ✅ Yes |

### Recommended Pattern: CI Sync Step

```yaml
# .github/workflows/sync-secrets.yml
name: Sync Secrets to Vercel
on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * *'  # daily
jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # for OIDC to AWS
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/GitHubActions-SSM-Reader
          aws-region: us-east-1
      - name: Fetch secrets from SSM
        id: ssm
        run: |
          # Use AWS CLI to get parameters, output as JSON
          aws ssm get-parameters-by-path --path /finsight/prod/ --recursive --with-decryption \
            --query 'Parameters[*].[Name,Value]' --output text | \
            while read name value; do
              key=$(basename "$name")
              echo "$key=$value" >> $GITHUB_ENV
            done
      - name: Push to Vercel
        run: |
          npx vercel@latest env add DATABASE_URL production --value="$DATABASE_URL" --token=$VERCEL_TOKEN
          # ... repeat for each secret, or use bulk API
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

### Alternative: Vercel OIDC Federation
- Vercel supports **OIDC tokens from GitHub Actions** to assume AWS roles
- Still requires CI step to *write* secrets to Vercel; Vercel cannot *pull* at build time

**References:**
- [Replace static CI keys with OIDC federation](https://vercel.com/i/oidc-federation-ci-tokens)
- [Marketplace Integrations](https://vercel.com/integrations) — External secret sync integrations (Infisical, Doppler, 1Password) require Pro/Enterprise

---

## 7. Preview Deployment Controls: Blocking Production API Calls

### Available on Hobby: **Vercel Authentication (Standard Protection)**

| Protection Scope | Hobby | What It Protects |
|------------------|-------|------------------|
| **Standard Protection** | ✅ | All preview + deployment URLs; **excludes production domains** |
| **All Deployments** | ✅ | **Everything** including production domain (`finsight.sahcreatives.com`) |
| **Password Protection** | ❌ | Pro only ($20/mo/project) |
| **Trusted IPs** | ❌ | Enterprise only |
| **Passport (OIDC/SAML)** | ❌ | Enterprise only |

### How It Works
- **Standard Protection** (recommended): Preview URLs (`<branch>-<project>.vercel.app`) require Vercel login; production custom domain remains public
- **All Deployments**: Even `finsight.sahcreatives.com` requires auth — useful for internal apps
- **Deployment Protection Exceptions**: Allow specific IPs, CIDR ranges, or shareable bypass links for automation/E2E tests

### Isolation Strategy for Phase 2
1. **Use Standard Protection** — previews protected, production public
2. **Scope environment variables correctly:**
   - Production secrets → `target: ["production"]`
   - Preview-safe values (test DB, mock APIs) → `target: ["preview"]`
   - Never share production API keys with preview scope
3. **Use Deployment Protection Exceptions** for:
   - CI/CD running E2E tests against previews
   - Internal tools calling preview APIs
4. **Client-side:** Previews automatically use preview-scoped env vars — cannot accidentally call production APIs if config is correct

### Cannot Do on Hobby
- ❌ Password-protected previews (Pro feature)
- ❌ IP-allowlisted production (Enterprise)
- ❌ Custom OIDC/SAML for previews (Enterprise)

**References:**
- [Deployment Protection](https://vercel.com/docs/deployment-protection)
- [Methods to Protect Deployments](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments)
- [Usage & Pricing for Deployment Protection](https://vercel.com/docs/deployment-protection/usage-and-pricing)

---

## 8. Cost/Usage Tracking on Hobby Tier

### Dashboard (Primary)
- **Usage page** in Vercel dashboard shows:
  - Function invocations, CPU time, memory
  - Bandwidth (Fast Data Transfer, Fast Origin Transfer)
  - Build minutes
  - Edge requests
  - Web Analytics / Speed Insights events
- **Allotment indicator** — shows % of monthly included usage consumed
- **Project/region breakdown** available
- **30-day rolling window** view

### CLI
```bash
vercel billing usage --since 30d --group-by project
```

### REST API
- **Endpoint:** `GET /v2/usage?teamId=<team>&since=30d`
- **On Hobby:** Returns **limited or empty data** (multiple community reports)
- **Rate limit:** 120 requests/minute (owner)
- **Pro/Enterprise:** Full usage breakdown

### Alerts & Spend Management
| Feature | Hobby |
|---------|-------|
| Usage notifications | ✅ Automatic (at 80%, 100% of allotment) |
| Spend Management (pause at threshold) | ❌ Pro only |
| Custom alert thresholds | ❌ Pro only |
| Webhook on threshold | ❌ Pro only |

### Hobby Behavior at Limits
- **Projects paused** when monthly allotment exceeded
- **No overage charges** — hard stop until next cycle or upgrade
- **3-day grace period** for Web Analytics before pause

**References:**
- [Manage and Optimize Usage](https://vercel.com/docs/pricing/manage-and-optimize-usage)
- [Pricing on Vercel](https://vercel.com/docs/pricing)
- [Vercel Hobby Usage Alerts](https://getmonii.com/guides/vercel-hobby-spend-alerts) — confirms API limitation

---

## Summary Matrix for Phase 2 Decision

| Requirement | Hobby Feasibility | Notes |
|-------------|-------------------|-------|
| Apex domain `finsight.sahcreatives.com` + HTTPS | ✅ Full support | 50 domains/project limit |
| Programmatic secret management (CI/CD) | ✅ Full REST API | Encrypted `type: "encrypted"` / `visibility: "secret"` |
| Git push → production deploy | ✅ Native | 100 deploys/day limit |
| PR → preview deploy | ✅ Native | Auto-protected with Standard Protection |
| Manual redeploy after env sync | ✅ Deploy Hooks | 5 hooks, 60/hr rate limit |
| Long-term log retention | ❌ 1 hour only | No Drains on Hobby; need external logging |
| Function duration > 5 min | ❌ Hard limit 300s | Pro: 800s, 1800s beta |
| Concurrent users > 10 | ❌ Hard limit | 11th request fails |
| Pull secrets from AWS SSM at build | ❌ Not supported | CI sync step mandatory |
| Block previews from prod APIs | ✅ Via env scoping + Standard Protection | Previews get separate env scope |
| Cost tracking / alerts | ⚠️ Dashboard only | API returns limited data on Hobby |
| Commercial use | ❌ Non-commercial only | ToS restriction |

---

## Recommendations for Phase 2

1. **Proceed with Hobby** for Phase 2 if:
   - Traffic < 10 concurrent users
   - Functions < 5 min
   - Non-commercial / pre-revenue
   - Can accept 1-hour log retention

2. **Plan Pro upgrade ($20/mo + usage)** when:
   - Need log Drains (Datadog, S3, etc.)
   - Need >10 concurrent executions
   - Need Password Protection on previews
   - Need usage API for automated cost monitoring
   - Commercial launch

3. **Implement CI secret sync** as a GitHub Actions workflow using Vercel REST API — this is the only supported pattern on any tier.

4. **Use Standard Protection** + env scoping (`target: ["preview"]` vs `["production"]`) to isolate preview deployments from production APIs.

---

## References

- [Vercel Hobby Plan](https://vercel.com/docs/plans/hobby)
- [Vercel Limits](https://vercel.com/docs/limits)
- [Vercel REST API](https://vercel.com/docs/rest-api)
- [Environment Variables](https://vercel.com/docs/environment-variables)
- [Deployment Protection](https://vercel.com/docs/deployment-protection)
- [Deploy Hooks](https://vercel.com/docs/deploy-hooks)
- [Runtime Logs](https://vercel.com/docs/logs/runtime)
- [Drains](https://vercel.com/docs/drains)
- [Pricing - Manage and Optimize Usage](https://vercel.com/docs/pricing/manage-and-optimize-usage)
- [Vercel Functions Limitations](https://vercel.com/docs/functions/limitations)
