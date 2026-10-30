import 'server-only';

import { clearSessionCookie, readSessionId } from '@/lib/auth/cookies';
import { getSessionService } from '@/lib/auth/session-factory';
import { getServerConfig } from '@/lib/config/server-config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(): Promise<Response> {
  const config = getServerConfig();
  const sessionId = await readSessionId(config);
  if (sessionId) {
    try {
      await getSessionService().signOut(sessionId);
    } catch {
      // Always clear the browser cookie, even if the store is unavailable.
    }
  }
  await clearSessionCookie(config);
  return new Response(null, {
    status: 303,
    headers: {
      Location: '/sign-in',
      'Cache-Control': 'no-store',
    },
  });
}
