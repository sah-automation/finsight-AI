import type { Metadata } from 'next';

import { canAsk } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';
import AskScreen from './ask-screen';

export const metadata: Metadata = { title: messages.navigation.ask };

export default async function AskPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canAsk(user.permissions ?? []));

  return <AskScreen user={user} permissions={user.permissions ?? []} />;
}
