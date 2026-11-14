import type { Metadata } from 'next';

import { canViewDocuments } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';
import DocumentsLibrary from './documents-library';

export const metadata: Metadata = { title: messages.navigation.documents };

export default async function DocumentsPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canViewDocuments(user.permissions ?? []));

  return <DocumentsLibrary user={user} permissions={user.permissions ?? []} />;
}
