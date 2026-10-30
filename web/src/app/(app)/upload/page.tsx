import type { Metadata } from 'next';

import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { canUpload } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

export const metadata: Metadata = { title: messages.navigation.upload };

export default async function UploadPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canUpload(user.permissions ?? []));

  return (
    <div className="space-y-6">
      <PageHeader title={messages.navigation.upload} />
      <EmptyState title={messages.upload.empty} />
    </div>
  );
}
