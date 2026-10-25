# Security Policy

## Supported versions

Security fixes are applied to `main`. This project is pre-1.0 and publishes no
long-term support branches.

| Version | Supported |
| --- | --- |
| `0.1.x` (main) | Yes |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Use GitHub private vulnerability reporting:

<https://github.com/sah-automation/finsight-AI/security/advisories/new>

Include:

- Affected component, file, or dependency.
- Reproduction steps or a proof of concept.
- Impact and any known workaround.
- Whether the issue is already public.

We acknowledge reports within 3 business days and aim to ship a fix or a
mitigation plan within 30 days. We will credit reporters who want credit.

## Dependency and supply-chain policy

- `pip-audit` runs in CI on every push and pull request (`dependency-audit`
  job). Any reported vulnerability fails the build.
- `actions/dependency-review-action` runs on every pull request and fails on
  high or critical severity findings.
- Dependabot opens grouped weekly updates for `uv` and GitHub Actions.
- Waivers are allowed only when the vulnerable code path is not reachable. Add
  `--ignore-vuln <ID>` to the `dependency-audit` job with a comment that
  explains why, and link the tracking issue. Never silently ignore a finding.
- Secrets must come from a secret store through `finsight.core.config`. Local
  placeholders live in `.env.example` and are never real credentials.

## Scope

Reports about the FinSight AI source code, CI workflows, container images, and
local infrastructure in this repository are in scope. Reports about third-party
services (AWS, LiteLLM, Cohere, model providers) should go to the vendor unless
FinSight misuses the service.
