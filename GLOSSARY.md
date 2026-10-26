# Glossary

| Term | Definition |
| --- | --- |
| Company | Tenant boundary; every query and data access must be scoped by `company_id`. |
| Document | Source file ingested into the system (PDF, DOCX, XLSX, CSV, etc.). |
| Chunk | Text segment extracted from a document for embedding and retrieval. |
| Metric | Extracted business metric/value with context and provenance. |
| Answer | Generated response to a question, grounded in evidence with citations. |
| Citation | Reference linking an answer back to a specific chunk/document. |
| Role | User permission level (`executive_leadership`, `corporate_finance_planners`, `audit_compliance`, `system_admin`). |
| Switch | Config-driven feature flag with both ON/OFF paths tested. |
| RAG | Retrieval-Augmented Generation combining vector/keyword search with LLM. |
| pgvector | PostgreSQL extension for vector similarity search. |
