import type { Metadata } from 'next';

import { canUpload } from '@/lib/auth/permissions';
import { requireCurrentUser, requirePageAccess } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';
import UploadForm from './upload-form';

export const metadata: Metadata = { title: messages.navigation.upload };

export default async function UploadPage() {
  const user = await requireCurrentUser();
  requirePageAccess(user, canUpload(user.permissions ?? []));

  return <UploadForm user={user} permissions={user.permissions ?? []} />;
}
