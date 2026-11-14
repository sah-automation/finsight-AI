import { describe, expect, it } from 'vitest';

import { MemorySessionStore, type SessionRecord } from '@/lib/auth/session-store';

function record(overrides: Partial<SessionRecord> = {}): SessionRecord {
  return {
    id: 'session-1',
    username: 'user@example.com',
    accessToken: 'access',
    idToken: 'id',
    refreshToken: 'refresh',
    accessTokenExpiresAt: 2_000,
    createdAt: 1_000,
    expiresAt: 10_000,
    ...overrides,
  };
}

describe('MemorySessionStore', () => {
  it('returns a copy so callers cannot mutate stored tokens', async () => {
    const store = new MemorySessionStore(() => 1_000);
    const original = record();
    await store.set(original);

    const loaded = await store.get('session-1');
    expect(loaded).toEqual(original);
    if (loaded) {
      loaded.accessToken = 'mutated';
    }
    expect((await store.get('session-1'))?.accessToken).toBe('access');
  });

  it('drops expired sessions on read', async () => {
    const store = new MemorySessionStore(() => 10_000);
    await store.set(record({ expiresAt: 10_000 }));
    expect(await store.get('session-1')).toBeNull();
  });

  it('deletes sessions', async () => {
    const store = new MemorySessionStore(() => 1_000);
    await store.set(record());
    await store.delete('session-1');
    expect(await store.get('session-1')).toBeNull();
  });
});
