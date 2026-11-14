import 'server-only';

import { SignInError, type IdentityProvider, type TokenSet } from '@/lib/auth/types';

/**
 * Mock identity provider for local development.
 * Accepts any email/password and returns fake tokens.
 * ONLY use in development - never in production.
 */
export class MockIdentityProvider implements IdentityProvider {
  private readonly users = new Map<string, { password: string; permissions: string[] }>();

  constructor() {
    // Pre-seed a test user
    this.users.set('admin@testcompany.com', {
      password: 'YourPassword123!',
      permissions: ['system_admin'],
    });
    this.users.set('user@testcompany.com', {
      password: 'password123',
      permissions: ['finance_manager'],
    });
  }

  addUser(email: string, password: string, permissions: string[] = []): void {
    this.users.set(email.toLowerCase(), { password, permissions });
  }

  async signIn(email: string, password: string): Promise<TokenSet> {
    const normalizedEmail = email.toLowerCase().trim();
    const user = this.users.get(normalizedEmail);

    if (!user || user.password !== password) {
      throw new SignInError('invalid_credentials');
    }

    const now = Date.now();
    return {
      username: normalizedEmail,
      accessToken: `mock-access-token-${normalizedEmail}-${now}`,
      idToken: `mock-id-token-${normalizedEmail}-${now}`,
      refreshToken: `mock-refresh-token-${normalizedEmail}-${now}`,
      accessTokenExpiresAt: now + 24 * 60 * 60 * 1000, // 24 hours
    };
  }

  async refresh(refreshToken: string, username: string): Promise<TokenSet> {
    const normalizedEmail = username.toLowerCase().trim();
    const user = this.users.get(normalizedEmail);

    if (!user) {
      throw new SignInError('invalid_credentials');
    }

    const now = Date.now();
    return {
      username: normalizedEmail,
      accessToken: `mock-access-token-${normalizedEmail}-${now}`,
      idToken: `mock-id-token-${normalizedEmail}-${now}`,
      refreshToken: `mock-refresh-token-${normalizedEmail}-${now}`,
      accessTokenExpiresAt: now + 24 * 60 * 60 * 1000,
    };
  }
}

/**
 * Singleton for development use.
 * In production, this should never be used.
 */
let devMockProvider: MockIdentityProvider | null = null;

export function getDevMockProvider(): MockIdentityProvider {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('MockIdentityProvider must not be used in production');
  }
  devMockProvider ??= new MockIdentityProvider();
  return devMockProvider;
}

export function resetDevMockProviderForTests(): void {
  devMockProvider = null;
}
