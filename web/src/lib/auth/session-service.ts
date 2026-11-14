import 'server-only';

import { BackendUnavailableError, SessionExpiredError, SignInError } from '@/lib/auth/types';
import type { CurrentUser, CurrentUserClient } from '@/lib/auth/current-user';
import {
  createSessionId,
  type SessionRecord,
  type SessionStore,
} from '@/lib/auth/session-store';
import type { IdentityProvider } from '@/lib/auth/types';

export interface SessionServiceOptions {
  store: SessionStore;
  identityProvider: IdentityProvider;
  currentUserClient: CurrentUserClient;
  ttlSeconds: number;
  refreshAheadSeconds: number;
  clock?: () => number;
}

export interface SignedInSession {
  sessionId: string;
  user: CurrentUser;
  record: SessionRecord;
}

/**
 * Owns the server-side session lifecycle. Access and ID tokens stay in the
 * session record; the browser receives only the opaque session id cookie.
 */
export class SessionService {
  private readonly store: SessionStore;
  private readonly identityProvider: IdentityProvider;
  private readonly currentUserClient: CurrentUserClient;
  private readonly ttlSeconds: number;
  private readonly refreshAheadSeconds: number;
  private readonly clock: () => number;

  constructor(options: SessionServiceOptions) {
    this.store = options.store;
    this.identityProvider = options.identityProvider;
    this.currentUserClient = options.currentUserClient;
    this.ttlSeconds = options.ttlSeconds;
    this.refreshAheadSeconds = options.refreshAheadSeconds;
    this.clock = options.clock ?? Date.now;
  }

  async signIn(email: string, password: string): Promise<SignedInSession> {
    const tokens = await this.identityProvider.signIn(email, password);
    const user = await this.currentUserClient.fetch(tokens.accessToken);
    const now = this.clock();
    const record: SessionRecord = {
      id: createSessionId(),
      username: tokens.username,
      accessToken: tokens.accessToken,
      idToken: tokens.idToken,
      refreshToken: tokens.refreshToken,
      accessTokenExpiresAt: tokens.accessTokenExpiresAt,
      createdAt: now,
      expiresAt: now + this.ttlSeconds * 1000,
    };
    await this.store.set(record);
    return { sessionId: record.id, user, record };
  }

  async resolve(sessionId: string): Promise<SessionRecord> {
    const record = await this.store.get(sessionId);
    if (!record) {
      throw new SessionExpiredError();
    }
    const now = this.clock();
    if (record.expiresAt <= now) {
      await this.store.delete(sessionId);
      throw new SessionExpiredError();
    }
    if (record.accessTokenExpiresAt - now > this.refreshAheadSeconds * 1000) {
      return record;
    }

    let refreshed;
    try {
      refreshed = await this.identityProvider.refresh(record.refreshToken, record.username);
    } catch (error) {
      if (error instanceof SignInError && error.code === 'temporarily_unavailable') {
        throw new BackendUnavailableError('Identity provider refresh failed');
      }
      await this.store.delete(sessionId);
      throw new SessionExpiredError();
    }

    const updated: SessionRecord = {
      ...record,
      accessToken: refreshed.accessToken,
      idToken: refreshed.idToken,
      refreshToken: refreshed.refreshToken,
      accessTokenExpiresAt: refreshed.accessTokenExpiresAt,
    };
    await this.store.set(updated);
    return updated;
  }

  async currentUser(sessionId: string): Promise<CurrentUser> {
    const record = await this.resolve(sessionId);
    return this.currentUserClient.fetch(record.accessToken);
  }

  async signOut(sessionId: string): Promise<void> {
    await this.store.delete(sessionId);
  }
}
