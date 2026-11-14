import 'server-only';

import { cache } from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import type { CurrentUser } from '@/lib/auth/current-user';
import { getSessionService } from '@/lib/auth/session-factory';
import { SessionExpiredError } from '@/lib/auth/types';
import { getServerConfig } from '@/lib/config/server-config';

export type ServerSessionState =
  | { status: 'active'; user: CurrentUser }
  | { status: 'anonymous' }
  | { status: 'expired' };

const SIGN_IN_PATH = '/sign-in';
const EXPIRED_SIGN_IN_PATH = '/sign-in?reason=expired';

/**
 * Reads the opaque session cookie and resolves the current user from the BFF
 * session. Memoised for the lifetime of one server request.
 */
export const getServerSession = cache(async (): Promise<ServerSessionState> => {
  const cookieStore = await cookies();
  const config = getServerConfig();
  const sessionId = cookieStore.get(config.sessionCookieName)?.value;
  if (!sessionId) {
    return { status: 'anonymous' };
  }

  try {
    const user = await getSessionService().currentUser(sessionId);
    return { status: 'active', user };
  } catch (error) {
    if (error instanceof SessionExpiredError) {
      return { status: 'expired' };
    }
    throw error;
  }
});

export async function requireCurrentUser(): Promise<CurrentUser> {
  const state = await getServerSession();
  if (state.status === 'active') {
    return state.user;
  }
  redirect(state.status === 'expired' ? EXPIRED_SIGN_IN_PATH : SIGN_IN_PATH);
}

/**
 * Direct visits to forbidden URLs land on the permission-denied screen, never a
 * blank page or a redirect loop.
 */
export function requirePageAccess(user: CurrentUser, allowed: boolean): void {
  if (!allowed) {
    redirect('/permission-denied');
  }
}
