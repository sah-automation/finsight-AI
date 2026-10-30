import type { Metadata } from 'next';

import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { canManageSettings } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

export const metadata: Metadata = { title: messages.navigation.settings };

export default async function SettingsPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canManageSettings(user.permissions ?? []));

  return (
    <div className="space-y-6">
      <PageHeader title={messages.navigation.settings} />
      <EmptyState title={messages.settings.empty} />
    </div>
  );
}
