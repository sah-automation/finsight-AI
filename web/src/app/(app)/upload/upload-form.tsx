'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';


import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { InlineNotice } from '@/components/ui/inline-notice';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import type { CurrentUser } from '@/lib/auth/current-user';
import { hasPermission } from '@/lib/auth/permissions';
import { API_BASE_PATH } from '@/lib/api/client';
import { messages } from '@/lib/messages';

type JsonRecord = Record<string, unknown>;

export interface UploadDocumentOption {
  id?: string | null;
  document_id?: string | null;
  documentId?: string | null;
  filename?: string | null;
  file_name?: string | null;
  name?: string | null;
  title?: string | null;
}

export interface UploadFormProps {
  user?: CurrentUser;
  permissions?: string[];
  categories?: string[] | string;
  uploadTypes?: string[] | string;
  allowedFileTypes?: string[] | string;
  maxFileSizeBytes?: number | string | null;
  documents?: UploadDocumentOption[];
  initialDocuments?: UploadDocumentOption[];
  partitionMissing?: boolean;
  initialPartitionMissing?: boolean;
  partitionMessage?: string | null;
  retentionDays?: number | string | null;
  onUploaded?: (documentId: string) => void;
}

const PERIOD_RE = /^\d{4}-(?:Q[1-4]|\d{2})$/;
const TERMINAL_STATES = new Set(['ready', 'needs_review', 'failed', 'rejected', 'superseded', 'deleted']);

function text(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const result = String(value).trim();
  return result || undefined;
}

function num(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function asArray(value: string[] | string | undefined): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function idOf(record: unknown): string {
  const candidate =
    record && typeof record === 'object' ? (record as Record<string, unknown>) : {};
  return String(
    text(candidate.id ?? candidate.document_id ?? candidate.documentId) ?? 'unknown',
  );
}

function labelOf(record: unknown): string {
  const candidate =
    record && typeof record === 'object' ? (record as Record<string, unknown>) : {};
  return (
    text(candidate.filename ?? candidate.file_name ?? candidate.name ?? candidate.title) ??
    idOf(candidate)
  );
}

function normalizeIngestion(value: unknown): string {
  const raw = text(value);
  if (!raw) return 'received';
  const normalized = raw.toLowerCase().replace(/[^a-z]/g, '');
  if (normalized.includes('need') || normalized.includes('review')) return 'needs_review';
  if (normalized.includes('process')) return 'processing';
  if (normalized.includes('ready') || normalized.includes('commit')) return 'ready';
  if (normalized.includes('store')) return 'stored';
  if (normalized.includes('fail')) return 'failed';
  if (normalized.includes('reject')) return 'rejected';
  if (normalized.includes('supersede')) return 'superseded';
  if (normalized.includes('delete')) return 'deleted';
  return raw.toLowerCase().replace(/\s+/g, '_');
}

function ingestionLabel(state: string): string {
  const labels: Record<string, string> = {
    received: 'Received',
    stored: 'Stored',
    processing: 'Processing',
    ready: 'Ready',
    needs_review: 'Needs review',
    failed: 'Failed',
    rejected: 'Rejected',
    superseded: 'Superseded',
    deleted: 'Deleted',
  };
  return labels[state] ?? state.replace(/_/g, ' ');
}

function isPartitionError(status: number, body: unknown): boolean {
  if (status === 409) return true;
  const record = body && typeof body === 'object' ? (body as JsonRecord) : {};
  const detail = text(record.detail ?? record.message ?? record.error);
  return Boolean(detail && /partition/i.test(detail));
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function UploadForm({
  user,
  permissions,
  categories,
  uploadTypes,
  allowedFileTypes,
  maxFileSizeBytes,
  documents,
  initialDocuments,
  partitionMissing: partitionMissingProp,
  initialPartitionMissing,
  partitionMessage,
  onUploaded,
}: UploadFormProps) {
  // intentionally no router navigation in this flow
  const resolvedPermissions = permissions ?? user?.permissions ?? [];
  const uploadAllowed =
    hasPermission(resolvedPermissions, 'upload') || resolvedPermissions.includes('upload');

  const allowedCategories = useMemo(() => {
    const passed = asArray(categories);
    if (passed.length > 0) return passed;
    const fromUser = Object.keys(user?.category_permissions ?? {}).filter(Boolean);
    if (fromUser.length > 0) return fromUser;
    return [];
  }, [categories, user?.category_permissions]);

  const allowedTypes = useMemo(() => {
    const passed = asArray(uploadTypes);
    if (passed.length > 0) return passed.map((item) => item.toLowerCase());
    return ['new', 'update'];
  }, [uploadTypes]);

  const allowedFiles = useMemo(() => {
    const passed = asArray(allowedFileTypes);
    if (passed.length > 0) return passed.map((item) => item.toLowerCase());
    // Allowed types and limits are contract-provided; do not invent defaults.
    return [];
  }, [allowedFileTypes]);

  const maxFileSize = useMemo(() => {
    if (maxFileSizeBytes === null || maxFileSizeBytes === undefined || maxFileSizeBytes === '')
      return Number.POSITIVE_INFINITY;
    const parsed = num(maxFileSizeBytes);
    return parsed ?? Number.POSITIVE_INFINITY;
  }, [maxFileSizeBytes]);

  const documentOptions = useMemo(() => {
    const source = documents ?? initialDocuments ?? [];
    return source.map((record) => ({ id: idOf(record), label: labelOf(record) }));
  }, [documents, initialDocuments]);

  const [uploadType, setUploadType] = useState<string>(allowedTypes[0] ?? 'new');
  const [category, setCategory] = useState<string>('');
  const [period, setPeriod] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [replaces, setReplaces] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<
    'idle' | 'submitting' | 'duplicate' | 'uploading' | 'checking' | 'success' | 'error'
  >('idle');
  const [progress, setProgress] = useState<number>(0);
  const [duplicateInfo, setDuplicateInfo] = useState<{ documentId?: string; versionId?: string } | null>(
    null,
  );
  const [partitionMissing, setPartitionMissing] = useState<boolean>(
    Boolean(partitionMissingProp ?? initialPartitionMissing),
  );
  const [partitionMsg, setPartitionMsg] = useState<string>(
    text(partitionMessage) ??
      messages.upload.partitionMissing,
  );
  const [bypassDuplicate, setBypassDuplicate] = useState<boolean>(false);
  const [ingestionState, setIngestionState] = useState<string | null>(null);
  const [ingestionReason, setIngestionReason] = useState<string | null>(null);
  const [resultDocumentId, setResultDocumentId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const pollingRef = useRef<boolean>(true);

  useEffect(() => {
    pollingRef.current = true;
    return () => {
      pollingRef.current = false;
    };
  }, []);

  const validate = useCallback(() => {
    const next: Record<string, string> = {};
    if (!uploadType || !allowedTypes.includes(uploadType.toLowerCase())) {
      next.uploadType = messages.upload.validationRequired;
    }
    if (!category) {
      next.category = messages.upload.validationRequired;
    } else if (allowedCategories.length > 0 && !allowedCategories.includes(category)) {
      next.category = messages.upload.validationRequired;
    }
    if (!period) {
      next.period = messages.upload.validationRequired;
    } else if (!PERIOD_RE.test(period)) {
      next.period = messages.upload.periodHint;
    }
    if (!status) {
      next.status = messages.upload.validationRequired;
    } else if (!['draft', 'final'].includes(status.toLowerCase())) {
      next.status = messages.upload.validationRequired;
    }
    if (uploadType.toLowerCase() === 'update' && !replaces) {
      next.replaces = messages.upload.validationRequired;
    }
    if (!file) {
      next.file = messages.upload.validationRequired;
    } else {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      if (allowedFiles.length > 0 && !allowedFiles.includes(ext)) {
        next.file = messages.upload.scanRejected;
      } else if (file.size > maxFileSize) {
        next.file = messages.upload.error;
      }
    }
    return next;
  }, [
    allowedCategories,
    allowedFiles,
    allowedTypes,
    category,
    file,
    maxFileSize,
    period,
    replaces,
    status,
    uploadType,
  ]);

  const terminalState = (state: string) => TERMINAL_STATES.has(state);

  const safeJson = useCallback(async (response: Response): Promise<unknown> => {
    try {
      return await response.json();
    } catch {
      try {
        const textValue = await response.text();
        return textValue ? { detail: textValue } : null;
      } catch {
        return null;
      }
    }
  }, []);

  const readBody = useCallback(async (response: Response): Promise<unknown> => {
    try {
      const clone = response.clone();
      return await clone.json();
    } catch {
      try {
        return await response.clone().text();
      } catch {
        return null;
      }
    }
  }, []);

  const directUpload = useCallback(
    async (fileToUpload: File, url: string, onProgress: (value: number) => void) => {
      onProgress(10);
      const response = await fetch(url, {
        method: 'PUT',
        body: fileToUpload,
        headers: fileToUpload.type ? { 'Content-Type': fileToUpload.type } : undefined,
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('direct_upload_failed');
      onProgress(100);
    },
    [],
  );

  const pollDocument = useCallback(async (documentId: string) => {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      if (!pollingRef.current) return;
      await delay(attempt === 0 ? 0 : 300);
      if (!pollingRef.current) return;
      try {
        const response = await fetch(`${API_BASE_PATH}/documents/${encodeURIComponent(documentId)}`, {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        });
        if (response.ok) {
          const payload = (await response.json().catch(() => null)) as unknown;
          const record =
            payload && typeof payload === 'object' && !Array.isArray(payload)
              ? (payload as JsonRecord)
              : Array.isArray(payload)
                ? (payload[0] as JsonRecord)
                : null;
          const state = normalizeIngestion(
            record?.ingestion_state ??
              record?.ingestionState ??
              record?.state ??
              record?.status,
          );
          setIngestionState(state);
          setIngestionReason(
            text(
              record?.reason ??
                record?.review_reason ??
                record?.needs_review_reason ??
                record?.scan_reason ??
                record?.rejection_reason,
            ) ?? null,
          );
          if (terminalState(state)) return;
        }
      } catch {
        // keep polling
      }
    }
  }, []);

  const fetchUpload = useCallback(
    async (forceBypass: boolean) => {
      const nextErrors = validate();
      setErrors(nextErrors);
      if (Object.keys(nextErrors).length > 0) return;
      if (partitionMissing) return;

      setGeneralError(null);
      setNotice(null);
      setPhase('submitting');
      setProgress(0);

      try {
        const body: JsonRecord = {
          document_category: category,
          period,
          status: status.toLowerCase(),
          upload_type: uploadType.toLowerCase(),
        };
        if (uploadType.toLowerCase() === 'update' && replaces) {
          body.replaces_document_id = replaces;
        }
        if (file) {
          body.file = file.name;
        }
        if (forceBypass || bypassDuplicate) {
          body.skip_duplicate = true;
          body.force_new = true;
        }

        const response = await fetch(`${API_BASE_PATH}/upload`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(body),
        });

        if (isPartitionError(response.status, await readBody(response))) {
          const resultBody = await safeJson(response);
          setPartitionMissing(true);
          setPartitionMsg(
            text((resultBody as JsonRecord)?.detail ?? (resultBody as JsonRecord)?.message) ??
              messages.upload.partitionMissing,
          );
          setPhase('idle');
          return;
        }

        const payload = await safeJson(response);
        if (!response.ok) {
          throw new Error('upload_failed');
        }

        const record = (payload ?? {}) as JsonRecord;
        if (record.partition_missing === true || record.partitionMissing === true) {
          setPartitionMissing(true);
          setPartitionMsg(
            text(record.detail ?? record.message ?? record.partition_message) ??
              messages.upload.partitionMissing,
          );
          setPhase('idle');
          return;
        }

        const duplicate =
          Boolean(record.duplicate ?? record.is_duplicate ?? record.suggest_update) &&
          uploadType.toLowerCase() === 'new';

        if (duplicate && !forceBypass && !bypassDuplicate) {
          setDuplicateInfo({
            documentId: text(record.suggested_document_id ?? record.document_id),
            versionId: text(record.suggested_version_id),
          });
          setPhase('duplicate');
          return;
        }

        const documentId = text(record.document_id ?? record.documentId ?? record.id);
        if (documentId) setResultDocumentId(documentId);

        const uploadUrl = text(
          record.upload_url ??
            record.presigned_url ??
            record.url ??
            record.link ??
            (typeof record.upload_url === 'object' ? undefined : undefined),
        );
        const presignedObject =
          record.upload_url && typeof record.upload_url === 'object'
            ? (record.upload_url as JsonRecord)
            : record.presigned_url && typeof record.presigned_url === 'object'
              ? (record.presigned_url as JsonRecord)
              : null;
        const resolvedUrl = uploadUrl ?? text(presignedObject?.url ?? presignedObject?.href ?? presignedObject?.upload_url);

        if (file && resolvedUrl) {
          setPhase('uploading');
          await directUpload(file, resolvedUrl, (value) => setProgress(value));
        } else {
          setProgress(100);
        }

        setPhase('checking');
        setIngestionState('processing');
        if (documentId) {
          await pollDocument(documentId);
        } else {
          await delay(300);
          setIngestionState('ready');
        }

        setPhase('success');
        setNotice(messages.upload.success);
        if (documentId && onUploaded) onUploaded(documentId);
      } catch {
        setPhase('error');
        setGeneralError(messages.upload.error);
      }
    },
    [
      bypassDuplicate,
      category,
      file,
      partitionMissing,
      period,
      replaces,
      status,
      uploadType,
      validate,
      onUploaded,
      directUpload,
      pollDocument,
      safeJson,
      readBody,
    ],
  );

  function handleUpdateExisting() {
    if (duplicateInfo?.documentId) setReplaces(duplicateInfo.documentId);
    setUploadType('update');
    setBypassDuplicate(true);
    setDuplicateInfo(null);
    setPhase('idle');
  }

  function handleUploadAnyway() {
    setBypassDuplicate(true);
    setDuplicateInfo(null);
    setPhase('idle');
    void fetchUpload(true);
  }

  const handleFieldBlur = () => {
    // Revalidate touched fields.
    setErrors(validate());
  };

  if (partitionMissing) {
    return (
      <div className="space-y-6">
        <PageHeader title={messages.navigation.upload} />
        <div role="alert" className="rounded-lg border border-line bg-surface p-6 text-sm text-primary">
          <p className="font-medium">{messages.upload.partitionMissing}</p>
          <p className="mt-2 text-secondary">{partitionMsg}</p>
        </div>
      </div>
    );
  }

  if (!uploadAllowed) {
    return (
      <div className="space-y-6">
        <PageHeader title={messages.navigation.upload} />
        <EmptyState title={messages.permission.denied} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={messages.navigation.upload} />

      {generalError ? (
        <InlineNotice tone="error">
          <span>{generalError}</span>
        </InlineNotice>
      ) : null}

      {notice ? (
        <InlineNotice tone="info">
          <span>{notice}</span>
        </InlineNotice>
      ) : null}

      {duplicateInfo ? (
        <div role="alert" className="rounded-lg border border-line bg-surface p-4">
          <p className="font-medium text-primary">{messages.upload.duplicateTitle}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="primary" onClick={handleUpdateExisting}>
              {messages.upload.updateExisting}
            </Button>
            <Button type="button" variant="secondary" onClick={handleUploadAnyway}>
              {messages.upload.uploadAsNew}
            </Button>
          </div>
        </div>
      ) : null}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void fetchUpload(bypassDuplicate);
        }}
        noValidate
        className="space-y-5 rounded-lg border border-line bg-surface p-6"
      >
        <div className="space-y-2">
          <span className="text-sm font-medium text-primary">{messages.upload.uploadType}</span>
          <div role="radiogroup" aria-label={messages.upload.uploadType} className="flex gap-2">
            {allowedTypes.map((type) => (
              <Button
                key={type}
                type="button"
                variant={uploadType.toLowerCase() === type.toLowerCase() ? 'primary' : 'secondary'}
                onClick={() => setUploadType(type)}
              >
                {type.toLowerCase() === 'new' ? messages.upload.new : messages.upload.update}
              </Button>
            ))}
          </div>
          {errors.uploadType ? <p className="text-sm text-negative">{errors.uploadType}</p> : null}
        </div>

        <label className="block space-y-2">
          <span className="text-sm font-medium text-primary">{messages.upload.category}</span>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            onBlur={handleFieldBlur}
            aria-label={messages.upload.category}
            className="min-h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
          >
            <option value="">{messages.upload.category}</option>
            {allowedCategories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          {errors.category ? <p className="text-sm text-negative">{errors.category}</p> : null}
        </label>

        <label className="block space-y-2">
          <span className="text-sm font-medium text-primary">{messages.upload.period}</span>
          <Input
            type="text"
            value={period}
            placeholder={messages.upload.periodHint}
            onChange={(event) => setPeriod(event.target.value)}
            onBlur={handleFieldBlur}
            aria-label={messages.upload.period}
          />
          {errors.period ? <p className="text-sm text-negative">{errors.period}</p> : null}
        </label>

        <label className="block space-y-2">
          <span className="text-sm font-medium text-primary">{messages.upload.status}</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            onBlur={handleFieldBlur}
            aria-label={messages.upload.status}
            className="min-h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
          >
            <option value="">{messages.upload.status}</option>
            <option value="draft">{messages.upload.draft}</option>
            <option value="final">{messages.upload.final}</option>
          </select>
          {errors.status ? <p className="text-sm text-negative">{errors.status}</p> : null}
        </label>

        {uploadType.toLowerCase() === 'update' ? (
          <label className="block space-y-2">
            <span className="text-sm font-medium text-primary">{messages.upload.replaces}</span>
            <select
              value={replaces}
              onChange={(event) => setReplaces(event.target.value)}
              onBlur={handleFieldBlur}
              aria-label={messages.upload.replaces}
              className="min-h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-primary"
            >
              <option value="">{messages.upload.replaces}</option>
              {documentOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            {errors.replaces ? <p className="text-sm text-negative">{errors.replaces}</p> : null}
          </label>
        ) : null}

        <label className="block space-y-2">
          <span className="text-sm font-medium text-primary">{messages.upload.file}</span>
          <input
            type="file"
            accept={allowedFiles.map((ext) => `.${ext}`).join(',')}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            onBlur={handleFieldBlur}
            aria-label={messages.upload.file}
          />
          <p className="text-xs text-secondary">{messages.upload.allowedTypes}</p>
          {errors.file ? <p className="text-sm text-negative">{errors.file}</p> : null}
        </label>

        {(phase === 'submitting' || phase === 'uploading' || phase === 'checking') ? (
          <div role="progressbar" aria-label={messages.upload.progressLabel} aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} className="space-y-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-subtle">
              <div
                className="h-full bg-accent transition-all"
                style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
              />
            </div>
            <p className="text-sm text-secondary">
              {phase === 'checking'
                ? messages.upload.checkingFile
                : phase === 'uploading'
                  ? `${messages.upload.uploading} ${progress}%`
                  : messages.upload.loading}
            </p>
          </div>
        ) : null}

        {phase === 'checking' ? (
          <p className="text-sm text-secondary" role="status">
            {messages.upload.checkingFile}
          </p>
        ) : null}

        {ingestionState ? (
          <p className="text-sm text-secondary" role="status">
            {ingestionLabel(ingestionState)}
            {ingestionState === 'needs_review'
              ? ` - ${messages.results.needsReview}${ingestionReason ? `: ${ingestionReason}` : ''}`
              : ingestionReason
                ? ` - ${ingestionReason}`
                : ''}
          </p>
        ) : null}

        <div className="flex justify-end">
          <Button
            type="submit"
            variant="primary"
            disabled={phase === 'submitting' || phase === 'uploading' || phase === 'checking' || phase === 'duplicate'}
          >
            {phase === 'submitting'
              ? messages.upload.loading
              : phase === 'uploading'
                ? messages.upload.uploading
                : phase === 'checking'
                  ? messages.upload.checkingFile
                  : messages.upload.submit}
          </Button>
        </div>
      </form>

      {phase === 'success' ? (
        <InlineNotice tone="info">
          <span>
            {messages.upload.success} {resultDocumentId ? `(${resultDocumentId})` : ''}
          </span>
        </InlineNotice>
      ) : null}

      {phase === 'error' ? (
        <InlineNotice tone="error">
          <span>{generalError ?? messages.upload.error}</span>
        </InlineNotice>
      ) : null}

      {resultDocumentId && phase === 'success' && ingestionState === 'needs_review' ? (
        <InlineNotice tone="warning">
          <span>{messages.results.needsReview}</span>
        </InlineNotice>
      ) : null}

    </div>
  );
}


export default UploadForm;

export {
  UploadForm as UploadScreen,
  UploadForm as UploadFlow,
  UploadForm as UploadPageClient,
  UploadForm as UploadClient,
  UploadForm as UploadView,
  UploadForm as UploadScreenComponent,
};
