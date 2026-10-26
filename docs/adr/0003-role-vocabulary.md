# ADR-0003: Use the four business roles as the role vocabulary

## Status

Accepted

## Context

The repository used three incompatible role vocabularies:

- `admin`, `analyst`, `viewer`, `approver` in the `Role` enum,
  `config/permissions.yaml`, and the security tests;
- `admin`, `finance_manager`, `analyst`, `viewer` in the initial migration's
  `users.role` check and the older requirement documents;
- `executive_leadership`, `corporate_finance_planners`, `audit_compliance`,
  `system_admin` in the config switch guide (5.29) and the known-risks review
  (risk 24).

Only `admin` was common to all three. A stored `approver` would pass the enum
but fail the database check, and a stored `finance_manager` would pass the
database but fail `RequestContext` validation. The security tests compared only
the YAML matrix with the enum, so they stayed green while the migration and the
requirement document disagreed.

The newer business roles also encode different semantics: Executive Leadership
approves decisions, Corporate Finance & Planners creates and uploads, Audit &
Compliance is read-only across all categories, and System Admin manages settings
without access to financial content. Renaming `approver` to `finance_manager`
would have made the wrong role responsible for approvals.

## Decision

Use the four business role IDs from the config switch guide (5.29) everywhere:

- `executive_leadership`
- `corporate_finance_planners`
- `audit_compliance`
- `system_admin`

Retire `admin`, `analyst`, `viewer`, `approver`, and `finance_manager`. No
aliases or mappings are kept, because no production data exists.

`config/permissions.yaml` holds the role/action/category matrix. Every role
lists every category explicitly. There is no default fallback: an unknown role
is denied. `delete` is not granted to any pilot role until a retention policy
exists. System Admin uses `configure` on content categories because there is no
separate settings category, and never gets `read` on financial content.

This ADR settles the vocabulary only. `config/permissions.yaml` still has no
runtime consumer, so issue #11 remains open for wiring or retiring it.

## Consequences

- The `Role` enum, the permission matrix, the `users.role` check, the security
  tests, and `GLOSSARY.md` use one vocabulary.
- The initial migration was edited in place because the project has no deployed
  environment. If a local database already applied the old migration, recreate
  it.
- The security tests now assert every role/action/category pair and parse the
  latest migration's role check, so enum and database drift fails the build.
- Cognito groups and the future RBAC loader must use these IDs. The loader still
  needs to validate that every configured role has a complete matrix before
  startup.
