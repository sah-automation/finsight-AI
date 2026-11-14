import 'server-only';

import { clearSessionCookie } from '@/lib/auth/cookies';
import { getServerSession } from '@/lib/auth/server-session';
import { getServerConfig } from '@/lib/config/server-config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const NO_STORE = { 'Cache-Control': 'no-store' } as const;

export async function GET(): Promise<Response> {
  const state = await getServerSession();
  if (state.status !== 'active') {
    return Response.json({ error: 'session_expired' }, { status: 401, headers: NO_STORE });
  }
  return Response.json(
    {
      user: {
        companyName: state.user.company_name,
        roleId: state.user.role_id,
        roleName: state.user.role_name ?? null,
        permissions: state.user.permissions ?? [],
      },
    },
    { status: 200, headers: NO_STORE },
  );
}

export async function DELETE(): Promise<Response> {
  await clearSessionCookie(getServerConfig());
  return new Response(null, { status: 204, headers: NO_STORE });
}
