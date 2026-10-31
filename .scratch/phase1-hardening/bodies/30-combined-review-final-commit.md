## Parent

Part of #115

## What to build

After all hardening tickets are implemented, run the `/code-review` skill across the combined implementation. Review against the coding standards and the originating spec, fix any gaps or regressions that surface, run the relevant quality gates, and produce the final commit.

## Acceptance criteria

- [ ] A combined Standards + Spec review report is produced.
- [ ] Every finding is fixed or explicitly recorded with a reason.
- [ ] Typecheck, lint, imports, architecture, unit, contract, security, golden, and relevant performance gates pass.
- [ ] The final combined implementation is committed.
- [ ] No existing GitHub issue is closed or modified.
