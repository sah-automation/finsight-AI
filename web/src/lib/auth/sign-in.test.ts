import { describe, expect, it, vi } from 'vitest';

import type { CurrentUser } from '@/lib/auth/current-user';
import {
  mapSignInError,
  parseSignInCredentials,
  signInWithService,
} from '@/lib/auth/sign-in';
import type { SessionService } from '@/lib/auth/session-service';
import { BackendUnavailableError, SignInError } from '@/lib/auth/types';

function user(permissions: string[]): CurrentUser {
  return {
    company_id: 'company-1',
    company_name: 'Acme',
    company_display_name: 'Acme',
    role: 'system_admin',
    role_id: 'system_admin',
    role_name: 'System Admin',
    permissions,
    category_permissions: {},
  };
}

describe('sign-in request handling', () => {
  it('accepts a trimmed email and password', () => {
    expect(parseSignInCredentials({ email: ' user@example.com ', password: 'secret' })).toEqual({
      email: 'user@example.com',
      password: 'secret',
    });
  });

  it('rejects missing, malformed or oversized credentials', () => {
    expect(parseSignInCredentials(null)).toBeNull();
    expect(parseSignInCredentials({ email: '', password: 'secret' })).toBeNull();
    expect(parseSignInCredentials({ email: 'user@example.com' })).toBeNull();
    expect(parseSignInCredentials({ email: 'not-an-email', password: 'secret' })).toBeNull();
    expect(
      parseSignInCredentials({ email: 'user@example.com', password: 'x'.repeat(1_025) }),
    ).toBeNull();
  });

  it('maps identity failures to approved codes and safe statuses', () => {
    expect(mapSignInError(new SignInError('invalid_credentials'))).toEqual({
      code: 'invalid_credentials',
      status: 401,
    });
    expect(mapSignInError(new SignInError('account_locked'))).toEqual({
      code: 'account_locked',
      status: 423,
    });
    expect(mapSignInError(new BackendUnavailableError())).toEqual({
      code: 'temporarily_unavailable',
      status: 503,
    });
    expect(mapSignInError(new Error('raw provider text'))).toEqual({
      code: 'temporarily_unavailable',
      status: 503,
    });
  });

  it('returns the permission-derived landing path without exposing user data', async () => {
    const executive = {
      signIn: vi.fn(async () => ({
        sessionId: 'session-1',
        user: user(['read']),
        record: {},
      })),
    } as unknown as SessionService;
    const admin = {
      signIn: vi.fn(async () => ({
        sessionId: 'session-2',
        user: user(['manage_settings']),
        record: {},
      })),
    } as unknown as SessionService;

    expect(await signInWithService(executive, { email: 'a@b.com', password: 'x' })).toEqual({
      sessionId: 'session-1',
      redirectTo: '/ask',
    });
    expect(await signInWithService(admin, { email: 'a@b.com', password: 'x' })).toEqual({
      sessionId: 'session-2',
      redirectTo: '/settings',
    });
  });
});
