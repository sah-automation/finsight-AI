# 10: Review all 9 fixes and commit

**What to build:** Once tickets 01–09 are complete (GitHub issues #215–#222, #214), run the `code-review` skill (standards axis + spec axis) against the full diff. Any gaps, regressions, or new violations found by the review must be fixed before committing. The final commit should follow conventional commits format and pass the complete pre-commit gate without `--no-verify`.

**Blocked by:** #214 (make sizes), #215 (compare-only report), #216 (gate exception freshness), #217 (variadic check), #218 (step pairing), #219 (remove ignores), #220 (ratchet target), #221 (block no-verify), #222 (private size + docstring)

**Status:** ready-for-agent

- [ ] All 9 tickets merged into a single working tree (or on a feature branch)
- [ ] `make check` (lint + typecheck + imports + vulture + secrets + tests + security) passes
- [ ] `git commit` without `--no-verify` succeeds (pre-commit hook passes)
- [ ] Code review (both standards and spec axes) has zero hard violations
- [ ] Commit follows conventional commits
- [ ] Commit is NOT made with `--no-verify`
