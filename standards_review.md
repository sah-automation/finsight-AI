# Standards Review — Diff Analysis

## Hard Violations (Documented Standard Breaches)

### 1. Undocumented Config Switch: `detailed_tracing_enabled`
**Files:** `src/finsight/composition/container.py` (lines 1707–1735), `src/finsight/adapters/tracing/__init__.py`
**Standard:** `docs/plans/project_requirement/finsight_config_switches.md` §1 rules 1, 3, 10 — "Every switch must be read from config. Both paths must exist. Every switch has an owner, a rollback step and a test."
**Issue:** The diff introduces a new switch `detailed_tracing_enabled` that selects between `TracingAdapter` and `DisabledTracer`. This switch is **not documented** in the config switch guide (no pilot/standard values, no code rules, no rollback, no validation rule in §4). The guide requires every switch to be listed in §5 with full metadata. Without documentation, the switch cannot be validated, rolled back, or reviewed per the release rules (one switch change per release).

### 2. Config Access via Raw Dict/Getattr (Violates "One Place to Read")
**File:** `src/finsight/composition/container.py` lines 1710–1723
**Standard:** `finsight_config_switches.md` §1 rule 2 — "Code reads switches only through one config module. No direct environment variable reads anywhere else." / `CODING_STANDARDS.md` §9 — "Only `core/config` reads config files and environment variables."
**Issue:** The container reaches into `config` with `isinstance(config, Mapping)` / `getattr(config, 'switches', None)` / `switches.get('detailed_tracing_enabled', True)`. This bypasses the typed config module. The config should expose `detailed_tracing_enabled` as a validated attribute on a frozen config object; the container should call `config.switches.detailed_tracing_enabled` (or similar). Raw dict access defeats validation (§4 rules) and makes the switch invisible to startup logging (§1 rule 8).

### 3. Missing Validation Rule for New Switch
**File:** `docs/plans/project_requirement/finsight_config_switches.md` §4 (validation rules table)
**Standard:** `finsight_config_switches.md` §1 rule 4 — "If a switch is missing, misspelled, or has an unknown value, the app must refuse to start."
**Issue:** No validation rule exists for `detailed_tracing_enabled` (type, allowed values, interaction with other switches). The container defaults to `True` silently if the switch is missing — a silent fallback, which rule 4 forbids.

---

## Judgement Calls (Baseline Smells)

| Smell | Location | Evidence |
|-------|----------|----------|
| **Primitive Obsession** | `container.py:1710–1723` | Raw `Mapping`/`getattr`/`dict.get` chain instead of a typed `Switches` model. |
| **Message Chains** | `container.py:1719–1722` | `config.get('switches')` → `switches.get('detailed_tracing_enabled')` — two hops through untyped dicts. |
| **Duplicated Code (Signature Mirroring)** | `disabled_tracer.py:37–52, 112–142` | `start_span` duplicates the port's 13-parameter signature verbatim (13 params × 2 methods). The port itself is flagged as an exception (`OVERSIZED_FUNCTION_EXCEPTIONS`) with removal condition "Split span configuration object in port." The adapter mirrors the bloat rather than solving it. |
| **Speculative Generality** | `disabled_tracer.py:160–162` | Four aliases (`InactiveTracer`, `MinimalTracer`, `NoOpTracer` = `DisabledTracer`) with no distinct behaviour. YAGNI unless callers need different names for clarity — no evidence in diff. |
| **Data Clumps** | `disabled_tracer.py:37–52` | 13 loose parameters (`name`, `span_name`, `trace_id`, `attributes`, `metadata`, `active`, `enabled`, `mode`, `minimal`, `**kwargs`) that form a conceptual "span config" object. The port exception notes this; the adapter inherits it. |
| **Large Function** | `disabled_tracer.py:112–142` | `start_span` is 31 lines (exception registered). The body does attribute merging, name resolution, span creation, company attribute injection, and list append — multiple responsibilities. |
| **Mysterious Name** | `container.py:1713` | Variable `Cls` — upper-case abbreviation for "class". `CODING_STANDARDS.md` §13: "No abbreviations nobody knows." Use `adapter_class` or `tracer_class`. |

---

## Compliant / Positive Notes
- New adapter lives in `adapters/tracing/` (correct layer).
- Implements `TracingPort` — respects Dependency Inversion.
- Contract tests (`test_tracing_contract.py`) cover both implementations — satisfies "both paths tested" (switch guide rule 3).
- Oversized-function exception for `disabled_tracer.py::start_span` includes required `reason`, `owner`, `removal_condition` fields — follows `test_invariants.py` exception protocol.
- No vendor imports in domain/application (architecture invariant passes).
- No `os.getenv`/`os.environ` in new adapter (architecture invariant passes).
- File naming: `disabled_tracer.py` matches class `DisabledTracer` (snake_case rule).

---

## Required Fixes Before Merge
1. Add `detailed_tracing_enabled` to `finsight_config_switches.md` §3 (pilot/standard values), §4 (validation rule), §5 (full switch reference with owner, rollback, code rules).
2. Move switch reading into the typed config module (`core/config`); expose as validated attribute; remove raw dict/getattr logic from `container.py`.
3. Make the switch fail-loudly if missing/unknown (remove silent `True` default).
4. Consider collapsing the four aliases in `disabled_tracer.py` unless a concrete use case exists.
5. Rename `Cls` → `tracer_class` in `container.py`.
