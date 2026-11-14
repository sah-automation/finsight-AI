import { describe, expect, it, vi } from 'vitest';

import type { CurrentUser } from '@/lib/auth/current-user';
import { SessionService } from '@/lib/auth/session-service';
import { MemorySessionStore } from '@/lib/auth/session-store';
import {
  BackendUnavailableError,
  SessionExpiredError,
  SignInError,
  type IdentityProvider,
  type TokenSet,
} from '@/lib/auth/types';

const USER: CurrentUser = {
  company_id: 'company-1',
  company_name: 'Acme',
  company_display_name: 'Acme',
  role: 'executive_leadership',
  role_id: 'executive_leadership',
  role_name: 'Executive Leadership',
  permissions: ['read'],
  category_permissions: {},
};

function tokens(overrides: Partial<TokenSet> = {}): TokenSet {
  return {
    username: 'user@example.com',
    accessToken: 'access-1',
    idToken: 'id-1',
    refreshToken: 'refresh-1',
    accessTokenExpiresAt: 60_000,
    ...overrides,
  };
}

function provider(overrides: Partial<IdentityProvider> = {}): IdentityProvider {
  return {
    signIn: vi.fn(async () => tokens()),
    refresh: vi.fn(async () => tokens({ accessToken: 'access-2', refreshToken: 'refresh-2' })),
    ...overrides,
  };
}

function service(options: {
  now: number;
  identityProvider?: IdentityProvider;
  store?: MemorySessionStore;
}) {
  const now = () => options.now;
  const store = options.store ?? new MemorySessionStore(now);
  const currentUserClient = { fetch: vi.fn(async () => USER) };
  return {
    store,
    currentUserClient,
    service: new SessionService({
      store,
      identityProvider: options.identityProvider ?? provider(),
      currentUserClient,
      ttlSeconds: 3_600,
      refreshAheadSeconds: 60,
      clock: now,
    }),
  };
}

describe('SessionService', () => {
  it('stores Cognito tokens server-side and returns only the session id', async () => {
    const { service: sessions, store } = service({ now: 1_000 });
    const signedIn = await sessions.signIn('user@example.com', 'secret');

    expect(signedIn.sessionId).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(signedIn.user).toEqual(USER);
    const record = await store.get(signedIn.sessionId);
    expect(record).toMatchObject({
      accessToken: 'access-1',
      idToken: 'id-1',
      refreshToken: 'refresh-1',
      createdAt: 1_000,
      expiresAt: 1_000 + 3_600_000,
    });
  });

  it('returns the stored record while the access token is fresh', async () => {
    const identityProvider = provider({
      signIn: async () => tokens({ accessTokenExpiresAt: 600_000 }),
    });
    const { service: sessions } = service({ now: 0, identityProvider });
    const signedIn = await sessions.signIn('user@example.com', 'secret');
    const record = await sessions.resolve(signedIn.sessionId);
    expect(record.accessToken).toBe('access-1');
    expect(identityProvider.refresh).not.toHaveBeenCalled();
  });

  it('refreshes tokens shortly before access-token expiry', async () => {
    const identityProvider = provider();
    let now = 1_000;
    const store = new MemorySessionStore(() => now);
    const sessions = new SessionService({
      store,
      identityProvider,
      currentUserClient: { fetch: async () => USER },
      ttlSeconds: 3_600,
      refreshAheadSeconds: 60,
      clock: () => now,
    });

    const signedIn = await sessions.signIn('user@example.com', 'secret');
    now = 59_970;

    const record = await sessions.resolve(signedIn.sessionId);
    expect(identityProvider.refresh).toHaveBeenCalledWith('refresh-1', 'user@example.com');
    expect(record.accessToken).toBe('access-2');
    expect(record.refreshToken).toBe('refresh-2');
    expect((await store.get(signedIn.sessionId))?.accessToken).toBe('access-2');
  });

  it('deletes and rejects expired sessions', async () => {
    const { service: sessions, store } = service({ now: 1_000 });
    const signedIn = await sessions.signIn('user@example.com', 'secret');

    const later = new SessionService({
      store,
      identityProvider: provider(),
      currentUserClient: { fetch: async () => USER },
      ttlSeconds: 3_600,
      refreshAheadSeconds: 60,
      clock: () => 1_000 + 3_600_000,
    });

    await expect(later.resolve(signedIn.sessionId)).rejects.toBeInstanceOf(
      SessionExpiredError,
    );
    expect(await store.get(signedIn.sessionId)).toBeNull();
  });

  it('deletes the session when refresh is rejected', async () => {
    let now = 1_000;
    const store = new MemorySessionStore(() => now);
    const identityProvider = provider({
      refresh: vi.fn(async () => {
        throw new SignInError('invalid_credentials');
      }),
    });
    const sessions = new SessionService({
      store,
      identityProvider,
      currentUserClient: { fetch: async () => USER },
      ttlSeconds: 3_600,
      refreshAheadSeconds: 60,
      clock: () => now,
    });

    const signedIn = await sessions.signIn('user@example.com', 'secret');
    now = 59_970;

    await expect(sessions.resolve(signedIn.sessionId)).rejects.toBeInstanceOf(
      SessionExpiredError,
    );
    expect(await store.get(signedIn.sessionId)).toBeNull();
  });

  it('keeps the session when the identity provider is temporarily unavailable', async () => {
    let now = 1_000;
    const store = new MemorySessionStore(() => now);
    const identityProvider = provider({
      refresh: vi.fn(async () => {
        throw new SignInError('temporarily_unavailable');
      }),
    });
    const sessions = new SessionService({
      store,
      identityProvider,
      currentUserClient: { fetch: async () => USER },
      ttlSeconds: 3_600,
      refreshAheadSeconds: 60,
      clock: () => now,
    });

    const signedIn = await sessions.signIn('user@example.com', 'secret');
    now = 59_970;

    await expect(sessions.resolve(signedIn.sessionId)).rejects.toBeInstanceOf(
      BackendUnavailableError,
    );
    expect(await store.get(signedIn.sessionId)).not.toBeNull();
  });

  it('fetches the current user with the session access token and signs out', async () => {
    const identityProvider = provider({
      signIn: async () => tokens({ accessTokenExpiresAt: 600_000 }),
    });
    const { service: sessions, store, currentUserClient } = service({ now: 0, identityProvider });
    const signedIn = await sessions.signIn('user@example.com', 'secret');

    expect(await sessions.currentUser(signedIn.sessionId)).toEqual(USER);
    expect(currentUserClient.fetch).toHaveBeenLastCalledWith('access-1');

    await sessions.signOut(signedIn.sessionId);
    expect(await store.get(signedIn.sessionId)).toBeNull();
  });
});
