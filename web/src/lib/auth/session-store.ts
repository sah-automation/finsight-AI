import { randomBytes } from 'node:crypto';

export interface SessionRecord {
  id: string;
  username: string;
  accessToken: string;
  idToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
  createdAt: number;
  expiresAt: number;
}

export interface SessionStore {
  get(id: string): Promise<SessionRecord | null>;
  set(record: SessionRecord): Promise<void>;
  delete(id: string): Promise<void>;
}

export function createSessionId(): string {
  return randomBytes(32).toString('base64url');
}

// Global singleton for development - survives across module reloads in Next.js dev
const globalForSessionStore = globalThis as unknown as {
  __memorySessionStore: MemorySessionStore | undefined;
};

/**
 * Process-local store for local development and tests. Production selects the
 * DynamoDB store so sessions survive across server instances.
 */
export class MemorySessionStore implements SessionStore {
  private readonly records = new Map<string, SessionRecord>();
  private readonly clock: () => number;

  constructor(clock: () => number = Date.now) {
    this.clock = clock;
  }

  static getInstance(): MemorySessionStore {
    if (!globalForSessionStore.__memorySessionStore) {
      globalForSessionStore.__memorySessionStore = new MemorySessionStore();
    }
    return globalForSessionStore.__memorySessionStore;
  }

  async get(id: string): Promise<SessionRecord | null> {
    const record = this.records.get(id);
    if (!record) {
      return null;
    }
    if (record.expiresAt <= this.clock()) {
      this.records.delete(id);
      return null;
    }
    return { ...record };
  }

  async set(record: SessionRecord): Promise<void> {
    this.records.set(record.id, { ...record });
  }

  async delete(id: string): Promise<void> {
    this.records.delete(id);
  }
}
