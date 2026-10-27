# AGENTS.md

## Agent skills

### Issue tracker
Issues and specs live in GitHub Issues for `sah-automation/finsight-AI`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels
The five canonical triage roles use their default label strings. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.


### Mandatory Policies (Binding Constraints)
The following are binding policies that must be followed for all implementation work:

- `docs/plans/project_requirement/finsight_config_switches.md` – Config switch rules, validation requirements, both-path enforcement, fail-loudly rules, protections that must stay on, and pilot/standard values.
- `CODING_STANDARDS.md` – Coding standards, dependency rules, patterns, testing, and the PR checklist.


## Rules
- **Follow Plan and Architecture:** Strictly follow required project plans and architectures at /docs/plans/ folder. Stop and escalate if any conflict found or needs clarifications.
