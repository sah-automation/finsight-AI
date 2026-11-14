import { AppShell } from '@/components/shell/app-shell';
import { requireCurrentUser } from '@/lib/auth/server-session';

export const dynamic = 'force-dynamic';

export default async function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireCurrentUser();
  return <AppShell user={user}>{children}</AppShell>;
}
