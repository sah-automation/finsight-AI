#!/usr/bin/env bash
# LocalStack bootstrap for integration tests.
# Creates the S3 buckets, SQS queues, and DynamoDB tables the adapters expect.
# Bucket, queue and table names must match the test profile in config/test.yaml.
set -euo pipefail

BUCKETS=("test-docs" "test-reports" "test-backups")
QUEUES=("ingest" "reprocess" "reports" "dlq")
TABLES=("test-answers" "test-roles" "test-metering")

# CORS rule required for browser presigned uploads direct to S3.
CORS_CONFIG="$(mktemp)"
cat > "${CORS_CONFIG}" <<'EOF'
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*", "http://localhost:3000", "http://127.0.0.1:3000"],
      "AllowedMethods": ["GET", "PUT", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

for bucket in "${BUCKETS[@]}"; do
  awslocal s3 mb "s3://${bucket}" >/dev/null 2>&1 || true
  awslocal s3api put-bucket-cors \
    --bucket "${bucket}" \
    --cors-configuration "file://${CORS_CONFIG}" >/dev/null 2>&1 || true
done

for queue in "${QUEUES[@]}"; do
  awslocal sqs create-queue --queue-name "${queue}" >/dev/null 2>&1 || true
done

# Purge all queues to ensure clean state (idempotent)
for queue in "${QUEUES[@]}"; do
  awslocal sqs purge-queue --queue-url "http://localhost:4566/000000000000/${queue}" >/dev/null 2>&1 || true
done

for table in "${TABLES[@]}"; do
  awslocal dynamodb create-table \
    --table-name "${table}" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null 2>&1 || true
done

rm -f "${CORS_CONFIG}"

echo "LocalStack init complete."
