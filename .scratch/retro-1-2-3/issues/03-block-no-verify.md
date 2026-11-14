# 03: Block `git commit --no-verify` in git guardrails

**What to build:** The git guardrails hook (installed via the `git-guardrails-claude-code` skill or directly in `.git/hooks/pre-commit`) should reject commits that use `--no-verify`. This prevents agents from bypassing the pre-commit gate after tickets 01 and 02 fix the underlying conflict.

**Blocked by:** #215 (ticket 01) — (the gate must pass cleanly first; otherwise blocking --no-verify just breaks commits)

**Status:** ready-for-agent

- [ ] `.git/hooks/pre-commit` (or the skill that generates it) checks for `--no-verify` in the commit command
- [ ] Attempting `git commit --no-verify` fails with a clear message (e.g., "Use `make ratchet` to update standards_report.md, then commit normally")
- [ ] Normal `git commit` (without --no-verify) works on a clean tree
- [ ] The hook does not interfere with other git operations (reset, checkout, etc.)
