import type { Metadata } from 'next';

import { PageHeader } from '@/components/ui/page-header';
import { requireCurrentUser } from '@/lib/auth/server-session';
import { messages } from '@/lib/messages';

export const metadata: Metadata = { title: messages.permission.denied };

export default async function PermissionDeniedPage() {
  await requireCurrentUser();

  return <PageHeader title={messages.permission.denied} />;
}
