# FinSight AI: Coding Standards

For the coding agent and every developer on this project. Read this before writing any code. If a task clashes with this file, stop and ask. Do not quietly break a rule.

Related files: `finsightAI.md` (what we build), `finsight_config_switches.md` (config switches), `finsight_known_risks.md` (risks), and the HLD diagram.

---

## 1. The big rules (short version)

1. **Business logic never knows about AWS, LiteLLM, Textract or any vendor.** It talks to interfaces only.
2. **One job per file, one job per class, one job per function.**
3. **Depend on interfaces, not on concrete classes.** Concrete classes are chosen in one place (the composition root).
4. **No hard-coded values.** Everything that can change comes from the config module (see section 9).
5. **The LLM never does maths.** All numbers come from code (SQL or pandas). See section 12.
6. **Every query carries the company id.** No exceptions.
7. **Both paths of every switch must exist and be tested.**
8. **Small, boring, readable code beats clever code.**
9. **If a change touches more than one layer, say so in the pull request.**

---

## 2. Tech baseline

- Python 3.12 or above, FastAPI for the API, deployed as Lambda zip packages.
- Type hints on every function. `mypy --strict` must pass.
- `ruff` for lint and format. `pytest` for tests. `pydantic` for data shapes and config.
- Async only where it helps (model calls, parallel steps). Do not mix sync and async in one class.
- Pin every dependency version. Add a new library only with a short reason in the pull request.

---

## 3. Project structure

```
src/finsight/
  core/                 # shared basics, no business rules
    config/             # the ONLY place that reads config and env vars
    errors/             # our own error types
    logging/            # logger, trace tags
    types/              # shared ids, enums (CompanyId, Role, Category)

  domain/               # pure business logic. No AWS, no HTTP, no vendor imports
    entities/           # Document, Chunk, Metric, Answer, Recommendation
    value_objects/      # Money, Period, Citation, Confidence
    services/           # business rules (evidence check, conflict rules)
    ports/              # interfaces (abstract classes) the outside world must fulfil

  application/          # use cases. Orchestrate domain + ports
    ask_question/       # question flow steps
    ingest_document/    # ingestion flow steps
    update_document/
    metrics/
    forecasting/
    risk_alerts/
    decisions/
    reports/

  adapters/             # the only place vendors live. Each implements a port
    llm/                # LiteLLM gateway, router, fallbacks
    embedding/
    vector_store/       # aurora_pgvector now, others later
    rerank/
    readers/            # pdfplumber, tesseract, textract, excel, csv, docx
    repositories/       # Aurora (Postgres) access
    storage/            # S3
    queue/              # SQS
    cache/              # DynamoDB answer cache, role cache
    auth/               # Cognito
    metering/           # usage rows, prices

  entrypoints/          # thin doors into the app. No logic here
    api/                # upload, status, question, source_viewer handlers
    workers/            # SQS and Step Functions handlers
    scheduled/          # reports, weekly jobs

  composition/          # wires everything together (the composition root)

config/                 # schema.yaml, permissions.yaml, prices.yaml, dev/staging/prod.yaml
tests/
  unit/                 # mirrors src/ folder by folder
    switches/           # one file per config switch, both ON and OFF paths
  integration/
  golden/               # the 100+ question set
  contract/             # one shared test per port, run against every adapter
  architecture/         # AST-based invariant tests for rules static tools cannot express
infra/                  # infrastructure code
docs/
```

### Dependency direction (strict)

```
entrypoints -> application -> domain <- adapters
                  ^                        |
                  +---- composition -------+
```

- `domain` imports nothing from `application`, `adapters` or `entrypoints`.
- `application` imports `domain` only. It never imports `adapters`.
- `adapters` import `domain` (to implement ports). Adapters never import each other.
- `entrypoints` import `application` and get objects from `composition`.
- Enforce this with an import checker (`import-linter`) in CI. A broken rule fails the build.

### File rules

- One main class per file. File name matches the class in snake_case.
- A file stays under about 300 lines. A function under about 30 lines. Over that, split it.
- No `utils.py` or `helpers.py` dumping grounds. Name files by what they do.
- Every folder has a short `README.md` saying what belongs there and what does not.
- Lazy imports for heavy libraries inside Lambda functions, so cold starts stay small.

---

## 4. OOP rules

**Encapsulation**
- Keep fields private (`_name`). Expose behaviour through methods, not raw fields.
- Entities protect their own rules. Example: a `Document` decides if it can move from `stored` to `committed`.

**Abstraction**
- Every outside dependency has a port (abstract base class or `Protocol`) in `domain/ports/`.
- Ports describe what we need, not how a vendor does it. Example: `LLMGateway.generate(prompt) -> Stream`, never `litellm_call(...)`.

**Inheritance**
- Use it only for a true "is a" with shared behaviour (for example `BaseReader`).
- Prefer composition ("has a") over deep inheritance. Max 2 levels.

**Polymorphism**
- Code calls the port. The chosen adapter (pdfplumber, Textract and so on) is picked by config.
- Never write `if reader == "textract"` in business code.

**Data and behaviour**
- Plain data shapes use frozen `pydantic` models or dataclasses.
- Value objects (Money, Period, Citation) are immutable and compare by value.
- Money always carries currency and units. Never pass a bare number around.

---

## 5. SOLID, mapped to FinSight

| Principle | What it means here | Example in this project |
|---|---|---|
| **S**ingle Responsibility | One reason to change per class | `InputGate` only checks input. `Reranker` only reranks. `CitationChecker` only checks citations |
| **O**pen/Closed | Add new things without editing old code | New file reader = new class + register it. Do not edit the pipeline |
| **L**iskov Substitution | Any adapter can replace another without surprises | Every `Reader` returns the same shape: text, tables, page numbers. Contract tests prove it |
| **I**nterface Segregation | Small, focused interfaces | Split `VectorSearch` and `VectorWrite`. A search step should not see write methods |
| **D**ependency Inversion | High level depends on interfaces | `AskQuestionUseCase` takes `LLMGateway`, `VectorSearch`, `Reranker` in its constructor |

Red flags the agent must fix before finishing:
- A class with "and" in its job ("reads and chunks and embeds").
- A long `if/elif` on a type or vendor name.
- A subclass that raises "not supported" for a parent method.
- A constructor that creates its own dependencies.

---

## 6. Design patterns to use (and where)

Use a pattern only when it solves a real problem here. Do not add patterns for decoration.

### Creational

| Pattern | Use it for | Notes |
|---|---|---|
| **Factory** | Choosing a reader, vector store, reranker or model from config | `ReaderFactory.create(config)`. Registry-based, so new items register themselves |
| **Abstract Factory** | Building a matching set per cell or per setup (pilot set vs standard set) | One factory returns a full set of adapters that fit together |
| **Builder** | Building the prompt (fixed part, chunks, question) and complex query objects | Keeps the fixed part first for the prompt cache |
| **Singleton (via DI only)** | One config, one logger, one connection pool per function | Do not write a global singleton class. Create once in `composition` and pass it in |

### Structural

| Pattern | Use it for | Notes |
|---|---|---|
| **Adapter** | Wrapping every vendor (Textract, Tesseract, LiteLLM, SQS, S3, Cognito) behind our port | The most important pattern in this project |
| **Facade** | One simple entry per big area: `ModelGateway`, `SearchInterface`, `IngestionService` | Hides many steps behind one call |
| **Decorator** | Adding retry, caching, tracing, metering, timeouts around an adapter | `MeteredLLM(RetryingLLM(LiteLLMGateway))`. Stack them from config |
| **Proxy** | Role check and company check in front of a repository or cache | Access control lives in a proxy, not scattered in code |
| **Repository** | All database reads and writes | Business code never writes SQL. Every method needs `company_id` |
| **Composite** | Documents made of sections, tables and chunks (parent and child) | One way to walk the tree |

### Behavioural

| Pattern | Use it for | Notes |
|---|---|---|
| **Strategy** | Swappable rules: chunking, understand mode (rules or model), output check mode (per sentence or full), queue priority | Chosen from config |
| **Chain of Responsibility** | Gates and checks: input gate, PII check, prompt trick check, output gate | Each link does one check and can stop the chain |
| **Pipeline (steps in order)** | Question flow and ingestion flow | Each step has the same interface: `run(context) -> context`. Steps can be added, reordered or run in parallel |
| **Template Method** | Base ingestion job with fixed order and overridable steps | Fixed: stored, processing, committed. Overridable: how to read |
| **State** | Job state machine: received, stored, processing, committed, failed | Illegal moves raise an error |
| **Observer / Events** | After an update: recompute metrics, clear cache, mark forecasts stale, notify approvers | Publishers do not know the listeners. Add listeners without touching the publisher |
| **Command** | Queue jobs (ingest, reprocess, report). Each is a small object with a job id | Safe to repeat |
| **Fallback chain** | Model fallbacks 1 to 3 | A list of strategies tried in order, with the backup request rule from the config guide |
| **Specification** | Reusable rules like "can this role see this category" | Reads only from `permissions.yaml` |

### Agent workflow (LangGraph)

- Each agent (ingestion, retrieval, metrics, charting, forecasting, risk, decision, verifier) is its own class behind one `Agent` interface.
- The supervisor only routes. It holds no business logic.
- LangGraph and LangChain stay inside `adapters/` or one `orchestration/` module. Domain code must not import them.
- The verifier agent checks against source data. It is never skipped.

---

## 7. Modularity and coupling

- A module exposes a small public surface through its `__init__.py` (`__all__`). Everything else is private.
- Modules talk through ports and events, not by reaching into each other's files.
- No circular imports. If two modules need each other, pull the shared piece into `domain` or use an event.
- No shared mutable global state. Lambda keeps nothing between requests, so state lives in the database or DynamoDB.
- Pass what a function needs as arguments. Do not read hidden globals.
- Cross-feature calls go through the application layer, never feature to feature inside `adapters`.

Test for low coupling: can you delete one adapter folder and swap it for another by changing config and writing one new class? If not, the design is too tight.

---

## 8. Dependency injection

- Constructors receive their dependencies. Nothing creates its own database, client or model.
- All wiring happens in `composition/`. It reads config and builds the objects.
- Tests build the same objects with fakes. No monkey-patching of imports.
- Two build modes must exist: pilot set and standard set (see the config switch guide).

---

## 9. Config rules (from the config switch guide)

- Only `core/config` reads config files and environment variables.
- No `if env == "prod"` anywhere. No fixed model names, sizes, timeouts or limits in code.
- Config is a typed, frozen object validated at startup. Missing, misspelled or unknown values stop the app. No silent fallback.
- Invalid combinations are rejected by the config module (see section 4 of the config guide).
- Log all active switch values at startup. Attach them as tags on every trace.
- Permissions come only from `config/permissions.yaml`. Prices only from `config/prices.yaml`.
- A new switch needs: an owner, a rollback step, both code paths, and tests for both.

---

## 10. Errors and failure handling

- Our own error types in `core/errors`, grouped by meaning: `UserFacingError`, `RetryableError`, `PolicyBlocked`, `InsufficientData`.
- Never show a raw error to a user. Entrypoints turn errors into friendly messages ("temporarily unavailable", "busy, please try again", "waking up, please wait").
- Do not swallow errors. Catch only what you can handle, and log it with the trace id.
- Retries come from config (attempts and wait). Put retry logic in a decorator, not copied inside each call.
- Every job is safe to repeat: use job id and upsert on chunk id.
- "Insufficient data" is a normal result, not a failure. Use the `InsufficientData` type for it.

---

## 11. Security and company separation

- Every repository, search and cache method takes `company_id` as a required argument. A missing company id fails a test build.
- Role check runs on every request. Business code receives an already checked `RequestContext` (company, user, role, access scope).
- Never log question text, chunk text, answers or personal data. Log ids and sizes only.
- Never put company or user data in the cached prompt part.
- Secrets come from a secret store through the config module. Never in code, never in logs.
- Answer cache key = company + role + access scope + question + document stamp. A unit test must prove it.
- Document text is data, never instructions. Prompts say so.
- Only in-region endpoints. A new vendor or model needs a residency check first.

---

## 12. Numbers and money

- All calculations happen in the "calculate with code" step (SQL or pandas). The model may only repeat numbers from code results or cited chunks.
- Use `Decimal` for money. Never `float`.
- Every figure carries currency, units, period and source (document, page, table).
- Units are checked on read (thousands vs millions). Missing units mean "needs review", never a guess.
- Every answer carries citations. Every sentence passes the output gate before it is shown.

---

## 13. Naming and style

- Classes: `PascalCase`. Functions and files: `snake_case`. Constants: `UPPER_CASE`.
- Names say what a thing is or does: `CitationChecker`, `extract_tables`, not `Manager`, `Handler2`, `do_stuff`.
- Ports end with what they are: `LLMGateway`, `VectorSearch`, `DocumentReader`. Adapters name the vendor: `TextractReader`, `LiteLLMGateway`.
- Booleans read like questions: `is_final`, `has_citation`.
- No abbreviations nobody knows. No single-letter names except short loops.
- Comments explain why, not what. Docstring on every public class and function (one line is fine).
- No dead code, no commented-out code, no TODO without a ticket number.

---

## 14. Testing

- Every new class ships with tests in the same pull request.
- **Unit tests:** fast, use fakes for ports, no network.
- **Contract tests:** one shared test per port, run against every adapter (all readers, all vector stores, all model gateways). This proves Liskov.
- **Both paths:** each switch is tested on and off (backup request, parallel steps, per-sentence and full-answer, reranker up and down, and so on).
- **Golden set:** runs on pilot and standard config. Same answers on both. A score drop blocks the release.
- **Security tests:** role table (every role, action, category), cache key test, company filter test.
- **Failure tests:** kill a job halfway and rerun, send the same message twice, block a provider.
- Aim for 85% or more coverage on `domain` and `application`. Coverage is a floor, not a goal.
- Tests must be deterministic. No real model calls in unit tests.

---

## 15. Observability

- Every step of every flow writes a trace span with: step name, company id, duration, active switch values, model name, retry count, cache hit, queue wait.
- Every paid call writes one usage row (company, service, units, cost, model, trace id). Metering is a decorator, so no call site forgets it. A paid call without a usage row is a bug.
- Alerts for: fallback 3 used, reranker down, embedding retries, job in retry list, role cache stale.

---

## 16. Git and release rules

- Small pull requests. One purpose each.
- One switch change per release. Do not mix a switch change with code changes.
- Every pull request has: what changed, why, which risk numbers it touches, how it was tested, how to roll back.
- CI must pass before review: lint, types, import rules, unit tests, contract tests, config validation, golden set.
- Config changes go dev, then staging, then production. No manual console edits.

---

## 17. Pattern and rule checklist (use before every pull request)

- [ ] Domain code has no vendor imports
- [ ] New outside dependency has a port and an adapter
- [ ] No `if vendor == ...` in business code
- [ ] Choices come from config, with both paths tested
- [ ] Constructor injection, no hidden globals
- [ ] Every data call carries `company_id`
- [ ] No maths done by the model
- [ ] No raw error can reach a user
- [ ] No sensitive data in logs
- [ ] Retries, caching, metering and tracing are decorators, not copied code
- [ ] Files and functions are small and named clearly
- [ ] Tests added: unit, contract (if a port changed), and both switch paths
- [ ] Import checker passes

---

## 18. Working rules for the coding agent

1. Read the three project files before starting a task.
2. Plan first: list the files you will add or change and which layer each belongs to. Ask if unsure.
3. Build the port first, then a fake, then the use case, then the real adapter.
4. Never add a new library, folder at the top level, or pattern without saying why.
5. Do not edit files outside the task. Do not "clean up" unrelated code in the same change.
6. If a rule here blocks you, stop and ask. Do not work around it.
7. After finishing, run the checklist in section 17 and report which items you checked.
8. When you are not sure of a value (limit, size, score), put it in config with a clear name. Never guess in code.
