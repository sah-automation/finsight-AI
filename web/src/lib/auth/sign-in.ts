import 'server-only';

import { BackendUnavailableError, SignInError } from '@/lib/auth/types';
import type { SessionService } from '@/lib/auth/session-service';
import { landingPath } from '@/lib/auth/permissions';
import type { SignInErrorCode } from '@/lib/messages';

export interface SignInCredentials {
  email: string;
  password: string;
}

export interface SignInOutcome {
  sessionId: string;
  redirectTo: string;
}

export interface SignInFailure {
  code: SignInErrorCode;
  status: number;
}

const MAX_EMAIL_LENGTH = 320;
const MAX_PASSWORD_LENGTH = 1_024;

export function parseSignInCredentials(payload: unknown): SignInCredentials | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const email = typeof record.email === 'string' ? record.email.trim() : '';
  const password = typeof record.password === 'string' ? record.password : '';
  if (
    !email ||
    !password ||
    email.length > MAX_EMAIL_LENGTH ||
    password.length > MAX_PASSWORD_LENGTH ||
    !email.includes('@')
  ) {
    return null;
  }
  return { email, password };
}

const statusByCode: Record<SignInErrorCode, number> = {
  invalid_request: 400,
  invalid_credentials: 401,
  account_locked: 423,
  account_not_confirmed: 403,
  password_reset_required: 403,
  temporarily_unavailable: 503,
};

export function mapSignInError(error: unknown): SignInFailure {
  if (error instanceof SignInError) {
    return { code: error.code, status: statusByCode[error.code] };
  }
  if (error instanceof BackendUnavailableError) {
    return { code: 'temporarily_unavailable', status: 503 };
  }
  return { code: 'temporarily_unavailable', status: 503 };
}

export async function signInWithService(
  service: SessionService,
  credentials: SignInCredentials,
): Promise<SignInOutcome> {
  const session = await service.signIn(credentials.email, credentials.password);
  return {
    sessionId: session.sessionId,
    redirectTo: landingPath(session.user.permissions ?? []),
  };
}
