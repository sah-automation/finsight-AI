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


## Implementation pre-flight (Binding)
Before editing any file, the implementation agent must, in order:

1. **Baseline gate** – run `make preflight` against the clean tree. Stop and escalate on any failure; never paper over a red baseline.
2. **TDD seam first** – write a committed, failing test that exercises the port/adapter (`tests/contract/` or `tests/unit/adapters/`) before creating or editing the implementation. No adapter code lands without a corresponding failing test.
3. **Architecture pre-check** – for each new adapter/entity, confirm the target module name is snake_case of the class name and that the file contains at most one public class. Run `pytest tests/architecture -q` after scaffolding the file, before filling the body.
4. **Small increments** – commit after each coherent green unit (one adapter, one decorator, one validator step), each checked with `make preflight` before proceeding.
5. **No adapter reads env/config directly** – vendor settings come through `_resolve_config`/constructor injection; `os.getenv`/`os.environ` never appears in `domain`, `application`, `adapters`, `entrypoints`, or `composition`.

These are listed so the baseline → TDD → gate sequence is explicit rather than optional.
