# Storage Adapter

S3 object storage.

**Implements:** `StoragePort` (upload, download, presign, delete)

**Belongs here:**
- `S3Storage` - boto3 wrapper
- Multipart upload for large files
- Presigned URL generation
- Lifecycle policy helpers

**Does not belong here:**
- File format logic (that's readers/)
- Business logic about what to store
