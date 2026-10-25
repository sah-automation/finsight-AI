# AGENTS.md

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for `sah-automation/finsight-AI`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Coding standards

Before writing or changing any code, read `CODING_STANDARDS.md` in the project root and strictly follow it.
- Plan first: list the files you will add or change and the layer each one belongs to.
- Follow the folder structure and the import direction rules.
- Use the interfaces, patterns and config rules from that file.
- Before you finish, run the checklist in section 17 and report which items you checked.
- If a task clashes with a rule, stop and ask. Do not work around it.
