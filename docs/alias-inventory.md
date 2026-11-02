# Alias Inventory

Reviewed compatibility shim modules and canonical module choices.

| Alias module | Canonical module(s) | Reason / status |
|---|---|---|
| `finsight/adapters/queue/dead_letter.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/orchestration.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/queue.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/sfn.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/sqs.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/sqs_adapter.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/sqs_job.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/step_function.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/step_functions.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/queue/stepfunctions.py` | `finsight.adapters.queue.sqs_queue` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/database_transaction.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/database_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/db_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/pg_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/session_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/sql_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/sqlalchemy_unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/transaction_manager.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/unit_of_work_adapter.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/repositories/uow.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/adapter.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/aws_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/aws_virus_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/clam_av_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/clamav_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/default_virus_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/malware_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/security.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/security_scanner.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/virus_scan_adapter.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/virus_scanner_adapter.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/security/virus_scanner_impl.py` | `finsight.adapters.security.virus_scanner` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/cloudwatch_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/in_memory_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/logging_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/open_telemetry_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/otel.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/otel_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/span_tracer.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/span_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/structured_log_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/structured_tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/tracer.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/tracing.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/tracing/tracing_provider.py` | `finsight.adapters.tracing.tracing_adapter` | Retained documented shim; remove after migration. |
| `finsight/adapters/transaction.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/unit_of_work.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/adapters/uow.py` | `finsight.adapters.repositories.postgres_unit_of_work` | Retained documented shim; remove after migration. |
| `finsight/entrypoints/api/me.py` | `finsight.entrypoints.api, finsight.entrypoints.api.current_user` | Retained documented shim; remove after migration. |
| `finsight/entrypoints/api/user.py` | `finsight.entrypoints.api, finsight.entrypoints.api.current_user` | Retained documented shim; remove after migration. |
| `finsight/entrypoints/api/users.py` | `finsight.entrypoints.api, finsight.entrypoints.api.current_user` | Retained documented shim; remove after migration. |
