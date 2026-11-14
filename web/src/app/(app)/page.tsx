import { redirect } from 'next/navigation';

import { landingPath } from '@/lib/auth/permissions';
import { requireCurrentUser } from '@/lib/auth/server-session';

export default async function HomePage() {
  const user = await requireCurrentUser();
  redirect(landingPath(user.permissions ?? []));
}
