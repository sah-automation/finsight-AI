import { describe, expect, it, vi } from 'vitest';

import {
  ApiSessionExpiredError,
  ApiUnavailableError,
  fetchSourceViewer,
  parseSseFrame,
  readSseStream,
  streamAskQuestion,
  type AskEvent,
} from '@/lib/api/events';

describe('parseSseFrame', () => {
  it('maps verified-sentence events to typed shapes', () => {
    expect(parseSseFrame('event: status\ndata: {"status":"searching"}')).toEqual({
      type: 'status',
      status: 'searching',
    });
    expect(parseSseFrame('event: delta\ndata: {"delta":"Hello"}')).toEqual({
      type: 'delta',
      text: 'Hello',
    });
    expect(
      parseSseFrame('event: citation\ndata: {"citation":{"document_id":"d1","page":2}}'),
    ).toEqual({
      type: 'citation',
      citation: { document_id: 'd1', page: 2 },
    });
    expect(
      parseSseFrame('event: insufficient_data\ndata: {"reason":"no evidence"}'),
    ).toEqual({ type: 'insufficient_data', reason: 'no evidence' });
    expect(
      parseSseFrame(
        'event: complete\ndata: {"done":true,"thread_id":"t1","answer_id":"a1","cached":false}',
      ),
    ).toEqual({
      type: 'complete',
      threadId: 't1',
      answerId: 'a1',
      cached: false,
      insufficientData: undefined,
    });
  });

  it('maps backend error classes to approved client codes', () => {
    expect(parseSseFrame('event: error\ndata: {"code":"BusyError","message":"raw"}')).toEqual({
      type: 'error',
      code: 'busy',
    });
    expect(
      parseSseFrame('event: error\ndata: {"code":"AuthorizationError","message":"raw"}'),
    ).toEqual({ type: 'error', code: 'permission_denied' });
    expect(
      parseSseFrame('event: error\ndata: {"code":"ProviderError","message":"raw"}'),
    ).toEqual({ type: 'error', code: 'temporarily_unavailable' });
  });

  it('ignores comments, unknown events and malformed data', () => {
    expect(parseSseFrame(': keep-alive')).toBeNull();
    expect(parseSseFrame('event: mystery\ndata: {"x":1}')).toBeNull();
    expect(parseSseFrame('event: delta\ndata: not-json')).toBeNull();
    expect(parseSseFrame('event: delta\ndata:')).toBeNull();
  });

  it('joins multi-line data fields', () => {
    expect(parseSseFrame('event: delta\ndata: {"text":\ndata: "Hello"}')).toEqual({
      type: 'delta',
      text: 'Hello',
    });
  });
});

describe('readSseStream', () => {
  it('handles frames split across chunks and CRLF line endings', async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'event: status\r\ndata: {"status":"answering"}\r\n\r',
      '\nevent: delta\ndata: {"delta":"Hello"}\n\n',
      'event: complete\ndata: {"done":true}\n',
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    const events: AskEvent[] = [];
    await readSseStream(stream, (event) => events.push(event));

    expect(events).toEqual([
      { type: 'status', status: 'answering' },
      { type: 'delta', text: 'Hello' },
      { type: 'complete', threadId: undefined, answerId: undefined, cached: undefined, insufficientData: undefined },
    ]);
  });
});

describe('streamAskQuestion', () => {
  it('posts to the BFF and emits typed events', async () => {
    const encoder = new TextEncoder();
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(encoder.encode('event: delta\ndata: {"delta":"OK"}\n\n'));
              controller.close();
            },
          }),
          { status: 200, headers: { 'content-type': 'text/event-stream' } },
        ),
    );

    const events: AskEvent[] = [];
    await streamAskQuestion(
      { question: 'What changed?', threadId: 'thread-1' },
      { fetchImpl: fetchImpl as unknown as typeof fetch, onEvent: (event) => events.push(event) },
    );

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/backend/ask');
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Accept')).toBe('text/event-stream');
    expect(JSON.parse(String(init.body))).toEqual({
      question: 'What changed?',
      thread_id: 'thread-1',
    });
    expect(events).toEqual([{ type: 'delta', text: 'OK' }]);
  });

  it('maps expired sessions and non-stream failures to client errors', async () => {
    const expired = vi.fn(async () => Response.json({ error: 'session_expired' }, { status: 401 }));
    await expect(
      streamAskQuestion(
        { question: 'q' },
        { fetchImpl: expired as unknown as typeof fetch, onEvent: () => undefined },
      ),
    ).rejects.toBeInstanceOf(ApiSessionExpiredError);

    const unavailable = vi.fn(
      async () => new Response('nope', { status: 502, headers: { 'content-type': 'text/plain' } }),
    );
    await expect(
      streamAskQuestion(
        { question: 'q' },
        { fetchImpl: unavailable as unknown as typeof fetch, onEvent: () => undefined },
      ),
    ).rejects.toBeInstanceOf(ApiUnavailableError);
  });
});


describe('fetchSourceViewer', () => {
  const CITATION = { document_id: 'doc-1', citation_id: 'cite-1' };

  it('normalizes unauthorized and unavailable statuses to not_available', async () => {
    for (const status of [403, 404, 410]) {
      const fetchImpl = vi.fn(async () => new Response(null, { status }));
      await expect(fetchSourceViewer(CITATION, { fetchImpl: fetchImpl as unknown as typeof fetch })).resolves.toEqual({
        status: 'not_available',
      });
    }
  });

  it('throws ApiSessionExpiredError on 401', async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 401 }));
    await expect(fetchSourceViewer(CITATION, { fetchImpl: fetchImpl as unknown as typeof fetch })).rejects.toBeInstanceOf(
      ApiSessionExpiredError,
    );
  });

  it('throws ApiUnavailableError on other failures', async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 500 }));
    await expect(fetchSourceViewer(CITATION, { fetchImpl: fetchImpl as unknown as typeof fetch })).rejects.toBeInstanceOf(
      ApiUnavailableError,
    );
  });

  it('returns the parsed payload on success', async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ status: 'available', text: 'verified' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    const result = await fetchSourceViewer(CITATION, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    expect(result).toMatchObject({ status: 'available', text: 'verified' });
  });
});
