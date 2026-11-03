"""Key tuples for request-to-context mapping in the source-viewer package.

These are the known key names used across different API versions and callers
to extract values from request payloads, context objects, and keyword arguments.
"""

_CONTEXT_KEYS = (
    'request_context',
    'context',
    'ctx',
    'user_context',
    'auth_context',
    'security_context',
    'current_user',
    'principal',
    'identity',
    'user',
)
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'source_input',
    'citation_input',
    'citation',
)
_CITATION_KEYS = (
    'citation',
    'citation_locator',
    'locator',
    'citation_id',
    'citationId',
    'cid',
    'citation_input',
)
_USE_CASE_KEYS = (
    'use_case',
    'source_viewer_use_case',
    'source_viewer',
    'source_view_use_case',
    'source_view',
    'view_source_use_case',
    'view_source',
    'service',
    'handler',
    'orchestrator',
    'handler_service',
    'container',
    'composition',
    'app',
    'factory',
)
_COMPANY_KEYS = ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
_USER_KEYS = ('user_id', 'userId', 'user', 'uid', 'actor')
_ROLE_KEYS = ('role', 'user_role', 'roleId')
_TRACE_KEYS = ('trace_id', 'traceId', 'trace', 'TraceId')
_TRACE_KEYS = ('trace_id', 'traceId', 'trace', 'TraceId')
_SCOPE_KEYS = ('access_scope', 'accessScope', 'scope', 'AccessScope')
_CATEGORY_KEYS = (
    'document_category',
    'documentCategory',
    'docCategory',
    'doc_category',
    'category',
)
_DOCUMENT_KEYS = ('document_id', 'documentId', 'doc_id', 'docId', 'document', 'docID')
_VERSION_KEYS = (
    'document_version',
    'documentVersion',
    'document_version_id',
    'documentVersionId',
    'version',
    'version_id',
    'versionId',
)
_CHUNK_KEYS = (
    'chunk_id',
    'chunkId',
    'chunkID',
    'chunk',
    'table_id',
    'tableId',
    'tableID',
    'table',
)
_STORAGE_KEY_KEYS = (
    'storage_key',
    'storageKey',
    's3_key',
    's3Key',
    'object_key',
    'objectKey',
    'file_key',
    'fileKey',
    'source_key',
    'sourceKey',
    'storage_path',
    'storagePath',
    's3_path',
    's3Path',
    'object_path',
    'objectPath',
    'path',
    'uri',
)
_PAGE_KEYS = ('page_number', 'pageNumber', 'pageNo', 'PageNumber', 'page', 'page_no')
_TTL_KEYS = (
    'source_original_link_ttl_seconds',
    'sourceOriginalLinkTtlSeconds',
    'ttl_seconds',
    'ttlSeconds',
    'expires_in',
    'expiresIn',
    'ttl',
)
_ORIGINAL_KEYS = ('_original', 'original', 'original_only')

__all__ = [
    '_CATEGORY_KEYS',
    '_CHUNK_KEYS',
    '_CITATION_KEYS',
    '_COMPANY_KEYS',
    '_CONTEXT_KEYS',
    '_DOCUMENT_KEYS',
    '_ORIGINAL_KEYS',
    '_PAGE_KEYS',
    '_PAYLOAD_KEYS',
    '_ROLE_KEYS',
    '_SCOPE_KEYS',
    '_STORAGE_KEY_KEYS',
    '_TRACE_KEYS',
    '_TTL_KEYS',
    '_USER_KEYS',
    '_USE_CASE_KEYS',
    '_VERSION_KEYS',
]
