import { describe, expect, it } from 'vitest';

import { messages } from '@/lib/messages';
import {
  UploadError,
  extractApiDetail,
  uploadFailureMessage,
} from '@/lib/upload/errors';

describe('upload failure mapping (#233 seam 4)', () => {
  it('maps a network failure to the storage-unreachable message', () => {
    expect(uploadFailureMessage(new TypeError('Failed to fetch'))).toBe(
      messages.upload.storageUnavailable,
    );
  });

  it('maps a rejected or expired presigned link to its own message', () => {
    expect(
      uploadFailureMessage(
        new UploadError({ kind: 'presigned_rejected', status: 403 }),
      ),
    ).toBe(messages.upload.uploadLinkRejected);
    expect(
      uploadFailureMessage(new UploadError({ kind: 'presigned_rejected', status: 410 })),
    ).toBe(messages.upload.uploadLinkRejected);
  });

  it('maps an API error body with a detail to that detail', () => {
    const error = new UploadError({
      kind: 'api_error',
      status: 422,
      detail: 'Period must use the YYYY-QX or YYYY-MM format.',
    });

    expect(uploadFailureMessage(error)).toBe(
      'Period must use the YYYY-QX or YYYY-MM format.',
    );
  });

  it('falls back to the generic message when the API has no usable detail', () => {
    expect(
      uploadFailureMessage(new UploadError({ kind: 'api_error', status: 500 })),
    ).toBe(messages.upload.error);
    expect(
      uploadFailureMessage(
        new UploadError({ kind: 'api_error', status: 500, detail: '   ' }),
      ),
    ).toBe(messages.upload.error);
  });

  it('maps an unrecognised failure to the generic message', () => {
    expect(uploadFailureMessage(new Error('boom'))).toBe(messages.upload.error);
    expect(uploadFailureMessage(null)).toBe(messages.upload.error);
  });

  it('extracts a usable detail without leaking stack output', () => {
    expect(extractApiDetail({ detail: ' Something went wrong. ' })).toBe(
      'Something went wrong.',
    );
    expect(extractApiDetail({ message: 'Short reason.' })).toBe('Short reason.');
    expect(extractApiDetail({ detail: 'Traceback (most recent call last): ...' })).toBeNull();
    expect(extractApiDetail({ detail: 'line one\nline two' })).toBeNull();
    expect(extractApiDetail({ detail: 'x'.repeat(500) })).toBeNull();
    expect(extractApiDetail({ detail: { nested: true } })).toBeNull();
    expect(extractApiDetail(null)).toBeNull();
  });
});
