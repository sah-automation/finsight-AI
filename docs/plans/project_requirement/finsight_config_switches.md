# FinSight AI MVP: Config Switch Guide

This guide covers the five low-cost choices we use during the pilot, the AI model swap, three traffic protection choices, nine speed choices, four scale and resilience choices, and seven design choices. Each one must be a switch in config, so we can go back to the standard setup or change providers without redesign.

The switches:
1. Aurora pauses when idle
2. WAF off
3. AWS-managed keys
4. Free document readers
5. Lambda SnapStart off
6. AI model swap (answer and embedding models)
7. Connection limits (concurrency cap and pool size)
8. RDS Proxy (shares database connections across functions)
9. Standby reader (second database copy)
10. Slow model protection (first word timeout and backup request)
11. Parallel steps
12. Question understanding mode
13. Rerank size
14. Prompt cache
15. Answer cache
16. Output check mode
17. Provisioned concurrency (question function only)
18. Sign-in speed (role check cache and refresh tokens)
19. Embedding retry
20. Cells and vector store
21. Fair share limits
22. Spike queue (priority and wait)
23. Chunking and parsing
24. Rerank model and evidence score
25. Document categories and updates
26. Cost metering
27. Consistency settings (ACID and BASE)
28. Answer retry
29. Roles and permissions

---

## 1. Strict rules (no exceptions)

1. **No hard-coding.** Every switch below must be read from config. Never write "if prod" or a fixed value in code.
2. **One place to read.** Code reads switches only through one config module. No direct environment variable reads anywhere else.
3. **Both paths must exist.** The cheap path and the standard path must both be written and tested. A switch with only one path is not a switch.
4. **Fail loudly.** If a switch is missing, misspelled, or has an unknown value, the app must refuse to start. Never fall back silently.
5. **Validate combinations.** The config module must reject invalid combinations (see section 4).
6. **Change by pull request only.** Every switch change needs a review and goes dev, then staging, then production. No manual edits in the AWS console.
7. **One change per release.** Do not change a switch and ship code in the same release. Speed and scale switches also ship one at a time, so a score drop can be traced to one change.
8. **Make it visible.** Log all active switch values at startup and attach them as tags on every trace.
9. **Protection stays on.** The items in section 8 can never be switched off.
10. **Every switch has an owner, a rollback step and a test.** If one is missing, the switch is not ready.
11. **Speed never beats quality.** A speed switch is blocked if the golden set score drops. Speed work may remove waiting, but it may not remove a check or weaken an answer.

---

## 2. File layout

```
config/
  schema.yaml        # allowed values and rules (single source of truth)
  permissions.yaml   # role x action x document category (see 5.29)
  prices.yaml        # price per model and service, used by cost metering (see 5.26)
  dev.yaml
  staging.yaml       # if staging available
  prod.yaml
```

Infrastructure code and the Lambda code both read the same file for their environment.

---

## 3. Pilot config (starting values)

```yaml
environment: prod

database:
  engine: aurora_postgres
  min_capacity_acu: 0          # 0 = pauses when idle, 0.5 = always on
  auto_pause_minutes: 30
  connect_retry_attempts: 5
  connect_retry_wait_seconds: 5
  show_waking_message: true
  rds_proxy_enabled: false     # true sends all database calls through RDS Proxy
  rds_proxy_max_connections_percent: 80
  standby_reader_enabled: false  # true adds a second database copy in another zone

traffic:
  lambda_reserved_concurrency: 20    # max functions running at once
  ingestion_max_concurrency: 4       # part of the number above. Upload work can never use more than this
  db_connections_per_request: 3      # connections one question uses (search, numbers, history)
  db_pool_size_per_function: 3       # connections each function keeps. Must be at least the line above when parallel_steps is true
  db_pool_timeout_seconds: 10        # wait time before showing the "busy" message
  aurora_max_capacity_acu: 4         # ceiling so cost cannot run away

protection:
  waf_enabled: false           # true attaches WAF to CloudFront
  api_rate_limit_per_second: 10
  api_burst_limit: 20

encryption:
  key_mode: aws_managed        # aws_managed | kms_customer
  kms_key_alias: ""            # required only when key_mode is kms_customer

documents:
  reader: pdfplumber           # pdfplumber | textract
  scan_reader: tesseract       # tesseract | textract | none (none rejects scans)
  table_reader: pdfplumber     # pdfplumber | textract | self_hosted_layout. Used for table and layout pages (see 5.23). Standard: textract
  per_company_override: {}     # example: { company_123: { scan_reader: textract } }
  categories:                  # set with the client (see 5.25)
    - invoice
    - bank_statement
    - financial_statement
    - budget
    - contract
    - board_report
  upload_types: [new, update, delete]
  delta_tracking: true         # true = on update, skip unchanged pages and chunks. false = full reprocess (see 5.25)
  duplicate_check: true        # same file, or same company, category and period, suggests Update
  version_retention_days: 365  # old versions kept for audit. Set with the client
  deleted_retention_days: 30   # soft delete, then purge

ingestion:
  page_router_enabled: true            # table and layout pages go to table_reader, text pages to reader (see 5.23)
  chunk_strategy: structure_recursive  # structure_recursive | plain_recursive
  child_chunk_tokens: 500              # size of the chunk that is searched
  parent_mode: section                 # section | page. The parent is stored as text, with no vector
  max_parent_tokens: 1500              # cap on one parent sent to the model
  llm_context_categories: []           # categories that get model-written context. Empty = off
  required_metadata: [company, period, category, currency, units, page, table_id]

lambda:
  snapstart_enabled: false
  keep_warm_ping: false
  weekly_republish: false
  question_provisioned_concurrency: 0   # 0 = off. Standard value is 2 (question function only)

models:
  answer:
    primary: provider_a/model_strong     # used for hard questions
    primary_fallbacks:                   # tried in this order if primary fails
      - provider_b/model_strong          # fallback 1
      - provider_c/model_strong          # fallback 2
      - self_hosted/open_model_small     # fallback 3, final safety net (in-region, open-source)
    cheap: provider_a/model_small        # router picks this for easy questions
    cheap_fallbacks:                     # tried in this order if cheap fails
      - provider_b/model_small           # fallback 1
      - provider_c/model_small           # fallback 2
      - self_hosted/open_model_small     # fallback 3, final safety net (in-region, open-source)
  failover_on:                           # what counts as a failure
    - timeout
    - first_word_timeout                 # no first word in time (new in v2)
    - rate_limit                         # "too many requests" errors
    - server_error
    - provider_unavailable
  embedding:
    primary: provider_a/embed_model      # changing this needs a reprocess job (see 5.6)
    version: v1                          # stored with every chunk
    dimensions: 1024                     # vector size. Choose before real data. Changing it needs a full reprocess (see 5.6)
    retry_attempts: 3                    # see 5.19
    retry_wait_seconds: 2
  rerank:
    primary: self_hosted/cross_encoder_small   # in-region cross-encoder (see 5.24). Pilot can use a small CPU model
    timeout_ms: 600
    on_failure: search_order             # use the search order, tag the trace, alert
  timeout_seconds: 20                    # limit for the whole answer, not the first word
  first_token_timeout_seconds: 4         # no first word by now counts as a failure
  backup_request_enabled: true           # see 5.10
  backup_request_after_seconds: 2.5      # send a second call to fallback 1, keep primary running
  prompt_cache_enabled: true             # see 5.14
  max_output_tokens: 1000
  monthly_budget_per_company: 50         # soft limit, alerts when reached

question_flow:
  parallel_steps: true                   # see 5.11
  understand_mode: rules_then_model      # rules_then_model | model_only (see 5.12)
  rules_confidence_min: 0.9              # rules decide only at or above this score
  chunk_token_budget: 4000               # most chunk text sent to the model per question

retrieval:
  rerank_top_n: 50                       # lower to 25 only after the golden set proves no drop (see 5.13)
  rerank_parallel_batches: 2             # split the rerank into batches that run together
  reranker: cross_encoder                # the rerank step is a cross-encoder (see 5.24)
  evidence_min_score: 0.30               # best rerank score under this means "insufficient data". Set from the golden set
  evidence_min_search_score: 0.50        # used only when the reranker is down
  evidence_min_chunks: 1

output_gate:
  mode: per_sentence                     # per_sentence | full_answer (see 5.16). The check itself is never off

cache:
  answer_enabled: true                   # see 5.15
  clear_on_upload: true                  # must stay true while answer_enabled is true
  ttl_seconds: 3600
                                         # cache key always includes company, role, access scope and document stamp (see 5.15)

auth:
  role_cache_seconds: 60                 # how long a role check result is reused (see 5.18)
  refresh_token_days: 7
  role_cache_seconds_privileged: 0       # System Admin and Executive Leadership roles. 0 = look up fresh on every call

edge:
  http3_enabled: true

answer_check:                            # see 5.28
  retry_max: 1                           # 0 or 1. 0 = no retry
  retry_time_limit_seconds: 4            # retry only if less time than this has passed. Set after a load test

metering:                                # see 5.26. Always on
  price_table: config/prices.yaml
  shared_cost_split: requests_and_runtime
  reconcile_tolerance_percent: 10

consistency:                             # see 5.27
  fresh_read_window_seconds: 10          # right after an upload, reads use the main database for this long
  job_max_receive_count: 5               # tries before a job goes to the retry list

access:                                  # see 5.29
  roles:
    - executive_leadership               # CEO, CFO, VP of Finance
    - corporate_finance_planners
    - audit_compliance
    - system_admin
  permissions_file: config/permissions.yaml
  users_per_company_max: 10

scale:                                   # see 5.20 to 5.22. Low on purpose in the pilot: these only cap work and add no cost
  cells: 1                               # every company maps to cell 1
  vector_store: aurora_pgvector          # all vector search goes through one search interface
  ingestion_max_parallel_jobs_per_company: 1
  reprocess_max_parallel_companies: 1
  queue_priority: quick_first            # quick_first | first_come
  queue_max_wait_seconds: 5              # after this, show the "busy" message
```

Model endpoints must always be in the approved region. This is not a switch (see section 8).

Standard values to go back to: `min_capacity_acu: 0.5`, `waf_enabled: true`, `key_mode: kms_customer`, `scan_reader: textract`, `table_reader: textract`, `snapstart_enabled: true`, `keep_warm_ping: true`, `weekly_republish: true`, `rds_proxy_enabled: true`, `standby_reader_enabled: true`, `question_provisioned_concurrency: 2`.

The traffic numbers (`lambda_reserved_concurrency`, `db_pool_size_per_function`, `aurora_max_capacity_acu`) and the model timing numbers (`first_token_timeout_seconds`, `backup_request_after_seconds`) are starting guesses. The chunk sizes, the `evidence_min_score` values and `retry_time_limit_seconds` are starting guesses as well. The `scale` numbers are starting guesses too, and stay low in the pilot so they add no cost. Set the final values after a load test.

---

## 4. Validation rules (config module must enforce)

| Rule | Reason |
|---|---|
| `key_mode: kms_customer` needs a non-empty `kms_key_alias` | Prevents a broken key setup |
| `min_capacity_acu` must be 0 or 0.5 or higher | Aurora limits |
| `scan_reader: none` means scans are rejected with a clear message to the user | No silent bad reads |
| `snapstart_enabled: true` needs a zip package and Python 3.12 or above | SnapStart limits |
| `keep_warm_ping: true` must use a health path that never touches the database | Otherwise Aurora never pauses |
| `waf_enabled: true` needs the CloudFront web ACL resource to exist | Avoids a failed deploy |
| `reader` and `scan_reader` values must match a registered reader | No unknown readers |
| Every model in `models` must be on the approved model list for our region | Data residency |
| Each chain (`primary` plus `primary_fallbacks`, and `cheap` plus `cheap_fallbacks`) must have exactly 3 fallbacks, and all models in a chain must be different | A real backup at every step |
| Fallback 3 in both chains must be a self-hosted, in-region model | The final safety net must not depend on an outside provider |
| `failover_on` must include `timeout`, `first_word_timeout`, `rate_limit` and `server_error` | Spikes, hangs and outages must trigger the fallback |
| Each fallback must have passed the golden set at its agreed minimum score before it goes live | A backup that gives bad answers is not a backup |
| Changing `embedding.primary` or `embedding.version` is blocked unless a reprocess job is marked complete | Old and new vectors cannot be mixed |
| `lambda_reserved_concurrency` times the larger of `db_pool_size_per_function` and `db_connections_per_request` must stay under the Aurora connection limit for `aurora_max_capacity_acu` (when `rds_proxy_enabled` is false) | A traffic spike cannot use up all connections |
| `lambda_reserved_concurrency` must be above 0 and `db_pool_size_per_function` must be 1 or more | No broken setup |
| `aurora_max_capacity_acu` must be at least 1 and at least `min_capacity_acu` | Aurora limits |
| `rds_proxy_enabled: true` with `min_capacity_acu: 0` is rejected until a test proves Aurora still pauses | A proxy may keep the database awake |
| `rds_proxy_enabled: true` needs the proxy resource to exist and the app to use its endpoint | Avoids a failed deploy |
| `standby_reader_enabled: true` with `min_capacity_acu: 0` is rejected until a test proves they work together | Pause and a standby copy may not fit |
| `first_token_timeout_seconds` must be below `timeout_seconds` and at most 5 | One failover must still land inside the 7 second p99.9 target |
| `backup_request_after_seconds` must be below `first_token_timeout_seconds` | The backup must start before the timeout |
| `backup_request_enabled: true` needs fallback 1 of the chosen chain to be live and past the golden set | The backup call must be a trusted model |
| `question_provisioned_concurrency` must be 0 or more, and not above `lambda_reserved_concurrency` | It counts toward the cap |
| `understand_mode: rules_then_model` needs `rules_confidence_min` between 0.5 and 1 | Rules must be sure before they decide |
| `rerank_top_n` must be between 10 and 100. Lowering it is blocked unless CI shows the golden set score is unchanged | A useful chunk must not be dropped |
| `rerank_parallel_batches` must be 1 or more, and must divide the chunks so each chunk is scored once | Same result as one big batch |
| `output_gate.mode` must be `per_sentence` or `full_answer`. There is no "off" value | The citation check is never removable |
| `cache.answer_enabled: true` needs `cache.clear_on_upload: true` | An old answer must never survive a new file |
| `cache.ttl_seconds` must be above 0 when `cache.answer_enabled` is true | No cache that never expires |
| `auth.role_cache_seconds` must be between 0 and 300 | A removed role must lose access quickly |
| `auth.refresh_token_days` must be between 1 and 30 | Sessions must expire |
| `parallel_steps: true` needs the input gate to finish before any model call | Nothing reaches a model before the gate passes |
| `db_connections_per_request` must be 1 or more, and `db_pool_size_per_function` must be at least `db_connections_per_request` when `parallel_steps` is true | Otherwise parallel steps line up on one connection and the speed gain is lost |
| `ingestion_max_concurrency` must be 1 or more and below `lambda_reserved_concurrency` | Upload work cannot take every slot |
| `embedding.retry_attempts` must be 0 to 5, `retry_wait_seconds` 1 to 10, and attempts times wait must stay under 10 seconds | A failing provider ends in the friendly message, not a long hang |
| Changing `embedding.dimensions` is blocked unless a reprocess job is marked complete | Same rule as changing the embedding model |
| `auth.role_cache_seconds_privileged` must be between 0 and `role_cache_seconds` | Privileged roles never wait longer than other roles |
| The answer cache key must include company, role, access scope and document stamp. A unit test in CI proves the key changes when any of them changes | One company or role never sees another's cached answer |
| `scale.cells` must be 1 or more, and the router must map every company to exactly one cell. A company with no cell, or two cells, stops the app from starting | No lost or doubled company |
| `scale.vector_store` must match a registered store | No unknown store |
| `ingestion_max_parallel_jobs_per_company` and `reprocess_max_parallel_companies` must be 1 or more | No stuck queue |
| `queue_priority` must be `quick_first` or `first_come` | No unknown value |
| `queue_max_wait_seconds` must be between 1 and 30 | Waiting always ends in a clear message |
| `access.roles` must list every role, and each one needs a full entry (every action and every document category) in `permissions_file`. An unknown role or a missing entry stops startup | No role with undefined access |
| `documents.categories` must not be empty and must match the categories in `permissions_file` exactly | Every category has a defined access rule |
| `upload_types` must be `new`, `update` and `delete` | No unknown upload type |
| `delta_tracking: true` needs `chunk_strategy: structure_recursive` | Stable chunk ids are needed to find what changed |
| `version_retention_days` must be 30 or more, and `deleted_retention_days` 1 or more | Old versions and deletions can always be audited |
| `table_reader` must match a registered reader | No unknown readers |
| `child_chunk_tokens` must be between 200 and 800 | Smaller chunks double the vectors, larger ones lose precision |
| Changing `chunk_strategy`, `child_chunk_tokens` or `parent_mode` is blocked unless a reprocess job is marked complete | Old and new chunks must not be mixed |
| `max_parent_tokens` must be at least `child_chunk_tokens` and not above `chunk_token_budget` | Prompt size and model cost stay predictable |
| `required_metadata` must include company, period, category, currency, units and page | Numbers cannot be read correctly without them |
| Every entry in `llm_context_categories` must be a valid category, and the pull request must include a cost estimate | Model-written context costs about $0.0006 per chunk |
| `retrieval.reranker` must be `cross_encoder`, `models.rerank.timeout_ms` must be 100 to 1000, and `models.rerank.on_failure` must be `search_order` | A down reranker never stops questions |
| `evidence_min_score` and `evidence_min_search_score` must be between 0 and 1, and `evidence_min_chunks` 1 or more. Changing a score is blocked unless CI shows the no-answer questions in the golden set still pass | Too high gives too many "insufficient data" answers, too low gives wrong answers |
| `answer_check.retry_max` must be 0 or 1, and `retry_time_limit_seconds` must be between 1 and 4 | One retry must still land inside the first-response target |
| `metering.price_table` must hold a price for every model in `models`, for embedding, rerank and Textract, and for each storage and database item. `reconcile_tolerance_percent` must be between 1 and 25 | No unpriced call |
| `consistency.fresh_read_window_seconds` must be between 0 and 60, and `job_max_receive_count` between 1 and 10 | A job must fail visibly, not loop for ever |
| `access.users_per_company_max` must be 1 or more | No broken setup |
| Onboarding must confirm that every partition exists before a company's first upload is accepted | A missing partition cannot fail an upload halfway |

---

## 5. Switch reference

### 5.1 Aurora pause when idle

| | Pilot | Standard |
|---|---|---|
| Setting | `min_capacity_acu: 0` | `min_capacity_acu: 0.5` |
| Effect | First request after idle waits about 15 seconds | Always ready |

**Code rules**
- Database calls must go through one connection helper with retry (attempts and wait from config).
- The app must show "waking up, please wait" while retrying, controlled by `show_waking_message`.
- Scheduled jobs and pings must not open database connections unless needed.

**Rollback:** set `min_capacity_acu: 0.5`, deploy. No data change.

### 5.2 WAF off

| | Pilot | Standard |
|---|---|---|
| Setting | `waf_enabled: false` | `waf_enabled: true` |
| Protection | CloudFront basics plus API rate limits | WAF rules plus rate limits |

**Code rules**
- The WAF resource is written in infrastructure code and attached only when the flag is true.
- Rate limits stay on in both modes and come from config.

**Rollback:** set `waf_enabled: true`, deploy. No data change. Turn this on before real client data goes live.

### 5.3 AWS-managed keys

| | Pilot | Standard |
|---|---|---|
| Setting | `key_mode: aws_managed` | `key_mode: kms_customer` |
| Encryption at rest | On | On, with our own key control |

**Code rules**
- Never reference a key ID directly. Always get the key setting from config.
- All S3 buckets, Aurora and DynamoDB take their key setting from the same config value.

**Rollback (needs planning, not a one-line change):**
1. Schedule a short maintenance window.
2. Create the KMS key and set `kms_key_alias`.
3. Copy S3 files to the new key setting. Restore the database from a snapshot encrypted with the new key. Recreate DynamoDB with the new key if needed.
4. Set `key_mode: kms_customer`, deploy, test, then remove old copies.

Tip: it is far easier to do this early, while data volume is small.

### 5.4 Free document readers

| | Pilot | Standard |
|---|---|---|
| Setting | `reader: pdfplumber`, `scan_reader: tesseract` | `scan_reader: textract` |
| Scans | Lower accuracy | Better accuracy |

**Code rules**
- All readers must implement one common interface and return the same output shape: text, tables, page numbers.
- Page and table numbers must be kept by every reader, so citations always work.
- Choose the reader from config, with optional per-company override.
- Table and layout pages use `table_reader` (see 5.23).
- If a reader's confidence is low, mark the document as "needs review" instead of guessing.

**Rollback:** set `scan_reader: textract` (or `reader: textract`), deploy. Reprocess old documents only if needed, using a reprocess job that does not duplicate chunks.

### 5.5 Lambda SnapStart off

| | Pilot | Standard |
|---|---|---|
| Setting | `snapstart_enabled: false` | `snapstart_enabled: true` |
| First request | Slower after idle | Faster |

**Code rules (keep these true even while SnapStart is off)**
- Heavy setup happens at startup, not inside the request.
- After-restore step must refresh database connections, keys, tokens and random seeds.
- Functions stay small, with lazy imports.
- Deploy as zip packages, not container images.

**Rollback:** set `snapstart_enabled: true`, `keep_warm_ping: true`, `weekly_republish: true`, deploy. A new version and fresh snapshot are created on deploy.

### 5.6 AI model swap

| | Pilot | Standard |
|---|---|---|
| Setting | Models named in `models` | Any approved model |
| Change effort | Config change | Config change |

**Code rules**
- The app talks only to the model gateway (LiteLLM). No code may call a provider directly.
- Model names appear only in config, never in code.
- The model router picks `cheap` or `primary` from config, based on the question type.
- If the chosen model fails, the gateway tries its 3 fallbacks in order and logs every step. A failure means any error listed in `failover_on`, including rate limit errors and a missing first word.
- The cheap chain does not jump to the strong chain. It uses its own 3 fallbacks.
- Fallback 3 is the final safety net. It is a self-hosted open-source model in the approved region, so it works even if every outside provider is down. It is used only after fallbacks 1 and 2 have also failed.
- Answers from fallback 3 still go through the citation check and the "insufficient data" rule. It may be less capable, so tag these answers in traces and alert the team when it is used.
- If all models in the chain fail, show a clear "temporarily unavailable, please try again" message. The app must never crash or show a raw error.
- Log the model name on every answer and trace.
- Prompts must not depend on one provider's special features. Keep them provider-neutral.
- Embedding calls (questions and uploads) follow the retry rules in 5.19.

**Swapping an answer model**
1. Set the new model name in config on a branch.
2. Run the 100-question golden set. Do not continue if the score drops.
3. Deploy to staging, then production in a quiet period.
4. Watch cost and latency dashboards for one day.

**Rollback:** set the old model name back, deploy. No data change.

**Swapping the embedding model (not a one-line change)**
- Every chunk stores the embedding model name and version.
- Old and new vectors must never be mixed in one search.
- Changing the vector size (`embedding.dimensions`) is treated the same as changing the model.
1. Add the new embeddings next to the old ones (new column or table).
2. Run a background reprocess job for all documents. Make it safe to rerun, with no duplicates. Run it as a rolling job, a few companies at a time (see 5.21), never all at once.
3. When it finishes, run the golden set against the new vectors.
4. Switch search to the new vectors by changing `embedding.primary` and `embedding.version`.
5. Keep the old vectors until you are sure, then delete them.

**Rollback:** switch search back to the old vectors while they still exist.

### 5.7 Connection limits

| | Pilot | Standard |
|---|---|---|
| Setting | Small concurrency cap, pool size 3 (one per parallel step) | Higher cap, set from a load test |
| Effect | Extra requests wait or get a clear "busy" message | More users at once |

**Code rules**
- All database calls use the one connection helper. Pool size, connections per request and timeout come from config.
- Upload and ingestion work is capped by `ingestion_max_concurrency`, so uploads cannot slow live questions.
- Reuse the connection between requests. Never open one per request.
- When the cap is reached, show a friendly "busy, please try again" message, not a raw error.
- The concurrency cap and the Aurora ceiling are written in infrastructure code and read from config.

**Rollback:** set the old numbers, deploy. No data change.

### 5.8 RDS Proxy

| | Pilot | Standard |
|---|---|---|
| Setting | `rds_proxy_enabled: false` | `rds_proxy_enabled: true` |
| Effect | Functions connect straight to Aurora | A proxy shares connections across functions |

**Code rules**
- The connection helper picks the proxy endpoint or the direct endpoint from config. No other code knows the difference.
- The proxy resource is written in infrastructure code and created only when the flag is true.
- Both paths are written and tested.
- Before turning this on with `min_capacity_acu: 0`, test that Aurora still pauses. If it does not, the pause saving is lost.

**Rollback:** set `rds_proxy_enabled: false`, deploy. No data change.

### 5.9 Standby reader

| | Pilot | Standard |
|---|---|---|
| Setting | `standby_reader_enabled: false` | `standby_reader_enabled: true` |
| Effect | One database copy | A second copy takes over if the first fails, and can serve reads |

**Code rules**
- The reader resource is written in infrastructure code and created only when the flag is true.
- When on, read-only queries (search, source viewer) may use the reader endpoint. Writes always go to the main one.
- When off, all queries use the main endpoint. Both paths are written and tested.
- Before turning this on with `min_capacity_acu: 0`, test that pause and the standby copy work together.

**Rollback:** set `standby_reader_enabled: false`, deploy. The extra copy is removed, no data change.

### 5.10 Slow model protection (first word timeout and backup request)

| | Before | Now |
|---|---|---|
| First word limit | None (only the 20 second whole-answer limit) | `first_token_timeout_seconds: 4` |
| Backup | None | A second call to fallback 1 after 2.5 seconds, while the primary keeps running |
| Effect | A hanging model made the user wait up to 20 seconds | A slow but healthy model is never cut off early. The wait is capped |

**Code rules**
- The gateway starts a timer when the model call begins.
- At `backup_request_after_seconds` with no first word, the gateway sends the same prompt to fallback 1 of the same chain. The primary call is not cancelled.
- Whichever model gives a first word first wins. The gateway cancels the other call.
- If neither gives a first word by `first_token_timeout_seconds`, the primary counts as failed and the chain moves on in order.
- Never jump to fallback 3 just because time has passed. It is used only after fallbacks 1 and 2 have failed.
- The backup call uses the same prompt, same chunks and same citation rules. Only the model differs.
- Log whether the backup fired, which model won, and the first word time. Attach these to every trace.
- Both paths are written and tested: backup on and backup off.

**Rollback:** set `backup_request_enabled: false`, deploy. No data change. The first word timeout still applies.

### 5.11 Parallel steps

| | Before | Now |
|---|---|---|
| Setting | `parallel_steps: false` | `parallel_steps: true` |
| Effect | Steps run one after another | Steps with no dependency run together |

**What runs together (same answers, less waiting)**
- Input gate, question embedding and the understand step start at the same time.
- Chat history, company settings and a database connection load while the request is being checked.
- Number calculations (SQL) run next to search and rerank.
- Rerank runs in `rerank_parallel_batches` batches. Each chunk is scored on its own, so the result is the same.
- The prompt is built and the model connection is opened during rerank. Only the final chunks are added at the end.

**Code rules**
- Nothing reaches a model until the input gate has passed. If the gate blocks the question, throw away all parallel work.
- Parallel work must never change the final list of chunks, the numbers, or the order of citations.
- The sequential path stays written and tested. The golden set must give the same answers on both paths.
- All maths is done by code (SQL or pandas) in the "calculate with code" step. The model may only repeat numbers from code results or cited chunks.
- Parallel work needs at least `db_connections_per_request` connections. With fewer, the steps line up and the gain is lost (see the validation rules).

**Rollback:** set `parallel_steps: false`, deploy. No data change.

### 5.12 Question understanding mode

| | Before | Now |
|---|---|---|
| Setting | `understand_mode: model_only` | `understand_mode: rules_then_model` |
| Effect | A small model reads every question | Simple rules read clear questions. The model reads only unclear ones |

**Code rules**
- Rules match company, period and metric against known lists for that company.
- If the rules score at or above `rules_confidence_min`, use the result. If not, call the small model. Never guess.
- Log which path was used on every question, so we can see how often rules decide.
- Both paths return the same output shape.

**Rollback:** set `understand_mode: model_only`, deploy. No data change.

### 5.13 Rerank size

| | Before | Now |
|---|---|---|
| Setting | `rerank_top_n: 50` | `rerank_top_n: 50` (go to 25 only after proof) |
| Effect | Scores 50 chunks | Scores fewer chunks, so it runs faster |

**Code rules**
- Lowering this number is allowed only when the golden set score and the citation pass rate are unchanged.
- The number of chunks sent to the model does not change here. Only the number scored changes.
- The rerank step is a cross-encoder model (see 5.24).

**Rollback:** set the old number, deploy. No data change.

### 5.14 Prompt cache

| | Before | Now |
|---|---|---|
| Setting | `prompt_cache_enabled: false` | `prompt_cache_enabled: true` |
| Effect | Full prompt processed every time | Fixed instructions are reused, so the first word comes sooner |

**Code rules**
- Put the fixed instructions first and the question and chunks last, so the cache can be reused.
- Never put company data or user data in the cached part.
- If a provider does not support it, skip it quietly for that provider only. The answer must be the same.

**Rollback:** set `prompt_cache_enabled: false`, deploy. No data change.

### 5.15 Answer cache

| | Before | Now |
|---|---|---|
| Setting | `answer_enabled: false` | `answer_enabled: true` |
| Effect | Every question runs the full flow | A repeat question gets the saved answer fast |

**Code rules**
- The cache key includes the company, the role and access scope of the user, the question, and a document version stamp for that company. The company is checked again when the answer is read. A unit test proves the key changes when any part changes.
- Uploading, changing or deleting a document changes the stamp, which clears old answers. `clear_on_upload` must stay true.
- A cached answer is shown only to a user whose role is allowed to see it. The role check still runs on every request.
- Cached answers keep their citations and their model name. Mark them as cached in traces.
- Entries expire after `ttl_seconds`.

**Rollback:** set `answer_enabled: false`, deploy, then clear the cache table.

### 5.16 Output check mode

| | Before | Now |
|---|---|---|
| Setting | `full_answer` | `per_sentence` |
| Effect | Wait for the whole answer, then check | Check each sentence as it streams |

**Code rules**
- In `per_sentence`, hold back each sentence until its citations (document, page, table), numbers (each must match a code result or a cited chunk) and personal data check pass. Show it only after that.
- If a check fails, never show that sentence. Replace it with a safe message or stop the answer with "insufficient data".
- In `full_answer`, nothing is shown until the full answer passes. Use this only as the fallback path.
- The checks are the same in both modes. Only the timing differs. There is no mode that skips them.
- What happens when a check fails (one retry, then "insufficient data") is in 5.28.
- Both modes are written and tested.

**Rollback:** set `mode: full_answer`, deploy. No data change.

### 5.17 Provisioned concurrency (question function only)

| | Pilot | Standard |
|---|---|---|
| Setting | `question_provisioned_concurrency: 0` | `question_provisioned_concurrency: 2` |
| Effect | Rare slow restores can add 300 to 600 ms | Ready copies remove these spikes |

**Code rules**
- Applies to the question function only. Other functions stay as they are.
- The ready copies count toward `lambda_reserved_concurrency`.
- Written in infrastructure code and created only when the number is above 0.

**Rollback:** set `question_provisioned_concurrency: 0`, deploy. No data change.

### 5.18 Sign-in speed (role check cache and refresh tokens)

| | Before | Now |
|---|---|---|
| Role check | Checked fresh every call | Result reused for `role_cache_seconds` (60) |
| Sign-in | Full sign-in each visit | Refresh token keeps users signed in for `refresh_token_days` (7) |

**Code rules**
- The role check still runs on every request. The cache only saves the lookup.
- Keep the role cache in one shared place (DynamoDB), or check a small "role version" number on every call. Never keep it only in function memory, because each running copy has its own memory.
- When an admin changes or removes a role, the role version goes up and every running copy sees it on the next call. The wait time is the worst case, not the normal case.
- System Admin and Executive Leadership roles use `role_cache_seconds_privileged` (0 means a fresh lookup on every call).
- Refresh tokens expire on schedule and can be revoked by an admin.

**Rollback:** set `role_cache_seconds: 0` and a lower `refresh_token_days`, deploy. No data change.

### 5.19 Embedding retry

| | Pilot | Standard |
|---|---|---|
| Setting | `retry_attempts: 3`, `retry_wait_seconds: 2` | Same, set from a load test |
| Effect | A failing embedding provider gives a short delay, then a clear message | Same |

There is no backup embedding model. A second set of vectors would cost too much for clients with many documents already embedded. Users accept a short delay, a retry, or a failure message.

**Code rules**
- Every embedding call (a question or an upload) retries `retry_attempts` times, waiting `retry_wait_seconds` between tries.
- For a question: if every try fails, show "temporarily unavailable, please try again". Never show a raw error.
- For an upload: the job stays in the retry list and finishes when embedding returns, with no duplicate chunks.
- Log every retry on the trace. Alert the team when embedding fails or retries often.
- Both paths are written and tested: retry succeeds, and retries run out.

**Rollback:** set the old numbers, deploy. No data change.

### 5.20 Cells and vector store

| | Pilot | Standard |
|---|---|---|
| Setting | `cells: 1`, `vector_store: aurora_pgvector` | More cells, set from a load test. Very large companies get their own |
| Effect | One database and one vector store for everyone | Companies spread across databases, so search stays fast |

**Code rules**
- The router maps every company to a region and a cell. In the pilot every company is in cell 1.
- Each cell has its own database and vector store. They are written in infrastructure code and created only for cells listed in config. The pilot creates one, so there is no extra cost.
- All vector search goes through one search interface. The store name comes from config. No code outside the interface knows which store is in use.
- Inside a cell, each company has its own partition of the large tables (documents, chunks, vectors, metrics). An onboarding job creates it, and must finish before the first upload. Each partition has its own vector index, so the company filter happens first. The row-level rule stays on as a second lock.
- Every query must carry the company id. A test build rejects any query that does not.
- Schema changes run through a migration tool that loops over every partition.
- When a company leaves, its partitions and its S3 folder are dropped.
- A search for one company must never return another company's chunks.
- Vector size comes from `embedding.dimensions`. Changing it follows the embedding swap steps in 5.6.
- Moving a company to another cell is a planned job: copy, verify, switch the router entry, keep the old copy until sure. A company is never half moved.
- Both paths are written and tested: one cell, and two cells (use two test cells in staging).

**Rollback (needs planning, not a one-line change):** move the company back with the same job in reverse, then remove the empty cell. Do this while data volume is small.

### 5.21 Fair share limits

| | Pilot | Standard |
|---|---|---|
| Setting | 1 ingestion job per company, 1 reprocess company at a time | Set from a load test (25 to 50 jobs per company is a sensible start) |
| Effect | One company cannot use up shared capacity | Same, with higher numbers |

**Code rules**
- Each company can run at most `ingestion_max_parallel_jobs_per_company` ingestion jobs. Extra jobs wait in the queue. Each cell has its own queue.
- A reprocess (for example an embedding change) runs a few companies at a time (`reprocess_max_parallel_companies`) and always has lower priority than live questions.
- Log the active limits at startup.
- Both paths are written and tested: under the limit, and at the limit.

**Rollback:** set the old numbers, deploy. No data change.

### 5.22 Spike queue (priority and wait)

| | Pilot | Standard |
|---|---|---|
| Setting | `queue_priority: quick_first`, `queue_max_wait_seconds: 5` | Same, wait set from a load test |
| Effect | A sudden wave waits briefly, then gets a clear "busy" message | Same |

**Code rules**
- Heavy work (search, model calls, ingestion) goes through a short waiting line. A request that waits longer than `queue_max_wait_seconds` gets the "busy, please try again" message from 5.7.
- With `quick_first`, quick questions go before uploads and reprocess. With `first_come`, the order is plain arrival. Both are written and tested.
- No company can use more than its share of any shared limit (the caps in 5.21).
- For known peaks (month-end, quarter close, board meetings), raise the capacity numbers before the peak through a normal config pull request, then lower them afterwards. The same release rules apply.
- Log the queue wait time on every trace.

**Rollback:** set the old values, deploy. No data change.

### 5.23 Chunking and parsing

| | Pilot | Standard |
|---|---|---|
| Setting | `table_reader: pdfplumber`, `chunk_strategy: structure_recursive`, `child_chunk_tokens: 500` | `table_reader: textract` (or a self-hosted layout reader), same chunk settings |
| Effect | Table pages read with the free tool | Better table accuracy |

**Code rules**
- A page router checks every page before reading. Table and layout pages go to `table_reader`, text pages go to `reader`. With `page_router_enabled: false`, every page goes to `reader`. Both paths are written and tested.
- A table reader returns each table as one unit, with its header row, units and page number (same output shape as 5.4).
- Chunk by structure: headings, paragraphs and lists. Never split a table. The numbers in a table are also saved as structured rows, so code can calculate with them.
- Parent and child chunks: the child chunk (about `child_chunk_tokens`) is embedded and searched. Its parent (a section or a page, set by `parent_mode`) is saved as text only, with no vector. A parent sent to the model is cut to `max_parent_tokens`, and all chunk text per question stays within `chunk_token_budget`.
- Every chunk gets a context header built by rules: company, period, category, section title, table title, currency and units. It is embedded with the text.
- Model-written context is used only for the categories in `llm_context_categories`. Empty means off.
- Before saving, check `required_metadata`. If something is missing, mark the chunk "needs review". Never guess.
- Chunk ids are stable: document id, section path and a hash of the text. This lets updates find what changed (see 5.25).
- Semantic chunking is not used.
- Changing the chunking settings needs a reprocess job, the same rule as an embedding change.

**Rollback (needs a reprocess):** set the old chunk settings and run the reprocess job. Keep the old chunks until the golden set passes on the new ones.

### 5.24 Rerank model and evidence score

| | Pilot | Standard |
|---|---|---|
| Setting | `reranker: cross_encoder`, `models.rerank.primary: self_hosted/cross_encoder_small`, `evidence_min_score: 0.30` | Same. Model size set from a load test |
| Effect | Question and chunk are scored together | Same |

**Code rules**
- The rerank step is a cross-encoder. It scores the question against each of the top `rerank_top_n` chunks, in `rerank_parallel_batches` batches. There is no second cross-encoder after it.
- The model runs in the approved region and is on the approved model list.
- The "Enough evidence?" step uses its score. If the best score is under `evidence_min_score`, or fewer than `evidence_min_chunks` chunks pass, the answer is "insufficient data".
- Set the score from the golden set, including questions that have no answer. Changing it is blocked unless CI passes.
- If the rerank call fails or passes `timeout_ms`, use the search order, tag the trace `rerank_fallback`, alert the team, and use `evidence_min_search_score` for the evidence check.
- Log the rerank time and model name on every trace.
- Both paths are written and tested: reranker working, and reranker down.

**Rollback:** set the old numbers or model name, deploy. No data change.

### 5.25 Document categories and updates

| | Pilot | Standard |
|---|---|---|
| Setting | `delta_tracking: true`, `duplicate_check: true` | Same. Categories set with the client |
| Effect | An update reads and embeds only what changed | Same |

**Code rules**
- The upload form needs a Document Category (from `categories`), an Upload Type (`new`, `update` or `delete`) and a status (draft or final). An update asks which document it replaces.
- The category decides which roles may see the document (5.29) and which metadata is required (5.23).
- Duplicate check: the same file hash, or the same company, category, period and a similar name, shows a warning and suggests Update.
- With `delta_tracking: true`: hash every page and skip unchanged pages (no reading, no embedding). Compare chunk ids and hashes, and embed only new or changed chunks. Mark removed chunks inactive. With `false`, the new version is fully reprocessed. Both paths are written and tested.
- Every update makes a new version. Old versions are kept for `version_retention_days`. Answers use the latest final version and cite the version.
- On every update (not switchable): recompute the affected metrics by code, change the document stamp (this clears cached answers), mark dependent forecasts, alerts and dashboards as stale, flag other documents for the same company and period as "may be affected", and notify the approvers of recommendations built on the old numbers. Other documents are never edited automatically.
- Conflicts: final beats draft, then newer beats older. If numbers still differ, show both with citations.
- Delete: soft delete for `deleted_retention_days`, then purge chunks, vectors, metrics and cache entries. The audit entry stays.
- All changes for one version are saved in one transaction (see 5.27).

**Rollback:** set `delta_tracking: false`, deploy. No data change. The next update does a full reprocess.

### 5.26 Cost metering

| | Pilot | Standard |
|---|---|---|
| Setting | Always on. `price_table: config/prices.yaml` | Same |
| Effect | Spend per company, per service and per model is visible | Same |

**Code rules**
- Every paid call writes one usage row: company, service, units, estimated cost, model name and trace id. The model gateway writes the model calls. Ingestion writes Textract and embedding. The rerank step and the functions (run time) write their own.
- Prices come only from `config/prices.yaml`, never from code. A missing price stops startup.
- Shared services (Lambda, API Gateway and similar) are split by company using request counts and run time (`shared_cost_split`).
- The cost view shows spend per company, per service, and model calls per model. Only roles that the permissions table allows can open it.
- Each month, compare the sum of the rows with the real bills. If the gap is above `reconcile_tolerance_percent`, alert.
- A paid call without a usage row is a bug. CI has a test for every call site, and a runtime alert catches the rest.
- The existing `monthly_budget_per_company` alert reads from these rows.

**Rollback:** metering cannot be switched off. Only prices change, by pull request.

### 5.27 Consistency settings (ACID and BASE)

| | Pilot | Standard |
|---|---|---|
| Setting | `fresh_read_window_seconds: 10`, `job_max_receive_count: 5` | Same, from a load test |
| Effect | Uploads are all or nothing, repeats do no harm | Same |

| Data | Where | Rule |
|---|---|---|
| Documents, chunks, vectors, metrics, versions | Aurora | ACID. One transaction per document version. Visible only when the whole version is saved |
| Roles, permissions, role version | DynamoDB and Aurora | Strongly consistent reads. Privileged roles use no cache |
| Audit log | Aurora and the write-once copy | ACID, append only |
| Job status | Aurora | ACID. Updated in the same transaction as the results |
| Answer cache | DynamoDB | BASE is fine. Entries stop being used when the document stamp changes. The stamp is read strongly consistent |
| Chat history, progress screens, counts | DynamoDB or the standby reader | BASE is fine. A lag of a few seconds is accepted |
| Raw files | S3 | Saved before the job is queued |
| Queue messages | SQS | Delivered at least once. Every job must be safe to repeat |

**Code rules**
- Jobs follow one state machine: received, stored, processing, committed, failed. A document shows "ready" only after commit.
- The document stamp changes in the same transaction as the document.
- Every ingestion step uses the job id and an upsert on the chunk id, so a repeat does no harm.
- When the standby reader is on, reads right after an upload use the main database for `fresh_read_window_seconds`, or until the reader has caught up.
- After `job_max_receive_count` tries, a job goes to the retry list and raises an alert.
- Both paths are written and tested: normal run, and killed or repeated job.

**Rollback:** set the old numbers, deploy. No data change.

### 5.28 Answer retry

| | Pilot | Standard |
|---|---|---|
| Setting | `retry_max: 1`, `retry_time_limit_seconds: 4` | Same, time set from a load test |
| Effect | A failed check gets one more try before "insufficient data" | Same |

**Code rules**
- A check failure means a missing citation, a number that does not match a code result or a cited chunk, or personal data in the answer.
- With `per_sentence`, a retry is allowed only if no sentence has been shown yet, and less than `retry_time_limit_seconds` has passed. If a check fails later, the answer ends with a clear message.
- With `full_answer`, a retry can happen any time before anything is shown, inside the same time limit.
- At most `retry_max` retries. A retry uses a stricter prompt and the next best chunks. It goes through the same gateway and gates.
- Tag the trace with the retry, and count it in metering.
- There is no model judge on every question.
- Feedback (thumbs and corrections) is stored per company. A person reviews it, and it is anonymised before it can enter the golden set. Nothing learned from one company is used for another. No training on client data without written consent. These rules are not switchable.
- Both paths are written and tested: `retry_max: 1` and `retry_max: 0`.

**Rollback:** set `retry_max: 0`, deploy. No data change.

### 5.29 Roles and permissions

| | Pilot | Standard |
|---|---|---|
| Setting | 4 roles in `access.roles`, permissions in `config/permissions.yaml` | Same |
| Effect | Each user has one role, and access follows the table | Same |

Roles (10 users per company): Executive Leadership (CEO, CFO, VP of Finance: 3 users), Corporate Finance & Planners (4 users), Audit & Compliance (2 users), System Admin (1 user).

Proposed permissions (confirm with the client):

| Role | Ask questions | Upload and update documents | Approve recommendations | Manage users and settings | See audit logs |
|---|---|---|---|---|---|
| Executive Leadership | Yes | No | Yes | No | No |
| Corporate Finance & Planners | Yes | Yes | No | No | No |
| Audit & Compliance | Yes (read only, all categories) | No | No | No | Yes |
| System Admin | No financial content | No | No | Yes | Yes |

**Code rules**
- Roles map to Cognito groups. Each user has exactly one role.
- Permissions come only from `config/permissions.yaml`: role by action by document category. No permission is written in code.
- Checked at the API, and again in the data layer (search filters by the categories the role may see).
- The role cache rules in 5.18 apply. System Admin and Executive Leadership use no cache (`role_cache_seconds_privileged: 0`).
- A table test covers every role, action and category. Both paths are written and tested.

**Rollback:** revert the permissions file in a pull request. No data change.

---

## 6. Latency targets and budget

**Targets for time to first word:** p95 at 3 seconds, p99 at 5 seconds, p99.9 at 7 seconds. A typical question must be answered in under 15 seconds.

Rough estimate for a hard question (strong model, Standard setup, US user on 5G):

| Step | Typical | Bad day (p95) |
|---|---|---|
| Request in (edge, API, role check, warm Lambda) | 90 ms | 200 ms |
| Input gate | 50 ms | 80 ms |
| Understand the question | 100 to 400 ms | 800 ms |
| Hybrid search | 100 ms | 200 ms |
| Rerank | 250 ms | 400 ms |
| Evidence check, router, gateway | 40 ms | 60 ms |
| Strong model first word | 900 ms | 1,650 ms |
| Output gate and first word back | 60 ms | 100 ms |
| **Total** | **~1.2 to 1.4 s** | **~2 to 2.3 s** |

With a slow model, the backup request caps the wait: about 1 s of work, plus 2.5 s, plus about 1 s for the backup's first word, so roughly 4.5 to 5 s. That fits inside the 7 second target.

These are estimates. Check them with a load test and set the final timeout values from real numbers.

---

## 7. Release and rollback steps

**Changing a switch**
1. Edit `config/<env>.yaml` in a branch.
2. CI runs schema validation and the golden question set on both the pilot config and the standard config.
3. Review, then deploy to staging and check the dashboard.
4. Deploy to production in a quiet period.
5. Check startup logs show the new values.

**Suggested order for the speed switches (one per release)**
1. Slow model protection (5.10)
2. Role check cache (5.18)
3. Parallel steps (5.11)
4. Prompt cache (5.14)
5. Question understanding mode (5.12)
6. Rerank size (5.13)
7. Answer cache (5.15)
8. Output check mode (5.16)
9. Provisioned concurrency (5.17)

After each one, compare first word time and the golden set score to the last release. If the score drops, roll back that one switch.

**Suggested order for the scale switches (one per release)**
1. Embedding retry (5.19)
2. Cells and vector store (5.20)
3. Fair share limits (5.21)
4. Spike queue (5.22)

**Suggested order for the design switches (one per release)**
1. Cost metering (5.26), so the effect of every later change can be seen
2. Roles and permissions (5.29)
3. Consistency settings (5.27)
4. Chunking and parsing (5.23). Do this before real client data is loaded, because it needs a reprocess
5. Document categories and updates (5.25)
6. Rerank model and evidence score (5.24)
7. Answer retry (5.28)

**Rolling back a switch**
1. Revert the config change in a new pull request (or set the standard value).
2. Follow the steps for that switch in section 5.
3. Confirm startup logs, traces and the golden question set.
4. Write a short note: what changed, why, and the date.

---

## 8. Never switchable (always on)

- Encryption at rest and in transit
- Role check on every request
- Company data separation: a partition per company, the row-level rule as a second lock, and an S3 folder per company
- Audit logs
- Citation and number check on every answer (only its timing can change, see 5.16)
- "Insufficient data" response when evidence is missing
- API rate limits
- Input checks for prompt tricks and personal data, finished before any model call
- Only in-region model endpoints (data residency)
- Lambda concurrency cap (the number can change, the cap itself cannot be removed)
- Answer cache clearing when a document changes or is deleted
- Answer cache key with company, role and access scope
- Role cache that every running copy can see (never function memory only)
- Company-first filtering in vector search
- Per-company limits on ingestion jobs (the numbers can change, the limits cannot be removed)
- A usage row for every paid call (cost metering)
- Permissions that come only from the permissions table, with every role fully defined
- Document updates change the stamp, recompute metrics and mark dependents stale
- Old document versions kept for the retention period
- At most one answer retry
- Feedback and learning stay inside one company
- Strongly consistent reads for roles and permissions
- Fallback 3 used only after fallbacks 1 and 2 have failed

---

## 9. Cost impact when switching back (rough, US prices)

| Switch | Extra cost per month |
|---|---|
| Aurora always on | About $30 to $40 |
| WAF on | About $8 to $15 |
| KMS keys | About $3 to $5 |
| Textract | About $1.5 to $15 per 1,000 pages |
| SnapStart on | A few dollars |
| AI model swap | Depends on the model price. Check the provider price list. An embedding swap also costs a one-time reprocess |
| Self-hosted fallback model (fallback 3) | Depends on the server size and whether it runs all the time. Check the calculator |
| RDS Proxy on | Has a fixed minimum charge. Check the calculator |
| Standby reader on | About the same as the main database, so roughly $30 to $40 at the smallest size |
| Higher concurrency cap | Only what the extra traffic uses |
| Backup request | One extra model call only on slow requests, usually a small share of traffic |
| Provisioned concurrency (2 copies) | A few dollars |
| Prompt cache | Usually lowers cost |
| Answer cache | Lowers cost on repeat questions. DynamoDB storage is small |
| Parallel steps, rules-first, rerank size | No extra cost. Rules-first removes some small model calls |
| More cells | Each extra cell adds its own database and vector store, so roughly the cost of another database. The pilot stays at 1 cell |
| Per-company and queue limits | No extra cost. They only cap work |
| Embedding retry | A few extra calls, only when the provider is failing |
| Shared role cache and role version | A few small DynamoDB reads |
| More connections per request | No cost on its own. Check the database connection limit |
| Table-aware reading (Textract tables) | Ten times the plain text price per page ($0.015 against $0.0015). The page router sends only table pages |
| Smaller chunks | Halving the chunk size doubles the vectors, so database cost rises about 30% (Low) to 70% (High) |
| Model-written context | About $0.0006 per chunk. Off by default |
| Cross-encoder rerank | A small machine, or a paid service at about $2 per 1,000 searches (estimate) |
| Delta tracking | Lowers cost. Unchanged pages and chunks are not read or embedded again |
| Cost metering | Small. One usage row per paid call |
| Answer retry | One extra model call, only on answers that failed a check |
| Partition per company | No extra cost |
| Roles and permissions | No extra cost |

Check the AWS Pricing Calculator for your region before switching.
