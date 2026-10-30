import type { Metadata } from 'next';

import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { canViewDocuments } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

export const metadata: Metadata = { title: messages.navigation.documents };

export default async function DocumentsPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canViewDocuments(user.permissions ?? []));

  return (
    <div className="space-y-6">
      <PageHeader title={messages.navigation.documents} />
      <EmptyState title={messages.documents.empty} />
    </div>
  );
}
