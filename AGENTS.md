# AGENTS.md

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for `sah-automation/finsight-AI`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.


## Authoritative Documents (Source of Truth)

### Parent Plans (Scope & Architecture)
The following define the scope, architecture, data flows, and requirements for FinSight AI:

- `docs/plans/project_requirement/finsightAI.md` – Project requirements, scope, and milestones
- `docs/plans/architecture/phase1/finsight_mvp_hld.svg` – Phase 1 High-Level Design (architecture, flows, and components)

### Mandatory Policies (Binding Constraints)
The following are binding policies that must be followed for all implementation work:

- `docs/plans/project_requirement/finsight_config_switches.md` – Config switch rules, validation requirements, both-path enforcement, fail-loudly rules, protections that must stay on, and pilot/standard values.
- `CODING_STANDARDS.md` – Coding standards, dependency rules, patterns, testing, and the PR checklist.


## Rules
- **Treat as authoritative:** All of the above are authoritative in their respective domains.
- **Read first:** Before drafting any sub-plan, design, or implementation plan, read `docs/plans/project_requirement/finsightAI.md`, `docs/plans/architecture/phase1/finsight_mvp_hld.svg`, and `docs/plans/project_requirement/finsight_config_switches.md` in full.
- **No deviation from Parent Plans:** Do **not** deviate from `finsightAI.md` or `finsight_mvp_hld.svg`. Only make child-level decisions and concrete implementation details in sub-plans (e.g. `docs/plans/phase1/*`).
- **Diagrams are binding:** Treat `finsight_mvp_hld.svg` as binding. If the diagram shows a component, flow, or integration, follow it. If you need to interpret it, ask rather than guessing.
- **Traceability required:** Any feature, component, or flow added to a child plan must be traceable to either a requirement in `finsightAI.md` or something shown in the Phase 1 HLD. If it cannot be traced, stop and ask.
- **No scope creep:** Do not expand Phase 1 scope. New modules, top-level folders, or major flows require explicit clearance.
- **Config is law:** For all config and feature toggles, `finsight_config_switches.md` is strictly binding. The `core/config` module must enforce every validation rule from it. No hard-coding of switch values is allowed. Both paths of every switch must exist and be tested.
- **Follow coding standards:** Adhere to `CODING_STANDARDS.md` at all times (dependency direction, ports/adapters, company isolation, citations required, numbers from code only, output gate never disabled).
- **Stop and ask for clearance:** If any proposed change, design, or plan would conflict with any authoritative document, that document is authoritative. **Stop and ask for clearance before proceeding.** Do not work around the conflict.
