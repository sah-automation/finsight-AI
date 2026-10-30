import { API_BASE_PATH } from '@/lib/api/client';

export interface SourceViewerHighlight {
  start_char?: number;
  end_char?: number;
  char_start?: number;
  char_end?: number;
  start?: number;
  end?: number;
  s?: number;
  e?: number;
}

export interface SourceViewerTable {
  table_id?: string;
  id?: string;
  page?: number;
  page_number?: number;
  headers?: string[] | null;
  rows?: Array<string[] | Record<string, unknown>> | null;
  data?: unknown;
  text?: string | null;
  needs_review?: boolean;
  [key: string]: unknown;
}

export interface SourceViewerResponse {
  status: 'available' | 'not_available';
  document_id?: string | null;
  document_title?: string | null;
  title?: string | null;
  document_version?: string | number | null;
  version?: string | number | null;
  version_id?: string | null;
  page_number?: number | string | null;
  page?: number | string | null;
  content_type?: 'text' | 'table';
  text?: string | null;
  table?: SourceViewerTable | null;
  tables?: SourceViewerTable[] | null;
  highlight?: SourceViewerHighlight | null;
  needs_review?: boolean;
  newer_version_available?: boolean;
  newer_version_id?: string | null;
  original_available?: boolean;
  original_link?: string | null;
  citation?: string | null;
  citation_locator?: string | null;
  locator?: string | null;
  company_id?: string | null;
  user_id?: string | null;
  role?: string | null;
  trace_id?: string | null;
  outcome?: string;
  result?: string;
  // Document metadata fields
  category?: string | null;
  period?: string | null;
  document_status?: string | null;
}

export interface SourceViewerCitation {
  document_id: string;
  citation_id: string;
  document_title?: string;
  document_version?: string | number;
  page_number?: number | string;
  table_id?: string;
  category?: string | null;
  period?: string | null;
  document_status?: string | null;
}

export interface SourceViewerOriginalResponse {
  status: 'available';
  original_link: string;
  original_available: boolean;
}

export interface AskStatusEvent {
  type: 'status';
  status: string;
}

export interface AskDeltaEvent {
  type: 'delta';
  text: string;
}

export interface AskCitationEvent {
  type: 'citation';
  citation: Record<string, unknown>;
}

export interface AskInsufficientDataEvent {
  type: 'insufficient_data';
  reason: string;
}

export interface AskCompleteEvent {
  type: 'complete';
  threadId?: string;
  answerId?: string;
  cached?: boolean;
  insufficientData?: boolean;
  relatedQuestions?: string[];
  related?: string[];
}

export type AskErrorCode =
  | 'busy'
  | 'permission_denied'
  | 'invalid_request'
  | 'temporarily_unavailable';

export interface AskErrorEvent {
  type: 'error';
  code: AskErrorCode;
}

export type AskEvent =
  | AskStatusEvent
  | AskDeltaEvent
  | AskCitationEvent
  | AskInsufficientDataEvent
  | AskCompleteEvent
  | AskErrorEvent;

export class ApiSessionExpiredError extends Error {
  constructor() {
    super('Session expired');
    this.name = 'ApiSessionExpiredError';
  }
}

export class ApiUnavailableError extends Error {
  constructor() {
    super('Backend unavailable');
    this.name = 'ApiUnavailableError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function text(record: Record<string, unknown>, ...names: string[]): string | undefined {
  for (const name of names) {
    const value = record[name];
    if (typeof value === 'string' && value) {
      return value;
    }
  }
  return undefined;
}

function boolean(record: Record<string, unknown>, ...names: string[]): boolean | undefined {
  for (const name of names) {
    const value = record[name];
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function errorCode(value: unknown): AskErrorCode {
  switch (value) {
    case 'BusyError':
      return 'busy';
    case 'AuthorizationError':
      return 'permission_denied';
    case 'ValidationError':
      return 'invalid_request';
    default:
      return 'temporarily_unavailable';
  }
}

function normalizeEvent(name: string, data: unknown): AskEvent | null {
  const record = isRecord(data) ? data : {};
  switch (name) {
    case 'status': {
      const status = text(record, 'status', 'state');
      return status ? { type: 'status', status } : null;
    }
    case 'delta': {
      const value = text(record, 'delta', 'text', 'content');
      return value ? { type: 'delta', text: value } : null;
    }
    case 'citation': {
      const citation = isRecord(record.citation) ? record.citation : record;
      return Object.keys(citation).length > 0 ? { type: 'citation', citation } : null;
    }
    case 'insufficient_data':
      return {
        type: 'insufficient_data',
        reason: text(record, 'reason', 'message') ?? '',
      };
    case 'complete':
      return {
        type: 'complete',
        threadId: text(record, 'thread_id', 'threadId'),
        answerId: text(record, 'answer_id', 'answerId'),
        cached: boolean(record, 'cached'),
        insufficientData: boolean(record, 'insufficient_data', 'insufficientData'),
        relatedQuestions:
          Array.isArray(record.related_questions)
            ? record.related_questions.filter((item): item is string => typeof item === 'string')
            : Array.isArray(record.relatedQuestions)
              ? record.relatedQuestions.filter((item): item is string => typeof item === 'string')
              : undefined,
        related:
          Array.isArray(record.related)
            ? record.related.filter((item): item is string => typeof item === 'string')
            : undefined,
      };
    case 'error':
      return { type: 'error', code: errorCode(record.code) };
    case 'busy':
      return { type: 'error', code: 'busy' };
    default:
      return null;
  }
}

/** Parses one SSE frame. Unknown or malformed frames are ignored. */
export function parseSseFrame(frame: string): AskEvent | null {
  let eventName = 'message';
  const dataLines: string[] = [];

  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) {
      continue;
    }
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) {
      value = value.slice(1);
    }
    if (field === 'event') {
      eventName = value;
    } else if (field === 'data') {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join('\n'));
  } catch {
    return null;
  }
  return normalizeEvent(eventName, data);
}

/** Reads a verified-sentence SSE stream and emits typed events. */
export async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flushFrames = (): void => {
    buffer = buffer.replace(/\r\n/g, '\n');
    let index = buffer.indexOf('\n\n');
    while (index !== -1) {
      const frame = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const event = parseSseFrame(frame);
      if (event) {
        onEvent(event);
      }
      index = buffer.indexOf('\n\n');
    }
  };

  try {
    while (true) {
      if (signal?.aborted) {
        throw new DOMException('The stream was aborted.', 'AbortError');
      }
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      flushFrames();
    }
    buffer += decoder.decode();
    flushFrames();
    if (buffer.trim()) {
      const event = parseSseFrame(buffer);
      if (event) {
        onEvent(event);
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export interface AskQuestionInput {
  question: string;
  threadId?: string | null;
}

export interface AskStreamOptions {
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  onEvent: (event: AskEvent) => void;
}

export async function streamAskQuestion(
  input: AskQuestionInput,
  options: AskStreamOptions,
): Promise<void> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const response = await fetchImpl(`${API_BASE_PATH}/ask`, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question: input.question,
      ...(input.threadId ? { thread_id: input.threadId } : {}),
    }),
    signal: options.signal,
  });

  if (response.status === 401) {
    throw new ApiSessionExpiredError();
  }
  const contentType = response.headers.get('content-type') ?? '';
  if (!response.ok || !response.body || !contentType.includes('text/event-stream')) {
    throw new ApiUnavailableError();
  }

  await readSseStream(response.body, options.onEvent, options.signal);
}

export async function fetchSourceViewer(
  citation: SourceViewerCitation,
  options?: { signal?: AbortSignal; fetchImpl?: typeof fetch },
): Promise<SourceViewerResponse> {
  const fetchImpl = options?.fetchImpl ?? fetch;
  const response = await fetchImpl(
    `${API_BASE_PATH}/documents/${encodeURIComponent(citation.document_id)}/citations/${encodeURIComponent(citation.citation_id)}/source`,
    {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal: options?.signal,
    },
  );

  if (response.status === 401) {
    throw new ApiSessionExpiredError();
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    if (errorBody?.status === 'not_available') {
      return { status: 'not_available' } as SourceViewerResponse;
    }
    throw new ApiUnavailableError();
  }

  return response.json() as Promise<SourceViewerResponse>;
}

export async function fetchOriginalDocument(
  citation: SourceViewerCitation,
  options?: { signal?: AbortSignal; fetchImpl?: typeof fetch },
): Promise<SourceViewerOriginalResponse> {
  const fetchImpl = options?.fetchImpl ?? fetch;
  const response = await fetchImpl(
    `${API_BASE_PATH}/documents/${encodeURIComponent(citation.document_id)}/citations/${encodeURIComponent(citation.citation_id)}/source/original`,
    {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal: options?.signal,
    },
  );

  if (response.status === 401) {
    throw new ApiSessionExpiredError();
  }
  if (!response.ok) {
    throw new ApiUnavailableError();
  }

  return response.json() as Promise<SourceViewerOriginalResponse>;
}

export async function reportWrongSource(
  citationReference: unknown,
  options?: { signal?: AbortSignal; fetchImpl?: typeof fetch },
): Promise<void> {
  const fetchImpl = options?.fetchImpl ?? fetch;
  const response = await fetchImpl(`${API_BASE_PATH}/report-wrong-source`, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ citation_reference: citationReference }),
    signal: options?.signal,
  });

  if (response.status === 401) {
    throw new ApiSessionExpiredError();
  }
  if (!response.ok) {
    throw new ApiUnavailableError();
  }
}
