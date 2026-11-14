import { describe, expect, it, vi } from 'vitest';

import { buildBackendUrl, proxyBackendRequest } from '@/lib/backend/proxy';

function options(fetchImpl: typeof fetch) {
  return {
    backendApiUrl: 'https://api.example.com',
    timeoutMs: 1_000,
    accessToken: 'access-token',
    fetchImpl,
  };
}

describe('buildBackendUrl', () => {
  it('joins encoded path segments and keeps the query string', () => {
    expect(buildBackendUrl('https://api.example.com/', ['documents', 'a b'], '?q=1')).toBe(
      'https://api.example.com/documents/a%20b?q=1',
    );
  });

  it('rejects empty requests and path traversal', () => {
    expect(buildBackendUrl('https://api.example.com', [])).toBeNull();
    expect(buildBackendUrl('https://api.example.com', ['..', 'me'])).toBeNull();
    expect(buildBackendUrl('https://api.example.com', ['.'])).toBeNull();
    expect(buildBackendUrl('https://api.example.com', ['a/b'])).toBeNull();
    expect(buildBackendUrl('https://api.example.com', ['a\\b'])).toBeNull();
  });
});

describe('proxyBackendRequest', () => {
  it('attaches the access token and forwards method, query and body', async () => {
    const fetchImpl = vi.fn(async (_url: string, init: RequestInit) => {
      expect(await new Response(init.body).text()).toBe('{"question":"hi"}');
      return Response.json({ ok: true }, { headers: { 'x-request-id': 'request-1' } });
    });
    const request = new Request('http://localhost:3000/api/backend/ask?stream=1', {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ question: 'hi' }),
    });

    const response = await proxyBackendRequest(
      request,
      ['ask'],
      options(fetchImpl as unknown as typeof fetch),
    );

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.example.com/ask?stream=1');
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer access-token');
    expect(new Headers(init.headers).get('content-type')).toBe('application/json');
    expect(response.status).toBe(200);
    expect(response.headers.get('x-request-id')).toBe('request-1');
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(await response.json()).toEqual({ ok: true });
  });

  it('passes SSE responses through unbuffered', async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: delta\ndata: {"text":"Hello"}\n\n'));
        controller.close();
      },
    });
    const fetchImpl = vi.fn(
      async () =>
        new Response(body, {
          status: 200,
          headers: { 'content-type': 'text/event-stream' },
        }),
    );
    const request = new Request('http://localhost:3000/api/backend/ask', {
      method: 'POST',
      headers: { accept: 'text/event-stream', 'content-type': 'application/json' },
      body: '{}',
    });

    const response = await proxyBackendRequest(
      request,
      ['ask'],
      options(fetchImpl as unknown as typeof fetch),
    );

    expect(response.headers.get('content-type')).toContain('text/event-stream');
    expect(response.headers.get('cache-control')).toBe('no-cache');
    expect(response.headers.get('x-accel-buffering')).toBe('no');
    expect(await response.text()).toContain('event: delta');
  });

  it('returns approved errors for bad paths, methods and outages', async () => {
    const request = new Request('http://localhost:3000/api/backend/me');
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('network down');
    });

    const invalid = await proxyBackendRequest(
      request,
      ['..', 'me'],
      options(fetchImpl as unknown as typeof fetch),
    );
    expect(invalid.status).toBe(400);
    expect(await invalid.json()).toEqual({ error: 'invalid_request' });

    const method = await proxyBackendRequest(
      new Request('http://localhost:3000/api/backend/me', { method: 'OPTIONS' }),
      ['me'],
      options(fetchImpl as unknown as typeof fetch),
    );
    expect(method.status).toBe(405);

    const outage = await proxyBackendRequest(
      request,
      ['me'],
      options(fetchImpl as unknown as typeof fetch),
    );
    expect(outage.status).toBe(503);
    expect(await outage.json()).toEqual({ error: 'temporarily_unavailable' });
  });
});
