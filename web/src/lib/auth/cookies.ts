import 'server-only';

import { cookies } from 'next/headers';

import type { ServerConfig } from '@/lib/config/server-config';

export interface SessionCookieOptions {
  httpOnly: true;
  secure: boolean;
  sameSite: 'lax';
  path: '/';
  maxAge: number;
}

/**
 * The browser only ever sees this opaque session id. Cognito tokens stay in the
 * server-side session record.
 */
export function sessionCookieOptions(config: ServerConfig): SessionCookieOptions {
  return {
    httpOnly: true,
    secure: config.sessionCookieSecure,
    sameSite: 'lax',
    path: '/',
    maxAge: config.sessionTtlSeconds,
  };
}

export async function readSessionId(config: ServerConfig): Promise<string | null> {
  const store = await cookies();
  return store.get(config.sessionCookieName)?.value ?? null;
}

export async function writeSessionCookie(config: ServerConfig, sessionId: string): Promise<void> {
  const store = await cookies();
  store.set(config.sessionCookieName, sessionId, sessionCookieOptions(config));
}

export async function clearSessionCookie(config: ServerConfig): Promise<void> {
  const store = await cookies();
  store.set(config.sessionCookieName, '', {
    ...sessionCookieOptions(config),
    maxAge: 0,
  });
}
