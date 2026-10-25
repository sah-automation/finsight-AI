#!/usr/bin/env bash
# LocalStack bootstrap for integration tests.
# Creates the S3 buckets, SQS queues, and DynamoDB tables the adapters expect.
set -euo pipefail

BUCKETS=("documents" "reports" "backups")
QUEUES=("ingestion" "reprocessing" "reports" "dlq")
TABLES=("answer_cache" "role_cache" "metering")

for bucket in "${BUCKETS[@]}"; do
  awslocal s3 mb "s3://${bucket}" >/dev/null 2>&1 || true
done

for queue in "${QUEUES[@]}"; do
  awslocal sqs create-queue --queue-name "${queue}" >/dev/null 2>&1 || true
done

for table in "${TABLES[@]}"; do
  awslocal dynamodb create-table \
    --table-name "${table}" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null 2>&1 || true
done

echo "LocalStack init complete."
