#!/usr/bin/env python3
"""Publish the Phase 1 hardening tickets as sub-issues of #115.

Usage:
    python3 .scratch/phase1-hardening/publish_tickets.py --dry-run
    python3 .scratch/phase1-hardening/publish_tickets.py --publish

The body files are always (re)generated under .scratch/phase1-hardening/bodies/.
Publishing is intentionally explicit: it creates GitHub issues, links them as
sub-issues of #115, and adds native blocking edges.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = 'sah-automation/finsight-AI'
PARENT = 115
ROOT = Path(__file__).resolve().parent
BODIES = ROOT / 'bodies'
PUBLISHED = ROOT / 'published.json'

TICKETS = [
    {
        'n': 1,
        'slug': 'inputgate-typed-seam-security',
        'title': '[H01] InputGate typed seam and executable security coverage',
        'what': (
            'Give the InputGate an explicit typed configuration dependency and a single '
            'documented check entry point. Remove positional/command-object guessing and '
            'undocumented aliases while preserving configurable PII actions and '
            'prompt-injection detection. Replace the skipped prompt-injection placeholder '
            'with executable tests at the InputGate seam covering direct and obfuscated '
            'injection, benign lookalikes, PII mask/block/log, length limits, and '
            'blocked-path errors.'
        ),
        'acceptance': [
            'InputGate accepts a typed config dependency and rejects undocumented positional/alias construction.',
            'One documented check entry point is used by all callers and the result contract is explicit.',
            'The skipped prompt-injection placeholder is removed; no placeholder-only security suite remains.',
            'Tests cover injection allow/block, PII mask/block/log, length limits, and blocked-path error behavior.',
            'Both configured actions (block and allow) are exercised independently.',
            'Binding pre-flight followed; `make typecheck && make lint && pytest tests/architecture tests/unit tests/security -q` is green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 2,
        'slug': 'contracts-model-ports',
        'title': '[H02] Contract suites for LLMGateway and EmbeddingProvider',
        'what': (
            'Add shared contract suites for `LLMGateway` and `EmbeddingProvider` under the '
            'existing contract-test pattern. Run each suite against every concrete adapter '
            'and test double. Cover happy path, provider failure/timeout, empty or invalid '
            'input, company scoping, and compatibility with the metering/tracing decorator '
            'stacks.'
        ),
        'acceptance': [
            'Shared suites exist for both ports and run against every concrete adapter.',
            'The contract matrix and README list both ports and their adapters.',
            'The architecture contract-matrix meta-test covers both ports.',
            'Tests assert external behavior, not private implementation.',
            'Binding pre-flight followed; relevant gates are green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 3,
        'slug': 'contracts-infrastructure-ports',
        'title': '[H03] Contract suites for ObjectStorage, QueuePort, PartitionGateway, and UnitOfWork',
        'what': (
            'Add shared contract suites for `ObjectStorage`, `QueuePort`, and '
            '`PartitionGateway`, and add the missing concrete `UnitOfWork` adapter over the '
            'existing database session plus its shared contract suite. Wire the new adapter '
            'in the composition root. Cover errors, idempotency, company scoping, '
            'commit/rollback, and failure paths.'
        ),
        'acceptance': [
            'Shared suites exist for ObjectStorage, QueuePort, PartitionGateway, and UnitOfWork.',
            'A concrete UnitOfWork adapter implements the port, is wired in composition, and commits/rolls back correctly.',
            'The contract matrix and README list all four ports.',
            'Failure and idempotency paths are covered.',
            'Binding pre-flight followed; relevant gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 4,
        'slug': 'contracts-repository-ports',
        'title': '[H04] Contract suites for repository ports and the AuditLog adapter',
        'what': (
            'Add shared contract suites for `CompanyRepository`, `UserRepository`, '
            '`JobRepository`, and `DocumentTableRepository`, and add the missing concrete '
            '`AuditLog` adapter plus its shared contract suite. Wire the new adapter. Cover '
            'company scoping, isolation, lifecycle transitions, not-found/conflict, and '
            'idempotency.'
        ),
        'acceptance': [
            'Shared suites exist for CompanyRepository, UserRepository, JobRepository, DocumentTableRepository, and AuditLog.',
            'A concrete AuditLog adapter implements the port, is wired, and passes the contract.',
            'The contract matrix and README list all five ports.',
            'Company isolation and not-found/conflict paths are covered.',
            'Binding pre-flight followed; relevant gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 5,
        'slug': 'typed-config-sections',
        'title': '[H05] Typed Phase 1 config sections and split config modules',
        'what': (
            'Replace arbitrary extended config fields with typed, frozen models for database, '
            'traffic, protection, encryption, lambda, models, cache, edge, scale, '
            'answer_check, metering, consistency, and access. Remove the `*_ext` duplication '
            'so each section has one typed owner. Split the config model module into focused '
            'per-section modules while preserving the public config surface and unknown-key '
            'rejection.'
        ),
        'acceptance': [
            'No `Any`-typed extended config section remains.',
            'Every section is frozen and validated; unknown keys still fail loudly.',
            'Config models are split under the documented file-size limit and imports are updated.',
            'All environment profiles load under `make config-check`.',
            'Tests cover each new section and its defaults.',
            'Binding pre-flight followed; architecture and unit gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 6,
        'slug': 'config-switch-validation',
        'title': '[H06] Enforce config-switch validation rules from the guide',
        'what': (
            'Enforce the binding validation rules from the config-switch guide against the '
            'typed config: cross-section combinations, ranges, registration checks, '
            'protected paths, retention rules, model/reader lists, and both-path enforcement. '
            'Extend the switch meta-test so switches outside `SwitchesConfig` also require an '
            'ON and OFF test. Invalid configuration must stop startup with an actionable '
            'message.'
        ),
        'acceptance': [
            'Every implemented rule has a reject test and an accept test.',
            'Invalid combinations stop startup; unknown, missing, or misspelled switches fail loudly.',
            'The switch meta-test covers switches in every typed section and rejects untested paths.',
            'No silent fallback or validation bypass remains.',
            'Binding pre-flight followed; config, architecture, and switch gates green.',
        ],
        'blocked_by': [5],
    },
    {
        'n': 7,
        'slug': 'provider-agnostic-model-config',
        'title': '[H07] Provider-agnostic model config, approved-model list, and D9 profiles',
        'what': (
            'Make provider, model, chain role (answer, cheap, fallback, embedding, rerank), '
            'timeout, and retry selection fully config-driven. Add a config-driven '
            'approved-model list per environment and region; validate every configured model; '
            'enforce exactly three distinct fallbacks per chain and a self-hosted in-region '
            'fallback 3; validate failover conditions and price coverage for every configured '
            'model. Reconcile dev, staging, and production profiles with decision D9 (Gemini '
            'primary and embeddings, Groq cheap, NVIDIA NIM fallback and reranker). Adding '
            'Anthropic, OpenAI, or another approved provider later must require config plus '
            'adapter registration only.'
        ),
        'acceptance': [
            'All model and provider selection comes from typed config; no business or adapter-construction module hardcodes a vendor.',
            'The approved-model list rejects unapproved models and validates region.',
            'Fallback-chain rules and failover conditions are enforced.',
            'Missing price-table entries stop startup.',
            'Profiles reflect D9; a test proves a new approved model can be introduced by config.',
            'Binding pre-flight followed; relevant gates green.',
        ],
        'blocked_by': [5, 6],
    },
    {
        'n': 8,
        'slug': 'composition-adapter-factories',
        'title': '[H08] Composition root: extract adapter and registry factories',
        'what': (
            'Extract adapter factories and reader registries from the composition root into '
            'focused modules. The root should select and assemble; it must not contain '
            'business logic, vendor branching, or construction fallbacks. Preserve '
            'pilot/standard differences as config-only differences and fail loudly when '
            'construction fails.'
        ),
        'acceptance': [
            'Adapter and registry factories live in focused modules; the composition root is materially smaller.',
            'Composition contains no business logic or vendor branching.',
            'Pilot and standard modes differ only by config.',
            'Construction failures propagate instead of returning a partial container.',
            'Composition tests cover wiring, mode selection, and loud failure.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [7],
    },
    {
        'n': 9,
        'slug': 'composition-use-case-builders',
        'title': '[H09] Composition root: extract infrastructure factories and use-case builders',
        'what': (
            'Extract repository, queue, storage, partition, and unit-of-work factories plus '
            'use-case builders from the composition root. Entrypoints should receive '
            'already-wired ask, source-viewer, upload, onboarding, documents, and reprocess '
            'use cases instead of rebuilding dependencies.'
        ),
        'acceptance': [
            'Infrastructure factories and use-case builders are focused modules; the root is assembly only.',
            'Each use case is resolved once and reused by entrypoints.',
            'No business logic or vendor branching remains in composition.',
            'Composition tests cover builder output and reuse.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [8],
    },
    {
        'n': 10,
        'slug': 'ingestion-orchestration-decomposition',
        'title': '[H10] Decompose ingestion orchestration into named steps',
        'what': (
            'Split the ingestion orchestration into named steps with narrow inputs and '
            'outputs. Preserve step ordering, switch behavior, idempotency, DocumentVersion '
            'state transitions, retries/DLQ handling, delta tracking, and version '
            'supersession. Each step must be testable without running the whole pipeline.'
        ),
        'acceptance': [
            'Ingestion orchestration is decomposed into named, independently testable steps.',
            'Step order, switch paths, idempotency, and state transitions are preserved.',
            'Delta tracking, versioning, and retry/DLQ behavior remain covered.',
            'Existing ingestion and golden-fixture tests pass.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 11,
        'slug': 'qa-source-viewer-decomposition',
        'title': '[H11] Decompose Q&A and source-viewer orchestration',
        'what': (
            'Split the Q&A and source-viewer orchestration into named steps with narrow inputs '
            'and outputs. Preserve input-gate ordering, cache and waiting-line behavior, '
            'retrieval/rerank/calculation/evidence/generation/output-gate/streaming order, '
            'citation locator minting, source authorization/fetch, and non-leaking '
            'unavailable/denied responses.'
        ),
        'acceptance': [
            'Ask and source-viewer flows are decomposed into named, testable steps.',
            'Gate ordering, switch paths, citation behavior, and streaming remain unchanged.',
            'Source-viewer authorization covers allowed, denied, missing, removed, and newer-version cases.',
            'No sensitive text enters logs or traces.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [1],
    },
    {
        'n': 12,
        'slug': 'lifecycle-orchestration-decomposition',
        'title': '[H12] Decompose update, delete, reprocess, and onboarding orchestration',
        'what': (
            'Split update, delete, reprocess, and onboarding orchestration into named steps. '
            'Preserve delta updates, supersession, soft delete and purge, rolling reprocess '
            'with atomic commit, onboarding idempotency, and partition readiness checks.'
        ),
        'acceptance': [
            'Each flow is decomposed into named, testable steps.',
            'Idempotency, atomicity, retention, and state transitions are preserved.',
            'Switch paths remain tested.',
            'Existing application and integration tests pass.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 13,
        'slug': 'reader-adapters-decomposition',
        'title': '[H13] Decompose oversized reader adapters',
        'what': (
            'Split the oversized reader adapters into under-limit modules while preserving the '
            'common reader return shape, page routing, table/layout handling, scan-reader '
            'rejection behavior, and every supported file format.'
        ),
        'acceptance': [
            'Each reader module is under the documented file and function limits.',
            'One public reader class per file and filename matches the class.',
            'Reader contract and unit tests remain green.',
            'Reader, scan-reader, and table-reader switch paths remain covered.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 14,
        'slug': 'repository-vector-partition-decomposition',
        'title': '[H14] Decompose oversized repository, vector-store, and partition adapters',
        'what': (
            'Split the oversized repository, Aurora vector-store, and partition adapters into '
            'under-limit modules while preserving company scoping/RLS, transaction handling, '
            'lifecycle queries, vector search/write behavior, and partition operations.'
        ),
        'acceptance': [
            'Each module is under the documented size limits.',
            'Repository and vector contract suites pass unchanged.',
            'Company isolation and transaction behavior remain tested.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [4],
    },
    {
        'n': 15,
        'slug': 'infra-adapters-decomposition',
        'title': '[H15] Decompose oversized storage, queue, cache, security, and tracing adapters',
        'what': (
            'Split the oversized S3 storage, SQS queue, answer/job-progress cache, '
            'virus-scanner, and tracing adapters while preserving idempotency, retries/DLQ, '
            'cache-key company isolation, redaction, and span behavior.'
        ),
        'acceptance': [
            'Each module is under the documented size limits.',
            'Storage, queue, cache, scanner, and tracing behavior remains covered.',
            "Cache keys and traces cannot leak another Company's data.",
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [2, 3],
    },
    {
        'n': 16,
        'slug': 'model-adapters-decomposition',
        'title': '[H16] Decompose oversized LLM, embedding, rerank, and metering adapters',
        'what': (
            'Split the oversized LLM gateway, embedding, rerank, and metering adapters and '
            'decorator stacks while preserving decorator order (tracing → metering → retry → '
            'provider), streaming, retry behavior, and price-derived usage records.'
        ),
        'acceptance': [
            'Each module is under the documented size limits.',
            'Model-port and metering contract suites pass.',
            'Decorator order, streaming, retries, and usage rows remain tested.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [2],
    },
    {
        'n': 17,
        'slug': 'api-entrypoints-decomposition',
        'title': '[H17] Decompose oversized API entrypoints',
        'what': (
            'Split the oversized API entrypoints into thin handlers that delegate to '
            'application use cases. Preserve authentication/authorization, request '
            'validation, error mapping, streaming, and the published OpenAPI contract.'
        ),
        'acceptance': [
            'Each entrypoint module is under the documented size limits.',
            'Handlers contain no business logic.',
            'API/OpenAPI tests and authorization behavior remain unchanged.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 18,
        'slug': 'domain-core-decomposition',
        'title': '[H18] Decompose oversized domain and core modules',
        'what': (
            'Split the oversized domain and core modules (DocumentVersion, calculator, '
            'evidence checker, output gate, citation locator, residual config modules) into '
            'under-limit modules while preserving behavior, invariants, and dependency '
            'direction.'
        ),
        'acceptance': [
            'Each module is under the documented size limits.',
            'Domain and core tests remain green without behavior changes.',
            'No vendor, config, or environment reads are introduced.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [5],
    },
    {
        'n': 19,
        'slug': 'async-modernization',
        'title': '[H19] Modernize deprecated async event-loop usage',
        'what': (
            'Remove deprecated `asyncio.get_event_loop` access from library, adapter, and '
            'entrypoint code. Use explicit async execution or one documented compatibility '
            'helper; do not mix sync and async behavior inside one class. Add a regression '
            'test that prevents the deprecated pattern from returning.'
        ),
        'acceptance': [
            'No deprecated event-loop access remains in source code.',
            'Async paths run cleanly on Python 3.12+ without deprecation warnings.',
            'A regression test fails if the deprecated pattern returns.',
            'No class mixes sync and async behavior.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [10, 11, 15, 16, 17],
    },
    {
        'n': 20,
        'slug': 'alias-cleanup-public-surfaces',
        'title': '[H20] Alias cleanup and intentional public surfaces',
        'what': (
            'Clean up alias-module sprawl. Inventory compatibility shims, choose one canonical '
            'module per concept, add intentional `__all__` exports, migrate imports, and remove '
            'aliases. Any alias retained for compatibility must document the reason and the '
            'removal condition. Run as expand → migrate imports → contract so every batch '
            'stays green.'
        ),
        'acceptance': [
            'A reviewed alias inventory is committed with canonical module choices.',
            'Each concept has one obvious import location; undocumented shims are removed.',
            'Retained aliases document reason and removal condition.',
            'Package initializers expose intentional public surfaces only.',
            'Import contracts and tests remain green.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    },
    {
        'n': 21,
        'slug': 'size-gate-enforcement',
        'title': '[H21] Flip the file and function size gate to failing',
        'what': (
            'Turn the documented file and function size checks into failing architecture tests '
            '(files over 300 lines, functions over 30 lines). Complete the full refactor first; '
            'the exception list may contain only legitimate, reviewed data/config modules, '
            'each with a reason, owner, and removal condition. Update the generated standards '
            'report.'
        ),
        'acceptance': [
            'The architecture gate fails on an oversized file or function.',
            'Every exception is justified and listed with reason, owner, and removal condition.',
            'No oversized module is silently exempt.',
            'The standards report reflects the failing gate and current exceptions.',
            'Binding pre-flight followed; full architecture gate green.',
        ],
        'blocked_by': [6, 20],
    },
    {
        'n': 22,
        'slug': 'metering-enforcement',
        'title': '[H22] Enforce metering for every paid call site',
        'what': (
            'Add a CI or architecture check that every paid call site (LLM, embedding, rerank, '
            'extraction/OCR) is wrapped by the metering decorator or records an equivalent '
            'usage row. Fix any unmetered site. Use a test double to prove a paid call produces '
            'one usage row with company, service, model, units, cost, and trace identifier.'
        ),
        'acceptance': [
            'The paid-call inventory is checked automatically.',
            'An unmetered paid call fails the gate.',
            'A test double proves the required usage-row fields.',
            'Metering failures remain non-fatal to the user answer.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [2, 9, 16],
    },
    {
        'n': 23,
        'slug': 'tracing-alerts-coverage',
        'title': '[H23] Verify tracing span attributes and alert mapping coverage',
        'what': (
            'Verify and cover the standard tracing span attributes: step, company, duration, '
            'active switch values, model name, retry count, cache hit, and queue wait. Prove '
            'redaction of question text, chunk text, answers, PII, credentials, and signed '
            'URLs. Confirm the five alert mappings (fallback 3, reranker down, embedding '
            'retries, retry-list job, stale role cache) exist in infrastructure and are '
            'snapshot- or test-covered.'
        ),
        'acceptance': [
            'Standard span attributes are emitted by the shared tracing decorators.',
            'Sensitive fields never appear in spans or logs.',
            'All five alert mappings are present and covered by tests or snapshots.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [9, 15],
    },
    {
        'n': 24,
        'slug': 'coverage-ratchet-1',
        'title': '[H24] Coverage ratchet I: global floor 24 → 50',
        'what': (
            'Add targeted behavioral tests for the lowest-covered config, InputGate, and '
            'ingestion paths, then raise the enforced global coverage floor from 24 to 50 in '
            'one reviewed step. Coverage is a floor; tests must assert behavior, not just '
            'execute lines.'
        ),
        'acceptance': [
            'Targeted tests cover config validation, InputGate behavior, and ingestion steps.',
            'The global coverage floor is raised to 50 in `pyproject.toml` and `Makefile`.',
            'The quality-standards document records the ratchet.',
            'Coverage gate passes without exclusions that hide adapters.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [1, 5, 6, 10],
    },
    {
        'n': 25,
        'slug': 'coverage-ratchet-2',
        'title': '[H25] Coverage ratchet II: domain/application toward 85%',
        'what': (
            'Add targeted behavioral tests for Q&A orchestration, source viewer, metering, and '
            'tracing, then ratchet domain and application coverage toward 85% in reviewed '
            "steps. Keep the global floor at or above the previous ticket's level."
        ),
        'acceptance': [
            'Q&A, source-viewer, metering, and tracing behavior is covered.',
            'Domain and application coverage floors are raised in reviewed steps toward 85%.',
            'The ratchet is recorded in the quality-standards document.',
            'Coverage gate passes.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [11, 16, 22, 23, 24],
    },
    {
        'n': 26,
        'slug': 'migration-round-trip',
        'title': '[H26] Migration round-trip against a test database',
        'what': (
            'Exercise the migration chain against a test database: upgrade → downgrade → '
            'upgrade, including Company partitions and vector indexes. Keep the test '
            'integration-only where real services are unavailable and document the checks '
            'that must pass in staging/CI.'
        ),
        'acceptance': [
            'Upgrade → downgrade → upgrade passes against the test database.',
            'Company partitions and vector indexes are created and recreated correctly.',
            'Integration-only portions are documented for staging/CI.',
            'Migration test is wired into the appropriate CI lane.',
            'Binding pre-flight followed; relevant gates green.',
        ],
        'blocked_by': [],
    },
    {
        'n': 27,
        'slug': 'cross-company-isolation',
        'title': '[H27] Cross-Company isolation end-to-end',
        'what': (
            'Add end-to-end cross-Company isolation coverage across every endpoint and data '
            "path. Prove a Company cannot read another Company's Documents, Chunks, Answers, "
            'Citations, cache entries, metering rows, traces, queue payloads, or repository '
            'rows. Deny by default.'
        ),
        'acceptance': [
            'Each relevant endpoint is exercised for Company A versus Company B.',
            'Data paths cover Documents, Chunks, Answers, Citations, caches, metering, tracing, queue, and repositories.',
            'Denied access does not leak existence or content.',
            'Isolation tests run in the appropriate unit or integration lane.',
            'Binding pre-flight followed; gates green.',
        ],
        'blocked_by': [4, 14, 17, 18],
    },
    {
        'n': 28,
        'slug': 'sample-documents-golden-gate',
        'title': '[H28] Real sample Document ingestion and golden-set release gate',
        'what': (
            'Ingest real sample Documents across PDF, scanned PDF, Excel, CSV, and DOCX, then '
            'query them and verify fully populated Citations. Run the golden question set '
            'through the real ask flow for pilot and standard configurations and keep it as a '
            'release gate.'
        ),
        'acceptance': [
            'All five sample formats ingest successfully.',
            'Queries return Answers with valid, company-scoped Citations for each format.',
            'Golden set runs through the real ask flow for pilot and standard.',
            'The golden score remains a release gate.',
            'Integration/staging-only portions are documented.',
            'Binding pre-flight followed; relevant gates green.',
        ],
        'blocked_by': [7, 10, 26],
    },
    {
        'n': 29,
        'slug': 'documentation-reconciliation',
        'title': '[H29] Documentation reconciliation',
        'what': (
            'Reconcile the Phase 1 plan checkboxes, recorded decisions, config-switch '
            'references, and issue-tracker notes with the implemented hardening work. Do not '
            'close, move, or retriage any existing issue; the maintainer will do that later.'
        ),
        'acceptance': [
            'Phase 1 plan checkboxes and recorded decisions match implementation.',
            'Config-switch references and profiles match the current config surface.',
            'Issue notes link to the hardening tickets without closing or modifying existing issues.',
            'Documentation checks are green.',
            'Binding pre-flight followed; docs gate green.',
        ],
        'blocked_by': [21, 25, 27, 28],
    },
    {
        'n': 30,
        'slug': 'combined-review-final-commit',
        'title': '[H30] Combined /code-review and final commit',
        'what': (
            'After all hardening tickets are implemented, run the `/code-review` skill across '
            'the combined implementation. Review against the coding standards and the '
            'originating spec, fix any gaps or regressions that surface, run the relevant '
            'quality gates, and produce the final commit.'
        ),
        'acceptance': [
            'A combined Standards + Spec review report is produced.',
            'Every finding is fixed or explicitly recorded with a reason.',
            'Typecheck, lint, imports, architecture, unit, contract, security, golden, and relevant performance gates pass.',
            'The final combined implementation is committed.',
            'No existing GitHub issue is closed or modified.',
        ],
        'blocked_by': [29],
    },
]


def body_for(ticket: dict) -> str:
    lines = [
        '## Parent',
        '',
        f'Part of #{PARENT}',
        '',
        '## What to build',
        '',
        ticket['what'],
        '',
        '## Acceptance criteria',
        '',
    ]
    lines.extend(f'- [ ] {item}' for item in ticket['acceptance'])
    lines.append('')
    return '\n'.join(lines)


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(
            f'Command failed ({result.returncode}): {" ".join(cmd)}\n'
            f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
        )
    return result


def create_body_files() -> None:
    BODIES.mkdir(parents=True, exist_ok=True)
    for ticket in TICKETS:
        path = BODIES / f'{ticket["n"]:02d}-{ticket["slug"]}.md'
        path.write_text(body_for(ticket), encoding='utf-8')


def load_published() -> dict[int, int]:
    if not PUBLISHED.exists():
        return {}
    raw = json.loads(PUBLISHED.read_text(encoding='utf-8'))
    return {int(key): value for key, value in raw.items()}


def save_published(mapping: dict[int, int]) -> None:
    PUBLISHED.write_text(
        json.dumps({str(key): value for key, value in sorted(mapping.items())}, indent=2),
        encoding='utf-8',
    )


def publish() -> None:
    create_body_files()
    published = load_published()

    for ticket in TICKETS:
        n = ticket['n']
        if n in published:
            print(f'skip #{n}: already published as #{published[n]}')
            continue

        body_path = BODIES / f'{n:02d}-{ticket["slug"]}.md'
        result = run(
            [
                'gh',
                'issue',
                'create',
                '--repo',
                REPO,
                '--title',
                ticket['title'],
                '--body-file',
                str(body_path),
                '--label',
                'ready-for-agent',
            ]
        )
        match = re.search(r'/issues/(\d+)\s*$', result.stdout.strip())
        if not match:
            raise SystemExit(f'Could not parse issue number from: {result.stdout!r}')
        number = int(match.group(1))
        published[n] = number
        save_published(published)
        print(f'created H{n:02d} -> #{number}')

    # Link every ticket as a sub-issue of the parent in a separate pass so an
    # interrupted run can resume without losing the links.
    for ticket in TICKETS:
        n = ticket['n']
        number = published[n]
        result = run(
            [
                'gh',
                'issue',
                'edit',
                str(PARENT),
                '--repo',
                REPO,
                '--add-sub-issue',
                str(number),
            ],
            check=False,
        )
        if result.returncode != 0:
            print(f'  warn: could not link #{number} as a sub-issue of #{PARENT}')

    # Dependencies are added in a second pass so every blocker has a real number.
    for ticket in TICKETS:
        n = ticket['n']
        child = published[n]
        for blocker_n in ticket['blocked_by']:
            blocker = published[blocker_n]
            result = run(
                [
                    'gh',
                    'issue',
                    'edit',
                    str(child),
                    '--repo',
                    REPO,
                    '--add-blocked-by',
                    str(blocker),
                ],
                check=False,
            )
            if result.returncode == 0:
                print(f'  blocked_by: #{child} <- #{blocker}')
                continue

            # REST fallback using the blocker's database id.
            db_id = run(
                ['gh', 'api', f'repos/{REPO}/issues/{blocker}', '--jq', '.id']
            ).stdout.strip()
            result = run(
                [
                    'gh',
                    'api',
                    '--method',
                    'POST',
                    f'repos/{REPO}/issues/{child}/dependencies/blocked_by',
                    '-F',
                    f'issue_id={db_id}',
                ],
                check=False,
            )
            if result.returncode == 0:
                print(f'  blocked_by (REST): #{child} <- #{blocker}')
                continue

            # Fallback for repos without native issue dependencies.
            print(f'  native dependency unavailable for #{child} <- #{blocker}; using body text')
            body_path = BODIES / f'{n:02d}-{ticket["slug"]}.md'
            text = body_path.read_text(encoding='utf-8')
            if '## Blocked by' not in text:
                text = text.rstrip() + '\n\n## Blocked by\n\n'
            else:
                text = text.rstrip() + '\n'
            text += f'- #{blocker}\n'
            body_path.write_text(text, encoding='utf-8')
            run(
                [
                    'gh',
                    'issue',
                    'edit',
                    str(child),
                    '--repo',
                    REPO,
                    '--body-file',
                    str(body_path),
                ]
            )

    print('\nPublished tickets:')
    for ticket in TICKETS:
        blockers = ', '.join(f'#{published[b]}' for b in ticket['blocked_by']) or 'none'
        print(f'  H{ticket["n"]:02d} #{published[ticket["n"]]}  blocked by: {blockers}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.publish and not args.dry_run:
        parser.error('choose --dry-run or --publish')

    create_body_files()
    print(f'Wrote {len(TICKETS)} ticket bodies to {BODIES}')
    if args.dry_run:
        for ticket in TICKETS:
            blockers = ', '.join(f'H{b:02d}' for b in ticket['blocked_by']) or 'none'
            print(f'  H{ticket["n"]:02d} {ticket["title"]}  [blocked by: {blockers}]')
        return

    publish()


if __name__ == '__main__':
    main()
