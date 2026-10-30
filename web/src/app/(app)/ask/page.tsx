import type { Metadata } from 'next';

import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { canAsk } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

export const metadata: Metadata = { title: messages.navigation.ask };

export default async function AskPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canAsk(user.permissions ?? []));

  return (
    <div className="space-y-6">
      <PageHeader title={messages.navigation.ask} />
      <EmptyState title={messages.ask.empty} />
    </div>
  );
}
