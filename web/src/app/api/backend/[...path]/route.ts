import 'server-only';

import { clearSessionCookie, readSessionId } from '@/lib/auth/cookies';
import { getSessionService } from '@/lib/auth/session-factory';
import { BackendUnavailableError, SessionExpiredError } from '@/lib/auth/types';
import { proxyBackendRequest } from '@/lib/backend/proxy';
import { getServerConfig } from '@/lib/config/server-config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

const NO_STORE = { 'Cache-Control': 'no-store' } as const;

function sessionError(error: string, status: number): Response {
  return Response.json({ error }, { status, headers: NO_STORE });
}

async function handle(request: Request, context: RouteContext): Promise<Response> {
  const config = getServerConfig();
  const sessionId = await readSessionId(config);
  if (!sessionId) {
    return sessionError('session_expired', 401);
  }

  let accessToken: string;
  try {
    const record = await getSessionService().resolve(sessionId);
    accessToken = record.accessToken;
  } catch (error) {
    if (error instanceof SessionExpiredError) {
      await clearSessionCookie(config);
      return sessionError('session_expired', 401);
    }
    if (error instanceof BackendUnavailableError) {
      return sessionError('temporarily_unavailable', 503);
    }
    throw error;
  }

  const { path } = await context.params;
  return proxyBackendRequest(request, path, {
    backendApiUrl: config.backendApiUrl,
    timeoutMs: config.backendRequestTimeoutMs,
    accessToken,
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
