import 'server-only';

import { writeSessionCookie } from '@/lib/auth/cookies';
import { getSessionService } from '@/lib/auth/session-factory';
import {
  mapSignInError,
  parseSignInCredentials,
  signInWithService,
} from '@/lib/auth/sign-in';
import { getServerConfig } from '@/lib/config/server-config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_BODY_BYTES = 8_192;

function jsonError(code: string, status: number): Response {
  return Response.json(
    { error: code },
    { status, headers: { 'Cache-Control': 'no-store' } },
  );
}

export async function POST(request: Request): Promise<Response> {
  const contentLength = Number(request.headers.get('content-length') ?? '0');
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return jsonError('invalid_request', 400);
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return jsonError('invalid_request', 400);
  }

  const credentials = parseSignInCredentials(payload);
  if (!credentials) {
    return jsonError('invalid_request', 400);
  }

  const config = getServerConfig();
  try {
    const outcome = await signInWithService(getSessionService(), credentials);
    await writeSessionCookie(config, outcome.sessionId);
    return Response.json(
      { redirectTo: outcome.redirectTo },
      { status: 200, headers: { 'Cache-Control': 'no-store' } },
    );
  } catch (error) {
    const failure = mapSignInError(error);
    return jsonError(failure.code, failure.status);
  }
}
