# Contract Tests

One shared test per port, run against every adapter implementation.

**Purpose:** Prove Liskov Substitution - any adapter can replace another.

**Structure:**
```
tests/contract/
  test_llm_gateway.py        # run against LiteLLMGateway, MockGateway
  test_vector_search.py      # run against AuroraPgVectorSearch, MockSearch
  test_document_reader.py    # run against PdfPlumber, Tesseract, Textract...
  test_cache_port.py         # run against DynamoAnswerCache, MockCache
  ...
```

**Each test file:**
- Defines abstract test class with port test cases
- Concrete test classes inherit and provide adapter fixture
- Tests: happy path, error cases, edge cases, idempotency

**Implemented shared contract suites today:**

| Port | Adapter (primary) | Contract suite |
| --- | --- | --- |
| `AnswerCache` | `finsight.adapters.cache.answer_cache.AnswerCache` | `tests/contract/test_answer_cache_contract.py` |
| `ChangeEventPublisher` | `finsight.adapters.messaging.change_event_publisher.ChangeEventPublisher` | `tests/contract/test_change_event_publisher_contract.py` |
| `ChunkRepository` | `finsight.adapters.repositories.postgres_chunk_repository.PostgresChunkRepository` | `tests/contract/test_chunk_repository_contract.py` |
| `DocumentRepository` | `finsight.adapters.repositories.postgres_document_repository.PostgresDocumentRepository` | `tests/contract/test_document_repository_lifecycle.py` |
| `VectorWrite` | `finsight.adapters.vector_store.aurora_pg_vector_write.AuroraPgVectorWrite` | `tests/contract/test_vector_write_contract.py` |
| `JobProgressPort` | `finsight.adapters.cache.job_progress.JobProgress` | `tests/contract/test_job_progress_port_contract.py` |
| `VirusScanner` | `finsight.adapters.security.virus_scanner.VirusScanner` | `tests/contract/test_virus_scanner_contract.py` |
| `DocumentReader` | `finsight.adapters.readers.pdf_plumber_reader.PdfPlumberReader` | `tests/contract/test_document_reader_contract.py` |
| `HybridSearch` | `finsight.adapters.vector_store.aurora_pg_vector_search.AuroraPgVectorSearch` | `tests/contract/test_hybrid_search_contract.py` |
| `Reranker` | `finsight.adapters.rerank.cohere_reranker.CohereReranker` | `tests/contract/test_reranker_contract.py` |
| `MetricRepository` | `finsight.adapters.repositories.postgres_metric_repository.PostgresMetricRepository` | `tests/contract/test_metric_repository_contract.py` |
| `WaitingLine` | `finsight.adapters.waiting_line.waiting_line_adapter.WaitingLineAdapter` | `tests/contract/test_waiting_line_contract.py` |
| `MeteringPort` | `finsight.adapters.metering.dynamo_metering.DynamoMetering` | `tests/contract/test_metering_port_contract.py` |
| `LLMGateway` | `finsight.adapters.llm.lite_llm_gateway.LiteLLMGateway` | `tests/contract/test_llm_gateway_contract.py` |
| `EmbeddingProvider` | `finsight.adapters.embedding.lite_llm_embedding.LiteLLMEmbedding` | `tests/contract/test_embedding_provider_contract.py` |
| `ObjectStorage` | `finsight.adapters.storage.s3_storage.S3Storage` | `tests/contract/test_object_storage_contract.py` |
| `QueuePort` | `finsight.adapters.queue.sqs_queue.SqsQueue` | `tests/contract/test_queue_port_contract.py` |
| `PartitionGateway` | `finsight.adapters.partitions.partition_manager.PartitionManager` | `tests/contract/test_partition_gateway_contract.py` |
| `UnitOfWork` | `finsight.adapters.repositories.postgres_unit_of_work.PostgresUnitOfWork` | `tests/contract/test_unit_of_work_contract.py` |
| `CompanyRepository` | `finsight.adapters.repositories.company_repository.CompanyRepository` | `tests/contract/test_company_repository_contract.py` |
| `UserRepository` | `finsight.adapters.repositories.user_repository.UserRepository` | `tests/contract/test_user_repository_contract.py` |
| `JobRepository` | `finsight.adapters.repositories.job_repository.JobRepository` | `tests/contract/test_job_repository_contract.py` |
| `DocumentTableRepository` | `finsight.adapters.repositories.postgres_document_table_repository.PostgresDocumentTableRepository` | `tests/contract/test_document_table_repository_contract.py` |
| `AuditLog` | `finsight.adapters.audit.postgres_audit_log.PostgresAuditLog` | `tests/contract/test_audit_log_contract.py` |

**Integration-only contract coverage:** ports whose adapters require a database,
AWS, or another external service do not have an in-memory unit path. Their
shared suites run against real services in integration CI:
`PartitionMetadataRepository`.

**Rules:**
- Every new adapter must pass all contract tests for its port
- Contract tests live here, not in adapter folders
- Run in CI for every adapter
- Adding a new adapter requires updating this matrix and the shared suite
