import 'server-only';

export interface BackendProxyOptions {
  backendApiUrl: string;
  timeoutMs: number;
  accessToken: string;
  fetchImpl?: typeof fetch;
  extraHeaders?: Headers;
}

const ALLOWED_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']);
const BODY_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const REQUEST_HEADERS = ['accept', 'content-type', 'if-none-match', 'range'];
const RESPONSE_HEADERS = [
  'content-type',
  'cache-control',
  'etag',
  'last-modified',
  'content-disposition',
  'x-request-id',
];

function errorResponse(code: string, status: number): Response {
  return Response.json({ error: code }, { status, headers: { 'Cache-Control': 'no-store' } });
}

/**
 * Builds the upstream URL from untrusted path segments. Rejects anything that
 * could escape the configured backend base path.
 */
export function buildBackendUrl(
  backendApiUrl: string,
  segments: readonly string[],
  search = '',
): string | null {
  if (segments.length === 0) {
    return null;
  }
  for (const segment of segments) {
    if (!segment || segment === '.' || segment === '..' || /[/\\]/.test(segment)) {
      return null;
    }
  }
  const path = segments.map((segment) => encodeURIComponent(segment)).join('/');
  return `${backendApiUrl.replace(/\/+$/, '')}/${path}${search}`;
}

function requestSignal(request: Request, timeoutMs: number, streaming: boolean): AbortSignal {
  if (streaming) {
    return request.signal;
  }
  const timeout = AbortSignal.timeout(timeoutMs);
  return typeof AbortSignal.any === 'function'
    ? AbortSignal.any([request.signal, timeout])
    : timeout;
}

/**
 * Forwards one BFF request to the backend with the session access token. SSE
 * responses are passed through unbuffered so verified sentences arrive live.
 */
export async function proxyBackendRequest(
  request: Request,
  segments: readonly string[],
  options: BackendProxyOptions,
): Promise<Response> {
  const method = request.method.toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    return errorResponse('method_not_allowed', 405);
  }

  const target = buildBackendUrl(options.backendApiUrl, segments, new URL(request.url).search);
  if (!target) {
    return errorResponse('invalid_request', 400);
  }

  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
  headers.set('Authorization', `Bearer ${options.accessToken}`);
  // Forward extra headers (e.g., dev context)
  if (options.extraHeaders) {
    options.extraHeaders.forEach((value, key) => {
      headers.set(key, value);
    });
  }

  const acceptsEventStream = (request.headers.get('accept') ?? '').includes('text/event-stream');
  const init: RequestInit & { duplex?: 'half' } = {
    method,
    headers,
    signal: requestSignal(request, options.timeoutMs, acceptsEventStream),
    redirect: 'manual',
    cache: 'no-store',
  };
  if (BODY_METHODS.has(method) && request.body) {
    init.body = request.body;
    init.duplex = 'half';
  }

  const fetchImpl = options.fetchImpl ?? fetch;
  let upstream: Response;
  try {
    upstream = await fetchImpl(target, init);
  } catch {
    return errorResponse('temporarily_unavailable', 503);
  }

  const responseHeaders = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) {
      responseHeaders.set(name, value);
    }
  }

  const contentType = upstream.headers.get('content-type') ?? '';
  if (contentType.includes('text/event-stream')) {
    responseHeaders.set('Cache-Control', 'no-cache');
    responseHeaders.set('X-Accel-Buffering', 'no');
  } else if (!responseHeaders.has('cache-control')) {
    responseHeaders.set('Cache-Control', 'no-store');
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
