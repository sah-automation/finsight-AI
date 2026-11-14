import { messages } from '@/lib/messages';

/**
 * A failure captured while uploading a document.
 *
 * This module is intentionally pure: no React, no fetch, no browser globals.
 * The upload form classifies its failure into one of these kinds and the
 * mapping decides the message.
 */
export type UploadFailure =
  | { kind: 'storage_unreachable' }
  | { kind: 'presigned_rejected'; status?: number }
  | { kind: 'api_error'; status?: number; detail?: unknown }
  | { kind: 'unknown' };

export class UploadError extends Error {
  readonly failure: UploadFailure;

  constructor(failure: UploadFailure) {
    super(failure.kind);
    this.name = 'UploadError';
    this.failure = failure;
  }
}

const MAX_DETAIL_LENGTH = 280;

/**
 * Return a server-provided detail only when it is safe to show as one short
 * sentence. Stack traces, multi-line payloads and overlong bodies fall back to
 * the generic upload message.
 */
export function extractApiDetail(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  const record = body as Record<string, unknown>;
  const candidate = record.detail ?? record.message ?? record.error;
  if (typeof candidate !== 'string') return null;

  const detail = candidate.trim();
  if (!detail || detail.length > MAX_DETAIL_LENGTH) return null;
  if (/[\r\n]/.test(detail)) return null;
  if (/(?:traceback|stack trace|at\s+\S+\s+\(.+:\d+\))/i.test(detail)) return null;

  return detail;
}

function failureOf(error: unknown): UploadFailure {
  if (error instanceof UploadError) return error.failure;
  // Network errors from fetch: TypeError (most browsers), DOMException/AbortError (some)
  if (error instanceof TypeError && /^(Failed to fetch|NetworkError)/i.test(error.message)) {
    return { kind: 'storage_unreachable' };
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    // Request was aborted (user navigated away, component unmounted)
    return { kind: 'unknown' }; // Not a storage issue, don't show misleading message
  }
  if (error instanceof DOMException && /network|cors/i.test(error.message)) {
    return { kind: 'storage_unreachable' };
  }
  return { kind: 'unknown' };
}

/** Map any upload failure to the single approved message for that cause. */
export function uploadFailureMessage(error: unknown): string {
  const failure = failureOf(error);

  switch (failure.kind) {
    case 'storage_unreachable':
      return messages.upload.storageUnavailable;
    case 'presigned_rejected':
      return messages.upload.uploadLinkRejected;
    case 'api_error':
      return extractApiDetail({ detail: failure.detail }) ?? messages.upload.error;
    case 'unknown':
      return messages.upload.error;
  }
}
